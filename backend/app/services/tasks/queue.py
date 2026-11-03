import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.database.engine import engine
from app.database.models import Task

logger = logging.getLogger(__name__)

# Registry mapping task_type string to async handler function
TaskHandler = Callable[[Task, Session], Coroutine[Any, Any, dict[str, Any]]]
TASK_HANDLERS: dict[str, TaskHandler] = {}


def register_task_handler(task_type: str):
    """Decorator to register a function as a handler for a specific task type."""

    def decorator(fn: TaskHandler):
        TASK_HANDLERS[task_type] = fn
        return fn

    return decorator


class TaskQueue:
    def __init__(self):
        self._running = False
        self._worker_task: asyncio.Task | None = None

    def start_worker(self) -> None:
        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())
        logger.info("Background task queue worker started.")

    async def stop_worker(self) -> None:
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Background task queue worker stopped.")

    def submit_task(self, task_type: str, parameters: dict[str, Any]) -> Task:
        """Enqueue a new task into SQLite."""
        with Session(engine) as db:
            task = Task(
                task_type=task_type,
                status="queued",
                parameters=json.dumps(parameters),
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            return task

    async def _process_queue(self) -> None:
        while self._running:
            try:
                await self._execute_next_job()
            except Exception as e:
                logger.error(f"Error in task processing loop: {e}", exc_info=True)
            await asyncio.sleep(settings.TASK_WORKER_POLL_INTERVAL_SECONDS)

    async def _execute_next_job(self) -> None:
        task_id = None
        task_type = None

        with Session(engine) as db:
            # Fetch oldest queued task
            stmt = (
                select(Task)
                .where(Task.status == "queued")
                .order_by(Task.created_at.asc())  # type: ignore
                .limit(1)
            )
            task = db.exec(stmt).first()
            if not task:
                return

            task.status = "running"
            task.updated_at = datetime.now(UTC)
            db.add(task)
            db.commit()
            task_id = task.id
            task_type = task.task_type

        handler = TASK_HANDLERS.get(task_type)
        if not handler:
            self._mark_task_failed(task_id, f"No handler registered for task type: '{task_type}'")
            return

        with Session(engine) as db:
            current_task = db.get(Task, task_id)
            if not current_task:
                return
            try:
                result_data = await handler(current_task, db)
                current_task.status = "completed"
                current_task.progress_percent = 100
                current_task.result = json.dumps(result_data)
                current_task.updated_at = datetime.now(UTC)
                db.add(current_task)
                db.commit()
            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}", exc_info=True)
                self._mark_task_failed(task_id, str(e))

    def _mark_task_failed(self, task_id: str, error_message: str) -> None:
        with Session(engine) as db:
            t = db.get(Task, task_id)
            if t:
                t.status = "failed"
                t.error_message = error_message
                t.updated_at = datetime.now(UTC)
                db.add(t)
                db.commit()


task_queue = TaskQueue()
