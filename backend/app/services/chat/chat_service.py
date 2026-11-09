import base64
import io
import json
import mimetypes
import random
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import logger
from PIL import Image
from sqlmodel import Session
from sse_starlette.sse import ServerSentEvent

from app.database.engine import engine
from app.database.models import Character, Message
from app.schemas.chat import ChatMessage
from app.services.embeddings.rag_service import rag_service
from app.services.tasks.queue import task_queue
from app.supervisors.model_supervisor import ModelState, model_supervisor


def file_to_data_url(file_path: str, max_dimension: int = 1096) -> str:
    """Reads, downscales if necessary, and converts image to base64 Data URL."""
    path = Path(file_path).resolve()
    mime_type, _ = mimetypes.guess_type(path)
    if not mime_type:
        mime_type = "image/jpeg"

    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            if max(img.size) > max_dimension:
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=85)
            encoded = base64.b64encode(buffered.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"


def format_messages_for_llm(
    messages: list[ChatMessage],
    knowledge_base_id: str | None = None,
) -> list[dict[str, Any]]:
    formatted = []

    rag_context = ""
    if knowledge_base_id and messages:
        last_user_msg = next((m.content for m in reversed(messages) if m.role == "user"), None)
        if last_user_msg:
            results = rag_service.search_similar(knowledge_base_id, last_user_msg, limit=3)
            if results:
                snippets = [f"[{r['file_name']}]:\n{r['text']}" for r in results]
                rag_context = (
                    "\n\nRelevant Context from Knowledge Base:\n"
                    + "\n---\n".join(snippets)
                    + "\n\nPlease use the above context to inform your answer when relevant."
                )

    for i, msg in enumerate(messages):
        content_text = msg.content
        if i == len(messages) - 1 and msg.role == "user" and rag_context:
            content_text = f"{content_text}\n{rag_context}"

        if not msg.image_paths:
            formatted.append({"role": msg.role, "content": content_text})
        else:
            parts: list[dict[str, Any]] = [{"type": "text", "text": content_text}]
            for img_path in msg.image_paths:
                data_url = file_to_data_url(img_path)
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    }
                )
            formatted.append({"role": msg.role, "content": parts})

    return formatted


def should_generate_image(mode: str, user_prompt: str) -> bool:
    """Evaluates whether to generate an image based on the selected mode."""
    if mode == "definitely":
        return True
    if mode == "probable":
        visual_triggers = [
            "draw",
            "picture",
            "image",
            "scene",
            "illustration",
            "painting",
            "visualize",
            "photo",
        ]
        has_keywords = any(w in user_prompt.lower() for w in visual_triggers)
        return has_keywords or (random.random() < 0.5)
    return False


async def stream_chat_completion(
    messages: list[ChatMessage],
    conversation_id: str | None = None,
    character_id: str | None = None,
    image_gen_mode: str = "none",
    knowledge_base_id: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> AsyncGenerator[ServerSentEvent, None]:
    if model_supervisor.state != ModelState.READY or not model_supervisor.active_model:
        err_msg = f"Model is not ready (current state: {model_supervisor.state.value})"
        yield ServerSentEvent(event="error", data=json.dumps({"error": err_msg}))
        return

    has_images = any(len(m.image_paths or []) > 0 for m in messages)
    if has_images and not model_supervisor.active_model.vision_supported:
        err_msg = (
            f"Active model '{model_supervisor.active_model.display_name}' does not support vision"
        )
        yield ServerSentEvent(event="error", data=json.dumps({"error": err_msg}))
        return

    # Apply Persona / Character settings if provided
    if character_id:
        with Session(engine) as db:
            char = db.get(Character, character_id)
            if char:
                logger.info(f"🎭 Activating Persona: '{char.name}' (Temp: {char.temperature})")
                messages = [ChatMessage(role="system", content=char.system_prompt)] + [
                    m for m in messages if m.role != "system"
                ]
                temperature = char.temperature

    # Apply guidance when image generation is requested
    if image_gen_mode == "definitely":
        guidance = (
            "\nNote: The user requested image generation. Provide a concise, creative response. "
            "Do NOT attempt to draw text diagrams, ascii art, or icon grids; the image will "
            "be generated and displayed by the system automatically."
        )
        if messages and messages[0].role == "system":
            messages[0].content += f"\n{guidance}"
        else:
            messages = [ChatMessage(role="system", content=guidance)] + messages

    await model_supervisor.slot_semaphore.acquire()
    model_supervisor.active_requests += 1

    yield ServerSentEvent(event="message_start", data=json.dumps({"status": "started"}))

    accumulated_response: list[str] = []

    try:
        url = f"{model_supervisor.base_url}/v1/chat/completions"
        payload = {
            "messages": format_messages_for_llm(messages, knowledge_base_id),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    yield ServerSentEvent(
                        event="error",
                        data=json.dumps({"error": f"Inference error: {err_body.decode()}"}),
                    )
                    return

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        raw_data = line[6:].strip()
                        if raw_data == "[DONE]":
                            break
                        try:
                            parsed = json.loads(raw_data)
                            choice = parsed.get("choices", [{}])[0]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")
                            finish_reason = choice.get("finish_reason")

                            if content:
                                accumulated_response.append(content)
                                yield ServerSentEvent(
                                    event="token",
                                    data=json.dumps({"text": content}),
                                )

                            # Emit finish reason (e.g. "length" vs "stop")
                            if finish_reason:
                                yield ServerSentEvent(
                                    event="message_end",
                                    data=json.dumps({"finish_reason": finish_reason}),
                                )
                        except json.JSONDecodeError:
                            continue

        if conversation_id and accumulated_response:
            full_text = "".join(accumulated_response)
            with Session(engine) as db:
                db.add(
                    Message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=full_text,
                    )
                )
                db.commit()

        yield ServerSentEvent(event="message_end", data=json.dumps({"finish_reason": "stop"}))

        # Autonomous in-chat image generation via ComfyUI
        last_user_prompt = next((m.content for m in reversed(messages) if m.role == "user"), "")
        if should_generate_image(image_gen_mode, last_user_prompt):
            image_task = task_queue.submit_task(
                task_type="image_generation",
                parameters={
                    "prompt": f"cinematic digital art of {last_user_prompt[:250]}",
                    "width": 512,
                    "height": 512,
                    "steps": 4,
                },
            )
            yield ServerSentEvent(
                event="image_generation_started",
                data=json.dumps({"task_id": image_task.id}),
            )
    except Exception as e:
        yield ServerSentEvent(event="error", data=json.dumps({"error": str(e)}))
    finally:
        model_supervisor.active_requests = max(0, model_supervisor.active_requests - 1)
        model_supervisor.last_active_at = datetime.now(UTC)
        model_supervisor.slot_semaphore.release()
