import uuid
from datetime import UTC, datetime

from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: str = Field(default="New Conversation")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    messages: list["Message"] = Relationship(back_populates="conversation", cascade_delete=True)


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    conversation_id: str = Field(foreign_key="conversations.id", index=True)
    role: str = Field(index=True)  # "system", "user", "assistant"
    content: str = Field(default="")
    created_at: datetime = Field(default_factory=utc_now)

    conversation: Conversation | None = Relationship(back_populates="messages")
    attachments: list["Attachment"] = Relationship(back_populates="message", cascade_delete=True)


class Attachment(SQLModel, table=True):
    __tablename__ = "attachments"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    message_id: str | None = Field(default=None, foreign_key="messages.id", index=True)
    file_name: str
    file_path: str  # Absolute path on disk in data/uploads/
    mime_type: str
    file_size_bytes: int
    created_at: datetime = Field(default_factory=utc_now)

    message: Message | None = Relationship(back_populates="attachments")


class ModelConfig(SQLModel, table=True):
    __tablename__ = "models"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    display_name: str
    file_path: str = Field(unique=True)
    format: str = Field(default="gguf")
    context_length: int = Field(default=4096)
    quantization: str | None = None
    vision_supported: bool = Field(default=False)
    mmproj_path: str | None = None
    gpu_layers: int = Field(default=-1)
    estimated_vram_bytes: int | None = None
    is_default: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)
    last_used_at: datetime | None = None


class AppSetting(SQLModel, table=True):
    __tablename__ = "app_settings"

    key: str = Field(primary_key=True)
    value: str
    updated_at: datetime = Field(default_factory=utc_now)


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    task_type: str = Field(index=True)  # e.g., "image_generation", "rag_indexing", "stt"
    status: str = Field(default="pending", index=True)
    progress_percent: int = Field(default=0)
    parameters: str = Field(default="{}")  # JSON-encoded input parameters
    result: str | None = Field(default=None)  # JSON-encoded output or artifact info
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class GeneratedFile(SQLModel, table=True):
    __tablename__ = "generated_files"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    task_id: str | None = Field(default=None, foreign_key="tasks.id", index=True)
    file_type: str = Field(index=True)  # "image", "audio", "document"
    file_name: str
    file_path: str  # Absolute path on disk in data/generated/
    mime_type: str
    file_size_bytes: int
    prompt: str | None = None
    metadata_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=utc_now)
