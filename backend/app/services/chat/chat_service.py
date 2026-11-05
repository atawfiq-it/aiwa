import base64
import io
import json
import mimetypes
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import httpx
from PIL import Image
from sqlmodel import Session
from sse_starlette.sse import ServerSentEvent

from app.database.engine import engine
from app.database.models import Message
from app.schemas.chat import ChatMessage
from app.services.embeddings.rag_service import rag_service
from app.supervisors.model_supervisor import ModelState, model_supervisor


def file_to_data_url(file_path: str, max_dimension: int = 1024) -> str:
    """Reads, optionally resizes, and converts image to base64 Data URL."""
    path = Path(file_path).resolve()
    mime_type, _ = mimetypes.guess_type(path)
    if not mime_type:
        mime_type = "image/jpeg"

    # Resize image if dimensions exceed max_dimension to minimize visual patch tokens
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
        # Fallback to raw file read if Pillow fails or not an image
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"


def format_messages_for_llm(
    messages: list[ChatMessage],
    knowledge_base_id: str | None = None,
) -> list[dict[str, Any]]:
    formatted = []

    # Inject RAG context into the last user query if KB is active
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
            # Multi-part content with Base64 data URLs
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


async def stream_chat_completion(
    messages: list[ChatMessage],
    conversation_id: str | None = None,
    knowledge_base_id: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
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

        async with httpx.AsyncClient(timeout=120.0) as client:
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
                            delta = parsed.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                accumulated_response.append(content)
                                yield ServerSentEvent(
                                    event="token",
                                    data=json.dumps({"text": content}),
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
    except Exception as e:
        yield ServerSentEvent(event="error", data=json.dumps({"error": str(e)}))
    finally:
        model_supervisor.active_requests = max(0, model_supervisor.active_requests - 1)
        model_supervisor.slot_semaphore.release()
