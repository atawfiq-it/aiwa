import uuid
from datetime import UTC, datetime

from sqlalchemy import MetaData
from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


# Ensure all constraints have deterministic names for SQLite batch migrations
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
SQLModel.metadata = MetaData(naming_convention=naming_convention)


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: str = Field(default="New Conversation")
    character_id: str | None = Field(default=None, foreign_key="characters.id")
    image_gen_mode: str = Field(default="none")  # "none", "probable", "definitely"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    messages: list["Message"] = Relationship(back_populates="conversation", cascade_delete=True)


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    conversation_id: str = Field(foreign_key="conversations.id", index=True)
    role: str = Field(index=True)
    content: str = Field(default="")
    created_at: datetime = Field(default_factory=utc_now)

    conversation: Conversation | None = Relationship(back_populates="messages")
    attachments: list["Attachment"] = Relationship(back_populates="message", cascade_delete=True)


class Attachment(SQLModel, table=True):
    __tablename__ = "attachments"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    message_id: str | None = Field(default=None, foreign_key="messages.id", index=True)
    file_name: str
    file_path: str
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
    task_type: str = Field(index=True)
    status: str = Field(default="pending", index=True)
    progress_percent: int = Field(default=0)
    parameters: str = Field(default="{}")
    result: str | None = Field(default=None)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class GeneratedFile(SQLModel, table=True):
    __tablename__ = "generated_files"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    task_id: str | None = Field(default=None, foreign_key="tasks.id", index=True)
    file_type: str = Field(index=True)
    file_name: str
    file_path: str
    mime_type: str
    file_size_bytes: int
    prompt: str | None = None
    metadata_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=utc_now)


class KnowledgeBase(SQLModel, table=True):
    __tablename__ = "knowledge_bases"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    description: str | None = None
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    documents: list["DocumentRecord"] = Relationship(
        back_populates="knowledge_base", cascade_delete=True
    )


class DocumentRecord(SQLModel, table=True):
    __tablename__ = "documents"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    knowledge_base_id: str = Field(foreign_key="knowledge_bases.id", index=True)
    file_name: str
    file_path: str
    num_chunks: int = Field(default=0)
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=utc_now)

    knowledge_base: KnowledgeBase | None = Relationship(back_populates="documents")


class Agent(SQLModel, table=True):
    __tablename__ = "agents"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    description: str | None = None
    system_prompt: str = Field(
        default="You are an autonomous AI assistant equipped with specialized tools."
    )
    tools_json: str = Field(default="[]")  # JSON list of allowed tool names
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ToolExecution(SQLModel, table=True):
    __tablename__ = "tool_executions"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    agent_id: str | None = Field(default=None, foreign_key="agents.id", index=True)
    tool_name: str = Field(index=True)
    arguments_json: str = Field(default="{}")
    status: str = Field(
        default="pending_approval", index=True
    )  # "pending_approval", "approved", "rejected", "completed", "failed"
    result_json: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class Workflow(SQLModel, table=True):
    __tablename__ = "workflows"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    description: str | None = None
    steps_json: str = Field(default="[]")  # JSON list of step specifications
    created_at: datetime = Field(default_factory=utc_now)


class WorkflowRun(SQLModel, table=True):
    __tablename__ = "workflow_runs"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    workflow_id: str = Field(foreign_key="workflows.id", index=True)
    status: str = Field(
        default="running", index=True
    )  # "running", "completed", "failed", "cancelled"
    current_step_index: int = Field(default=0)
    total_steps: int = Field(default=0)
    current_task_id: str | None = None
    input_data_json: str = Field(default="{}")
    context_data_json: str = Field(default="{}")  # Accumulated step outputs
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class Character(SQLModel, table=True):
    __tablename__ = "characters"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    avatar_emoji: str = Field(default="🤖")
    description: str | None = None
    system_prompt: str
    voice_persona: str = Field(default="af_heart")  # "af_heart", "am_adam", "bf_emma"
    temperature: float = Field(default=0.7)
    is_builtin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)
