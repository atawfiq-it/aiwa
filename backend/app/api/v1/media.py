import csv
import io
import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import verify_local_token
from app.database.engine import get_db
from app.database.models import Attachment, GeneratedFile, Task
from app.services.media.comfyui import comfyui_adapter
from app.services.media.diffusers_service import direct_diffusion
from app.services.tasks.queue import task_queue

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/media", tags=["Media"], dependencies=[Depends(verify_local_token)])


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)
    voice: str = "af_heart"
    speed: float = 1.0


class PodcastTurn(BaseModel):
    speaker: str
    voice: str = "am_adam"
    text: str


class PodcastRequest(BaseModel):
    script: list[PodcastTurn]
    silence_ms: int = 350
    speed: float = 1.0


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(min_length=1)
    negative_prompt: str = "ugly, blurry, distorted, low quality"
    width: int = 512
    height: int = 512
    steps: int = 20


class STTRequest(BaseModel):
    attachment_id: str
    model_size: str = "base"


class DirectImageRequest(BaseModel):
    prompt: str = Field(min_length=1)
    negative_prompt: str = ""
    checkpoint_path: str
    width: int = 512
    height: int = 512
    steps: int = 25  # Default 25 steps for high quality
    guidance_scale: float = 7.0  # Default 7.0 for standard SD
    sampler: str = "DPM++ 2M Karras"
    seed: int = -1
    batch_size: int = 1
    style_preset: str = "none"


@router.post("/audio/podcast-csv")
async def create_podcast_from_csv(
    file: UploadFile,
    silence_ms: int = 350,
    speed: float = 1.0,
):
    """Parses a multi-line CSV file (speaker, voice, text) and synthesizes a continuous podcast episode."""
    content = await file.read()
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError:
        decoded = content.decode("latin-1")

    reader = csv.reader(io.StringIO(decoded))
    script = []

    for row in reader:
        if not row or len(row) < 2:
            continue
        # Skip header row if present
        if row[0].strip().lower() in ["speaker", "name"] and "text" in "".join(row).lower():
            continue

        if len(row) >= 3:
            speaker, voice, text = row[0].strip(), row[1].strip(), row[2].strip()
        else:
            # Fallback if only 2 columns (speaker, text) -> auto-assign voice
            speaker, text = row[0].strip(), row[1].strip()
            voice = (
                "am_adam" if "adam" in speaker.lower() or "host" in speaker.lower() else "bf_emma"
            )

        if text:
            script.append({"speaker": speaker, "voice": voice, "text": text})

    if not script:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file contained no valid dialogue rows. Required columns: speaker, voice, text",
        )

    from app.services.media.audio_service import audio_service

    out_path = audio_service.generate_podcast_dialogue(
        script=script, silence_ms=silence_ms, speed=speed
    )
    return FileResponse(
        path=str(out_path),
        media_type="audio/wav",
        filename=out_path.name,
    )


@router.get("/diffusion/checkpoints")
def get_diffusion_checkpoints():
    """Returns available .safetensors checkpoints for Image Studio."""
    return direct_diffusion.list_checkpoints()


@router.post("/diffusion/generate-direct")
async def generate_image_direct(req: DirectImageRequest):
    """Direct high-quality image generation with sampler, seed, and style presets."""
    try:
        return await direct_diffusion.generate_image(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            checkpoint_path=req.checkpoint_path,
            width=req.width,
            height=req.height,
            steps=req.steps,
            guidance_scale=req.guidance_scale,
            sampler=req.sampler,
            seed=req.seed,
            batch_size=req.batch_size,
            style_preset=req.style_preset,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


@router.get("/comfyui/status")
async def check_comfyui_status():
    available = await comfyui_adapter.is_available()
    return {"service": "ComfyUI", "available": available, "endpoint": comfyui_adapter.base_url}


@router.post("/images/generate", response_model=Task)
def generate_image(req: ImageGenerationRequest):
    return task_queue.submit_task(
        task_type="image_generation",
        parameters=req.model_dump(),
    )


@router.get("/gallery", response_model=list[GeneratedFile])
def list_generated_media(db: Session = Depends(get_db)):
    return db.exec(
        select(GeneratedFile).order_by(GeneratedFile.created_at.desc())  # type: ignore
    ).all()


@router.get("/files/{file_id}")
def download_media_file(file_id: str, db: Session = Depends(get_db)):
    file_record = db.get(GeneratedFile, file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media file not found",
        )
    return FileResponse(
        path=file_record.file_path,
        media_type=file_record.mime_type,
        filename=file_record.file_name,
    )


@router.get("/audio/status")
def audio_status():
    from app.services.media.audio_service import audio_service

    return {
        "stt_available": audio_service.is_stt_available(),
        "tts_available": audio_service.is_tts_available(),
    }


@router.post("/audio/speech", response_model=Task)
def create_text_to_speech(req: TTSRequest):
    return task_queue.submit_task(
        task_type="text_to_speech",
        parameters=req.model_dump(),
    )


@router.post("/audio/speech-direct")
async def speech_direct(req: TTSRequest):
    """Synthesize speech immediately and return the playable audio file."""
    try:
        from app.services.media.audio_service import audio_service

        out_path = audio_service.generate_speech(req.text, voice=req.voice, speed=req.speed)
        return FileResponse(
            path=str(out_path),
            media_type="audio/wav",
            filename=out_path.name,
        )
    except Exception as e:
        logger.error(f"Speech synthesis error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech synthesis failed: {str(e)}",
        ) from e


@router.post("/audio/podcast")
async def create_podcast(req: PodcastRequest):
    """Synthesize a multi-speaker podcast episode."""
    try:
        from app.services.media.audio_service import audio_service

        out_path = audio_service.generate_podcast_dialogue(
            script=[t.model_dump() for t in req.script],
            silence_ms=req.silence_ms,
            speed=req.speed,
        )
        return FileResponse(
            path=str(out_path),
            media_type="audio/wav",
            filename=out_path.name,
        )
    except Exception as e:
        logger.error(f"Podcast generation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Podcast generation failed: {str(e)}",
        ) from e


@router.post("/audio/transcribe", response_model=Task)
def transcribe_audio(req: STTRequest, db: Session = Depends(get_db)):
    att = db.get(Attachment, req.attachment_id)
    if not att:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    return task_queue.submit_task(
        task_type="audio_transcription",
        parameters={"file_path": att.file_path, "model_size": req.model_size},
    )


@router.post("/audio/transcribe-direct")
async def transcribe_audio_direct(
    file: UploadFile,
    model_size: str = "base",
):
    safe_name = f"mic_{uuid.uuid4().hex[:8]}.webm"
    temp_path = settings.UPLOADS_DIR / safe_name

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        from app.services.media.audio_service import audio_service

        result = audio_service.transcribe_audio(temp_path, model_size=model_size)
        return {"text": result["text"], "language": result.get("language")}
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.delete("/files/{file_id}")
def delete_generated_media_file(file_id: str, db: Session = Depends(get_db)):
    """Deletes the physical image/audio file from disk and its metadata from SQLite."""
    record = db.get(GeneratedFile, file_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated media file not found",
        )

    file_path = Path(record.file_path)
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            logger.warning(f"Could not remove physical file {file_path}: {e}")

    db.delete(record)
    db.commit()
    return {"status": "success", "message": f"Deleted {record.file_name}"}
