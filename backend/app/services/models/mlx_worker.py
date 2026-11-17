import argparse
import base64
import inspect
import json
import tempfile
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="AIWA MLX Worker")

LOADED_MODEL = None
LOADED_PROCESSOR = None
LOADED_CONFIG = None
IS_VISION = False


class ChatReq(BaseModel):
    messages: list[dict[str, Any]]
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = True


def extract_prompt_and_images(
    messages: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[str], list[str]]:
    """Separates text messages and decodes base64 or file:// images for mlx-vlm."""
    images: list[str] = []
    temp_files: list[str] = []
    clean_messages: list[dict[str, str]] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, list):
            text_parts = []
            for part in content:
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif part.get("type") == "image_url":
                    url = part.get("image_url", {}).get("url", "")
                    if url.startswith("data:image"):
                        _, b64data = url.split(",", 1)
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                        tmp.write(base64.b64decode(b64data))
                        tmp.close()
                        images.append(tmp.name)
                        temp_files.append(tmp.name)
                    elif url.startswith("file://"):
                        images.append(url[7:])
            clean_messages.append({"role": role, "content": "\n".join(text_parts)})
        else:
            clean_messages.append({"role": role, "content": str(content)})

    return clean_messages, images, temp_files


def _build_prompt(clean_msgs: list[dict[str, str]], num_images: int) -> str:
    """Formats conversation history into the model's native chat template."""
    if IS_VISION:
        from mlx_vlm.prompt_utils import apply_chat_template

        return apply_chat_template(
            LOADED_PROCESSOR,
            LOADED_CONFIG,
            clean_msgs,
            num_images=num_images,
        )

    return LOADED_PROCESSOR.apply_chat_template(
        clean_msgs, tokenize=False, add_generation_prompt=True
    )


def _generate_stream(
    clean_msgs: list[dict[str, str]],
    images: list[str],
    max_tokens: int,
    temperature: float,
):
    """Yields token text chunks from either mlx_vlm or mlx_lm."""
    prompt = _build_prompt(clean_msgs, len(images))

    if IS_VISION:
        from mlx_vlm import stream_generate

        sig_params = inspect.signature(stream_generate).parameters
        gen_kwargs: dict[str, Any] = {"max_tokens": max_tokens}
        if "temperature" in sig_params or "kwargs" in sig_params:
            gen_kwargs["temperature"] = temperature
        elif "temp" in sig_params:
            gen_kwargs["temp"] = temperature

        if images:
            gen_kwargs["image"] = images

        for chunk in stream_generate(
            LOADED_MODEL,
            LOADED_PROCESSOR,
            prompt,
            **gen_kwargs,
        ):
            text = getattr(chunk, "text", str(chunk))
            if text:
                yield text
    else:
        from mlx_lm import stream_generate

        sig_params = inspect.signature(stream_generate).parameters
        gen_kwargs = {"prompt": prompt, "max_tokens": max_tokens}
        if "temp" in sig_params:
            gen_kwargs["temp"] = temperature
        elif "temperature" in sig_params:
            gen_kwargs["temperature"] = temperature

        for chunk in stream_generate(LOADED_MODEL, LOADED_PROCESSOR, **gen_kwargs):
            text = getattr(chunk, "text", str(chunk))
            if text:
                yield text


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/models")
def list_models():
    return {"object": "list", "data": [{"id": "mlx-local-model", "object": "model"}]}


@app.post("/v1/chat/completions")
def chat_completions(req: ChatReq):
    clean_msgs, images, temp_files = extract_prompt_and_images(req.messages)

    if not req.stream:
        # Synchronous completion for Agent Studio & Workflows
        try:
            full_text = "".join(
                _generate_stream(clean_msgs, images, req.max_tokens, req.temperature)
            )
            return JSONResponse(
                {
                    "id": "mlx-chat-sync",
                    "object": "chat.completion",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": full_text},
                            "finish_reason": "stop",
                        }
                    ],
                }
            )
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})
        finally:
            for tf in temp_files:
                Path(tf).unlink(missing_ok=True)

    # Streaming SSE completion for Text & Vision Chat
    def sse_generator():
        try:
            for token_text in _generate_stream(clean_msgs, images, req.max_tokens, req.temperature):
                payload = {"choices": [{"delta": {"content": token_text}}]}
                yield f"data: {json.dumps(payload)}\n\n"

            end_payload = {"choices": [{"delta": {}, "finish_reason": "stop"}]}
            yield f"data: {json.dumps(end_payload)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            print(f"[MLX Worker Error] {e}", flush=True)
            err_payload = {"error": {"message": str(e)}}
            yield f"data: {json.dumps(err_payload)}\n\n"
        finally:
            for tf in temp_files:
                Path(tf).unlink(missing_ok=True)

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AIWA Local MLX Inference Worker")
    parser.add_argument("--model", required=True, help="Path to MLX model directory")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--vision", action="store_true")
    args = parser.parse_args()

    IS_VISION = args.vision
    print(f"[MLX Worker] Loading model from: {args.model} (Vision={IS_VISION})...", flush=True)

    if IS_VISION:
        from mlx_vlm import load
        from mlx_vlm.utils import load_config

        LOADED_CONFIG = load_config(args.model)
        LOADED_MODEL, LOADED_PROCESSOR = load(args.model, trust_remote_code=True)
    else:
        from mlx_lm import load

        LOADED_MODEL, LOADED_PROCESSOR = load(args.model)

    print(
        f"[MLX Worker] ✅ Model loaded! Starting HTTP server on {args.host}:{args.port}...",
        flush=True,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
