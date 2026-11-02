from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.security import verify_local_token
from app.database.engine import get_db
from app.database.models import ModelConfig
from app.supervisors.model_supervisor import model_supervisor

router = APIRouter(prefix="/models", tags=["Models"], dependencies=[Depends(verify_local_token)])


@router.get("", response_model=list[ModelConfig])
def list_models(db: Session = Depends(get_db)):
    return db.exec(select(ModelConfig)).all()


@router.post("", response_model=ModelConfig)
def register_model(config: ModelConfig, db: Session = Depends(get_db)):
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


@router.post("/unload")
async def unload_model():
    await model_supervisor.unload_model()
    return {"status": "success", "message": "Model unloaded"}
