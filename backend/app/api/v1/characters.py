from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.security import verify_local_token
from app.database.engine import get_db
from app.database.models import Character

router = APIRouter(
    prefix="/characters",
    tags=["Characters"],
    dependencies=[Depends(verify_local_token)],
)


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1)
    avatar_emoji: str = "🤖"
    description: str | None = None
    system_prompt: str = Field(min_length=5)
    voice_persona: str = "af_heart"
    temperature: float = 0.7


@router.get("", response_model=list[Character])
def list_characters(db: Session = Depends(get_db)):
    return db.exec(select(Character).order_by(Character.created_at.asc())).all()  # type: ignore


@router.post("", response_model=Character)
def create_character(req: CharacterCreate, db: Session = Depends(get_db)):
    char = Character(
        name=req.name,
        avatar_emoji=req.avatar_emoji,
        description=req.description,
        system_prompt=req.system_prompt,
        voice_persona=req.voice_persona,
        temperature=req.temperature,
    )
    db.add(char)
    db.commit()
    db.refresh(char)
    return char


@router.delete("/{character_id}")
def delete_character(character_id: str, db: Session = Depends(get_db)):
    char = db.get(Character, character_id)
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.is_builtin:
        raise HTTPException(status_code=400, detail="Cannot delete built-in starter characters")
    db.delete(char)
    db.commit()
    return {"status": "success", "message": "Character deleted"}
