import json
from collections.abc import AsyncGenerator

import httpx
from sse_starlette.sse import ServerSentEvent

from app.supervisors.model_supervisor import ModelState, model_supervisor


async def stream_chat_completion(
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> AsyncGenerator[ServerSentEvent, None]:
    if model_supervisor.state != ModelState.READY:
        err_msg = f"Model is not ready (current state: {model_supervisor.state.value})"
        yield ServerSentEvent(
            event="error",
            data=json.dumps({"error": err_msg}),
        )
        return

    # Acquire slot semaphore
    await model_supervisor.slot_semaphore.acquire()
    model_supervisor.active_requests += 1

    yield ServerSentEvent(
        event="message_start",
        data=json.dumps({"status": "started"}),
    )

    try:
        url = f"{model_supervisor.base_url}/v1/chat/completions"
        payload = {
            "messages": messages,
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
                                yield ServerSentEvent(
                                    event="token",
                                    data=json.dumps({"text": content}),
                                )
                        except json.JSONDecodeError:
                            continue

        yield ServerSentEvent(
            event="message_end",
            data=json.dumps({"finish_reason": "stop"}),
        )
    except Exception as e:
        yield ServerSentEvent(
            event="error",
            data=json.dumps({"error": str(e)}),
        )
    finally:
        model_supervisor.active_requests = max(0, model_supervisor.active_requests - 1)
        model_supervisor.slot_semaphore.release()
