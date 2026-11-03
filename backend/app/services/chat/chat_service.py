import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import httpx
from sqlmodel import Session
from sse_starlette.sse import ServerSentEvent

from app.database.engine import engine
from app.database.models import Message
from app.schemas.chat import ChatMessage
from app.supervisors.model_supervisor import ModelState, model_supervisor


def format_messages_for_llm(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    formatted = []
    for msg in messages:
        if not msg.image_paths:
            formatted.append({"role": msg.role, "content": msg.content})
        else:
            # Multi-part content with local file references
            parts: list[dict[str, Any]] = [{"type": "text", "text": msg.content}]
            for img_path in msg.image_paths:
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"file://{Path(img_path).resolve()}"},
                    }
                )
            formatted.append({"role": msg.role, "content": parts})
    return formatted


async def stream_chat_completion(
    messages: list[ChatMessage],
    conversation_id: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> AsyncGenerator[ServerSentEvent, None]:
    if model_supervisor.state != ModelState.READY or not model_supervisor.active_model:
        err_msg = f"Model is not ready (current state: {model_supervisor.state.value})"
        yield ServerSentEvent(event="error", data=json.dumps({"error": err_msg}))
        return

    # Check vision capability if images are present
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
            "messages": format_messages_for_llm(messages),
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

        # Persist completed assistant message if conversation_id was provided
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
