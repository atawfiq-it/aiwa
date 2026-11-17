import base64
import json
import logging
import mimetypes
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from PIL import Image
from sqlmodel import Session, select
from sse_starlette.sse import ServerSentEvent

from app.database.engine import engine
from app.database.models import Character, Conversation, Message
from app.schemas.chat import ChatMessage
from app.services.agents.grammar_compiler import grammar_compiler
from app.services.embeddings.rag_service import rag_service
from app.supervisors.model_supervisor import ModelState, model_supervisor

logger = logging.getLogger(__name__)


def file_to_data_url(file_path: str, max_dimension: int = 1024) -> str:
    """Reads, optionally resizes, and converts a local image to a base64 Data URL."""
    path = Path(file_path).resolve()
    mime_type, _ = mimetypes.guess_type(path)
    if not mime_type:
        mime_type = "image/jpeg"

    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            if max(img.size) > max_dimension:
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            import io

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
    """Formats chat messages for llama.cpp OpenAI-compatible API, injecting RAG context and vision URLs."""
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


async def stream_chat_completion(
    messages: list[ChatMessage],
    conversation_id: str | None = None,
    character_id: str | None = None,
    character_name: str | None = None,
    image_gen_mode: str = "none",
    knowledge_base_id: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    json_schema: dict[str, Any] | None = None,
) -> AsyncGenerator[ServerSentEvent, None]:
    """Streams tokens from llama.cpp over SSE with persona directives, RAG context, and GBNF grammars."""
    if model_supervisor.state != ModelState.READY or not model_supervisor.active_model:
        err_msg = (
            "No language model is currently loaded in GPU VRAM. "
            "Please select a model from the header and click 'Apply'."
        )
        yield ServerSentEvent(event="error", data=json.dumps({"error": err_msg}))
        return

    # Check vision capability
    has_images = any(len(m.image_paths or []) > 0 for m in messages)
    if has_images and not model_supervisor.active_model.vision_supported:
        err_msg = (
            f"Active model '{model_supervisor.active_model.display_name}' does not support vision."
        )
        yield ServerSentEvent(event="error", data=json.dumps({"error": err_msg}))
        return

    # 1. Multi-Tier Character Persona Resolution
    active_char_name = "None (Default Assistant)"
    active_prompt_text = ""

    with Session(engine) as db:
        char = None

        if character_id:
            char = db.get(Character, character_id)
            if not char:
                char = db.exec(select(Character).where(Character.name == character_id)).first()

        if not char and character_name:
            char = db.exec(select(Character).where(Character.name == character_name)).first()

        if not char and conversation_id:
            conv = db.get(Conversation, conversation_id)
            if conv and conv.character_id:
                char = db.get(Character, conv.character_id)

        if not char:
            char = db.exec(select(Character)).first()

        if char:
            active_char_name = char.name
            active_prompt_text = char.system_prompt
            temperature = char.temperature

            persona_instruction = (
                f"### SYSTEM INSTRUCTION: MANDATORY ROLEPLAY AS {char.name.upper()} ###\n"
                f"{char.system_prompt}\n"
                f"### END SYSTEM INSTRUCTION - MAINTAIN THIS PERSONA STRICTLY ###"
            )

            messages = [ChatMessage(role="system", content=persona_instruction)] + [
                m for m in messages if m.role != "system"
            ]

    # 2. Terminal Diagnostic Logging
    print("\n" + "=" * 65)
    print("🎭 [AIWA PERSONA DIAGNOSTICS]")
    print(f"   -> Character ID received:   {character_id}")
    print(f"   -> Character Name received: {character_name}")
    print(f"   -> Resolved Persona:        {active_char_name}")
    print(f"   -> Applied Temperature:     {temperature}")
    print(f"   -> System Prompt Preview:   {active_prompt_text[:100]}...")
    print("-" * 65)
    formatted_payload = format_messages_for_llm(messages, knowledge_base_id)
    print("📨 [PAYLOAD DISPATCHED TO LLAMA-SERVER]:")
    for idx, msg in enumerate(formatted_payload):
        role = msg.get("role", "unknown")
        content_preview = str(msg.get("content", ""))[:120].replace("\n", " ")
        print(f"   [{idx}] Role: {role:<9} | Content: {content_preview}...")
    print("=" * 65 + "\n")

    # Acquire concurrency slot semaphore
    await model_supervisor.slot_semaphore.acquire()
    model_supervisor.active_requests += 1

    yield ServerSentEvent(event="message_start", data=json.dumps({"status": "started"}))

    accumulated_response: list[str] = []

    try:
        url = f"{model_supervisor.base_url}/v1/chat/completions"
        payload: dict[str, Any] = {
            "messages": formatted_payload,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        # 3. GBNF Grammar Logits Masking Enforcement
        if json_schema:
            compiled_grammar = grammar_compiler.compile_schema(json_schema)
            payload["grammar"] = compiled_grammar
            logger.info("Enforced GBNF grammar on chat completion stream.")

        # Infinite read timeout for long answer generations
        timeout_config = httpx.Timeout(connect=15.0, read=None, write=30.0, pool=None)

        async with httpx.AsyncClient(timeout=timeout_config) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    yield ServerSentEvent(
                        event="error",
                        data=json.dumps({"error": f"Inference engine error: {err_body.decode()}"}),
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

                            if finish_reason:
                                yield ServerSentEvent(
                                    event="message_end",
                                    data=json.dumps({"finish_reason": finish_reason}),
                                )
                        except json.JSONDecodeError:
                            continue

        # 4. Persist completed assistant message into SQLite
        full_text = "".join(accumulated_response)
        if conversation_id and full_text:
            with Session(engine) as db:
                db.add(
                    Message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=full_text,
                    )
                )
                conv = db.get(Conversation, conversation_id)
                if conv:
                    conv.updated_at = datetime.now(UTC)
                    db.add(conv)
                db.commit()

        yield ServerSentEvent(event="message_end", data=json.dumps({"finish_reason": "stop"}))

    except Exception as e:
        logger.error(f"Inference stream failed: {e}", exc_info=True)
        yield ServerSentEvent(event="error", data=json.dumps({"error": str(e)}))
    finally:
        model_supervisor.active_requests = max(0, model_supervisor.active_requests - 1)
        model_supervisor.last_active_at = datetime.now(UTC)
        model_supervisor.slot_semaphore.release()
