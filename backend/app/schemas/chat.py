from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str
    image_paths: list[str] | None = Field(default_factory=list)


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    character_id: str | None = None
    image_gen_mode: str = "none"  # "none", "probable", "definitely"
    knowledge_base_id: str | None = None
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 2048
