from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.core.security import verify_local_token
from app.services.chat.chat_service import stream_chat_completion

router = APIRouter(prefix="/chat", tags=["Chat"], dependencies=[Depends(verify_local_token)])


class ChatRequest(BaseModel):
    messages: list[dict[str, str]]
    temperature: float = 0.7
    max_tokens: int = 2048


@router.post("/completions")
async def chat_completions(req: ChatRequest):
    return EventSourceResponse(
        stream_chat_completion(
            messages=req.messages,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    )
