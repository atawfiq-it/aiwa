from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.security import verify_local_token
from app.database.engine import get_db
from app.database.models import Attachment, Conversation, Message

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
    dependencies=[Depends(verify_local_token)],
)


class ConversationCreate(BaseModel):
    title: str | None = "New Conversation"


class ConversationUpdate(BaseModel):
    title: str


class MessageCreate(BaseModel):
    role: str
    content: str
    attachment_ids: list[str] | None = None


@router.post("", response_model=Conversation)
def create_conversation(
    req: ConversationCreate,
    db: Session = Depends(get_db),
):
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
def get_conversation_with_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

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
                "created_at": m.created_at,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    conv.title = req.title
    conv.updated_at = datetime.now(UTC)

    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg = Message(
        conversation_id=conversation_id,
        role=req.role,
        content=req.content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Associate attachments if provided
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
