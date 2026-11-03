from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.security import verify_local_token
from app.database.engine import get_db
from app.database.models import GeneratedFile, Task
from app.services.media.comfyui import comfyui_adapter
from app.services.tasks.queue import task_queue

router = APIRouter(prefix="/media", tags=["Media"], dependencies=[Depends(verify_local_token)])


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(min_length=1)
    negative_prompt: str = "ugly, blurry, distorted, low quality"
    width: int = 512
    height: int = 512
    steps: int = 20


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file not found")
    return FileResponse(
        path=file_record.file_path,
        media_type=file_record.mime_type,
        filename=file_record.file_name,
    )
