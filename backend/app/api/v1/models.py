import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.security import verify_local_token
from app.database.engine import get_db
from app.database.models import ModelConfig
from app.supervisors.model_supervisor import model_supervisor

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/models",
    tags=["Models"],
    dependencies=[Depends(verify_local_token)],
)


class ModelRegisterRequest(BaseModel):
    display_name: str = Field(min_length=1)
    file_path: str
    format: str = "gguf"
    context_length: int = 4096
    quantization: str | None = None
    vision_supported: bool = False
    mmproj_path: str | None = None
    gpu_layers: int = -1
    is_default: bool = False


@router.get("", response_model=list[ModelConfig])
def list_models(db: Session = Depends(get_db)):
    return db.exec(select(ModelConfig)).all()


@router.post("", response_model=ModelConfig)
def register_model(req: ModelRegisterRequest, db: Session = Depends(get_db)):
    try:
        # Check if model path already exists -> Update instead of failing
        existing = db.exec(
            select(ModelConfig).where(ModelConfig.file_path == req.file_path)
        ).first()

        if existing:
            existing.display_name = req.display_name
            existing.context_length = req.context_length
            existing.vision_supported = req.vision_supported
            existing.mmproj_path = req.mmproj_path
            existing.gpu_layers = req.gpu_layers
            existing.is_default = req.is_default
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing

        new_model = ModelConfig(
            display_name=req.display_name,
            file_path=req.file_path,
            format=req.format,
            context_length=req.context_length,
            quantization=req.quantization,
            vision_supported=req.vision_supported,
            mmproj_path=req.mmproj_path,
            gpu_layers=req.gpu_layers,
            is_default=req.is_default,
        )
        db.add(new_model)
        db.commit()
        db.refresh(new_model)
        return new_model
    except Exception as e:
        logger.error(f"Error registering model: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}",
        ) from e


@router.get("/status")
def get_supervisor_status():
    return model_supervisor.get_status()


@router.post("/{model_id}/load")
async def load_model(model_id: str, db: Session = Depends(get_db)):
    model = db.get(ModelConfig, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model configuration not found",
        )
    try:
        await model_supervisor.load_model(model)
        return {"status": "success", "message": f"Model {model.display_name} loaded"}
    except Exception as e:
        logger.error(f"Error loading model {model_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


@router.post("/unload")
async def unload_model():
    await model_supervisor.unload_model()
    return {"status": "success", "message": "Model unloaded"}
