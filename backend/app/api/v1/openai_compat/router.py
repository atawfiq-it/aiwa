from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.supervisors.model_supervisor import ModelState, model_supervisor

router = APIRouter(prefix="/v1", tags=["OpenAI Compatibility Router"])


class OpenAIChatMessage(BaseModel):
    role: str
    content: Any


class OpenAIChatRequest(BaseModel):
    model: str = "default"
    messages: list[OpenAIChatMessage]
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False


@router.get("/models")
def list_openai_models():
    """OpenAI-compatible model listing."""
    status_info = model_supervisor.get_status()
    models = []
    if status_info.get("active_model_id"):
        models.append(
            {
                "id": status_info["active_model_id"],
                "object": "model",
                "owned_by": "aiwa-local",
            }
        )
    else:
        models.append(
            {
                "id": "default-local-model",
                "object": "model",
                "owned_by": "aiwa-local",
            }
        )
    return {"object": "list", "data": models}


@router.post("/chat/completions")
async def openai_chat_completions(req: OpenAIChatRequest):
    """OpenAI-compatible chat completion proxying directly to llama-server."""
    if model_supervisor.state != ModelState.READY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local LLM model is not loaded in VRAM.",
        )

    url = f"{model_supervisor.base_url}/v1/chat/completions"
    payload = req.model_dump()

    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.post(url, json=payload)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()
