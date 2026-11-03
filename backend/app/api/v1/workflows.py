from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, select

from app.core.security import verify_local_token
from app.database.engine import get_db
from app.database.models import Workflow, WorkflowRun
from app.services.tasks.workflow_engine import workflow_engine

router = APIRouter(
    prefix="/workflows",
    tags=["Workflows"],
    dependencies=[Depends(verify_local_token)],
)


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str
    steps: list[dict[str, Any]]


class WorkflowRunTrigger(BaseModel):
    input_data: dict[str, Any]


class WorkflowRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_id: str
    status: str
    current_step_index: int
    total_steps: int
    current_task_id: str | None = None
    input_data_json: str
    context_data_json: str
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


@router.get("", response_model=list[Workflow])
def list_workflows(db: Session = Depends(get_db)):
    return db.exec(
        select(Workflow).order_by(Workflow.created_at.desc())  # type: ignore
    ).all()


@router.post("", response_model=Workflow)
def create_workflow(req: WorkflowCreate, db: Session = Depends(get_db)):
    import json

    wf = Workflow(
        name=req.name,
        description=req.description,
        steps_json=json.dumps(req.steps),
    )
    db.add(wf)
    db.commit()
    db.refresh(wf)
    return wf


@router.post("/{workflow_id}/run", response_model=WorkflowRunResponse)
def run_workflow(
    workflow_id: str,
    req: WorkflowRunTrigger,
    db: Session = Depends(get_db),
):
    try:
        return workflow_engine.trigger_workflow(
            workflow_id=workflow_id,
            input_data=req.input_data,
            db=db,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
def get_workflow_run(run_id: str, db: Session = Depends(get_db)):
    workflow_engine.progress_workflow_if_ready(run_id)
    run = db.get(WorkflowRun, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow run not found",
        )
    return run
