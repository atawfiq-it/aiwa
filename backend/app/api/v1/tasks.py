from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.security import verify_local_token
from app.database.engine import get_db
from app.database.models import Task

router = APIRouter(prefix="/tasks", tags=["Tasks"], dependencies=[Depends(verify_local_token)])


class TaskStatusResponse(BaseModel):
    id: str
    task_type: str
    status: str
    progress_percent: int
    result: str | None
    error_message: str | None


@router.get("", response_model=list[Task])
def list_tasks(db: Session = Depends(get_db)):
    return db.exec(select(Task).order_by(Task.created_at.desc())).all()  # type: ignore


@router.get("/{task_id}", response_model=Task)
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.post("/{task_id}/cancel")
def cancel_task(task_id: str, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel task in '{task.status}' state",
        )
    task.status = "cancelled"
    db.add(task)
    db.commit()
    return {"status": "success", "message": "Task cancelled"}
