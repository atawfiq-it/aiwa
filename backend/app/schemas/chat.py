from typing import Any

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str
    image_paths: list[str] | None = Field(default_factory=list)


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    character_id: str | None = None
    character_name: str | None = None
    image_gen_mode: str = "none"
    knowledge_base_id: str | None = None
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 4096
    json_schema: dict[str, Any] | None = None  # GBNF-enforced structured schema
