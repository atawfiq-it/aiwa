from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.core.security import verify_local_token
from app.schemas.chat import ChatRequest
from app.services.chat.chat_service import stream_chat_completion

router = APIRouter(prefix="/chat", tags=["Chat"], dependencies=[Depends(verify_local_token)])


@router.post("/completions")
async def chat_completions(req: ChatRequest):
    return EventSourceResponse(
        stream_chat_completion(
            messages=req.messages,
            conversation_id=req.conversation_id,
            character_id=req.character_id,
            character_name=req.character_name,
            image_gen_mode=req.image_gen_mode,
            knowledge_base_id=req.knowledge_base_id,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    )
