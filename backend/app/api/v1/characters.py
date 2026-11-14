from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from PIL import Image, ImageDraw
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import verify_local_token
from app.database.engine import get_db
from app.database.models import Character

router = APIRouter(
    prefix="/characters",
    tags=["Characters"],
    dependencies=[Depends(verify_local_token)],
)

AVATARS_DIR = settings.DATA_DIR / "avatars"
AVATARS_DIR.mkdir(parents=True, exist_ok=True)


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1)
    avatar_emoji: str = "🤖"
    description: str | None = None
    system_prompt: str = Field(min_length=5)
    voice_persona: str = "af_heart"
    temperature: float = 0.7


def ensure_default_avatars_exist():
    """Generates clean default avatar image files on disk if not present."""
    default_img_path = AVATARS_DIR / "default.png"
    if not default_img_path.exists():
        # Create clean 256x256 fallback avatar
        img = Image.new("RGBA", (256, 256), color=(79, 70, 229))
        draw = ImageDraw.Draw(img)
        draw.ellipse((64, 40, 192, 168), fill=(255, 255, 255, 230))
        draw.ellipse((32, 180, 224, 300), fill=(255, 255, 255, 230))
        img.save(default_img_path)


ensure_default_avatars_exist()


@router.get("/avatars/{character_name}")
def get_character_avatar(character_name: str):
    """Serves local persona avatar from disk, falling back to default.png if missing."""
    safe_name = character_name.lower().replace(" ", "_").replace("/", "")
    custom_path = AVATARS_DIR / f"{safe_name}.png"
    default_path = AVATARS_DIR / "default.png"

    if custom_path.exists() and custom_path.is_file():
        return FileResponse(custom_path, media_type="image/png")
    return FileResponse(default_path, media_type="image/png")


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
