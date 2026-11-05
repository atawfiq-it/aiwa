from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import verify_local_token
from app.database.models import Task
from app.services.models.huggingface_service import hf_service
from app.services.tasks.queue import task_queue

router = APIRouter(
    prefix="/hf", tags=["HuggingFace Hub"], dependencies=[Depends(verify_local_token)]
)


class DownloadRequest(BaseModel):
    repo_id: str
    filename: str
    mmproj_filename: str | None = None


@router.get("/search")
def search_huggingface(query: str = "qwen", limit: int = 15):
    """Search for GGUF models on HuggingFace Hub."""
    return hf_service.search_gguf_models(query=query, limit=limit)


@router.get("/models/{repo_id:path}/files")
def get_model_files(repo_id: str):
    """Retrieve available GGUF and vision files in a HuggingFace repository."""
    return hf_service.get_repo_files(repo_id=repo_id)


@router.post("/download", response_model=Task)
def start_model_download(req: DownloadRequest):
    """Dispatches a background download task for a GGUF model."""
    return task_queue.submit_task(
        task_type="hf_model_download",
        parameters=req.model_dump(),
    )
