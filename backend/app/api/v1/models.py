import datetime
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.security import verify_local_token
from app.database.engine import get_db
from app.database.models import AppSetting, ModelConfig
from app.services.models.scanner import model_scanner
from app.supervisors.model_supervisor import model_supervisor

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/models",
    tags=["Models"],
    dependencies=[Depends(verify_local_token)],
)


class DirectoryListRequest(BaseModel):
    directories: list[str]


@router.get("/directories")
def get_model_directories(db: Session = Depends(get_db)):
    """Retrieve saved model scan directories."""
    record = db.get(AppSetting, "model_search_directories")
    if record and record.value:
        try:
            return json.loads(record.value)
        except Exception:
            pass
    # Return default models dir if none configured
    return [str(Settings.MODELS_DIR.resolve())]


@router.post("/directories")
def save_model_directories(req: DirectoryListRequest, db: Session = Depends(get_db)):
    """Save custom model scan directories."""
    record = db.get(AppSetting, "model_search_directories")
    clean_paths = [str(Path(p).resolve()) for p in req.directories if p.strip()]
    json_val = json.dumps(clean_paths)

    if not record:
        record = AppSetting(key="model_search_directories", value=json_val)
    else:
        record.value = json_val
        record.updated_at = datetime.now(datetime.UTC)

    db.add(record)
    db.commit()
    return clean_paths


class ScanRequest(BaseModel):
    paths: list[str] = Field(
        default_factory=list,
        description="List of custom absolute paths to scan for GGUF models.",
    )


class RegisterScannedModelRequest(BaseModel):
    display_name: str
    file_path: str
    mmproj_path: str | None = None
    context_length: int = 4096
    vision_supported: bool = False
    is_default: bool = False


@router.post("/scan")
def scan_local_models(req: ScanRequest):
    """Scans requested paths + default data/models directory for GGUF models."""
    search_paths = list(req.paths)
    default_path = str(Settings.MODELS_DIR.resolve())
    if default_path not in search_paths:
        search_paths.append(default_path)

    models_found = model_scanner.scan_directories(search_paths)
    return {
        "scanned_paths": search_paths,
        "total_found": len(models_found),
        "models": models_found,
    }


@router.post("/register-scanned", response_model=ModelConfig)
def register_scanned_model(
    req: RegisterScannedModelRequest,
    db: Session = Depends(get_db),
):
    """Registers a scanned model into SQLite configuration."""
    model_path = Path(req.file_path)
    if not model_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")

    # Check if already registered
    existing = db.exec(select(ModelConfig).where(ModelConfig.file_path == req.file_path)).first()
    if existing:
        existing.context_length = max(req.context_length, 4096)
        if req.mmproj_path:
            existing.mmproj_path = req.mmproj_path
            existing.vision_supported = True
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing


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
