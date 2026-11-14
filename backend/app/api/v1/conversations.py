import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.security import verify_local_token
from app.database.engine import get_db
from app.database.models import Attachment, Conversation, Message
from app.supervisors.model_supervisor import model_supervisor

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
    dependencies=[Depends(verify_local_token)],
)


class ConversationCreate(BaseModel):
    title: str | None = "New Conversation"


class ConversationUpdate(BaseModel):
    title: str | None = None
    character_id: str | None = None


class MessageCreate(BaseModel):
    role: str
    content: str
    attachment_ids: list[str] | None = None


@router.post("", response_model=Conversation)
def create_conversation(req: ConversationCreate, db: Session = Depends(get_db)):
    conv = Conversation(title=req.title or "New Conversation")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("", response_model=list[Conversation])
def list_conversations(db: Session = Depends(get_db)):
    return db.exec(
        select(Conversation).order_by(Conversation.updated_at.desc())  # type: ignore
    ).all()


@router.get("/{conversation_id}")
def get_conversation_with_messages(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = db.exec(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())  # type: ignore
    ).all()

    return {
        "conversation": conv,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "attachments": m.attachments,
            }
            for m in messages
        ],
    }


@router.patch("/{conversation_id}", response_model=Conversation)
def rename_conversation(
    conversation_id: str,
    req: ConversationUpdate,
    db: Session = Depends(get_db),
):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if req.title is not None:
        conv.title = req.title.strip() or "Untitled Conversation"
    if req.character_id is not None:
        conv.character_id = req.character_id

    conv.updated_at = datetime.now(UTC)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return {"status": "success", "message": "Conversation deleted"}


@router.post("/{conversation_id}/messages", response_model=Message)
def add_message(
    conversation_id: str,
    req: MessageCreate,
    db: Session = Depends(get_db),
):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Choice 1 A: Auto-generate title from first user prompt if still default
    if conv.title == "New Conversation" and req.role == "user" and req.content.strip():
        first_line = req.content.strip().split("\n")[0]
        conv.title = first_line[:35] + ("..." if len(first_line) > 35 else "")

    msg = Message(
        conversation_id=conversation_id,
        role=req.role,
        content=req.content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    if req.attachment_ids:
        for att_id in req.attachment_ids:
            att = db.get(Attachment, att_id)
            if att:
                att.message_id = msg.id
                db.add(att)
        db.commit()

    conv.updated_at = datetime.now(UTC)
    db.add(conv)
    db.commit()
    db.refresh(msg)
    return msg


@router.get("/{conversation_id}/export")
def export_conversation_markdown(conversation_id: str, db: Session = Depends(get_db)):
    """Choice 2 B: Rich Markdown export with metadata and timestamps."""
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = db.exec(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())  # type: ignore
    ).all()

    active_model_name = (
        model_supervisor.active_model.display_name if model_supervisor.active_model else "Unknown"
    )

    # Build Rich Markdown document
    md_lines = [
        f"# {conv.title}",
        "",
        "> **AIWA Workstation Conversation Record**",
        f"> - **Conversation ID**: `{conv.id}`",
        f"> - **Exported At**: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"> - **Model**: {active_model_name}",
        f"> - **Total Messages**: {len(messages)}",
        "",
        "---",
        "",
    ]

    for m in messages:
        timestamp_str = m.created_at.strftime("%H:%M:%S")
        role_label = "👤 User" if m.role == "user" else "🤖 Assistant"

        md_lines.append(f"### {role_label} `[{timestamp_str}]`")
        if m.attachments:
            att_names = ", ".join(f"`{a.file_name}`" for a in m.attachments)
            md_lines.append(f"*Attachments: {att_names}*\n")
        md_lines.append(m.content)
        md_lines.append("\n---\n")

    full_md = "\n".join(md_lines)
    safe_title = re.sub(r"[^a-zA-Z0-9_\-]", "_", conv.title[:25])
    filename = f"chat_{safe_title}_{conv.id[:6]}.md"

    return Response(
        content=full_md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class MessageUpdate(BaseModel):
    content: str


@router.patch("/{conversation_id}/messages/{message_id}", response_model=Message)
def update_message(
    conversation_id: str,
    message_id: str,
    req: MessageUpdate,
    db: Session = Depends(get_db),
):
    """Updates the text content of a user prompt or assistant reply."""
    msg = db.get(Message, message_id)
    if not msg or msg.conversation_id != conversation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    msg.content = req.content
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.delete("/{conversation_id}/messages/{message_id}")
def delete_message(
    conversation_id: str,
    message_id: str,
    db: Session = Depends(get_db),
):
    """Permanently deletes a message from the conversation."""
    msg = db.get(Message, message_id)
    if not msg or msg.conversation_id != conversation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    db.delete(msg)
    db.commit()
    return {"status": "success", "message": "Message deleted"}
