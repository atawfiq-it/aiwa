import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session

from app.database.engine import engine
from app.database.models import Workflow, WorkflowRun
from app.services.tasks.queue import task_queue

logger = logging.getLogger(__name__)


class WorkflowEngine:
    def trigger_workflow(
        self,
        workflow_id: str,
        input_data: dict[str, Any],
        db: Session,
    ) -> WorkflowRun:
        workflow = db.get(Workflow, workflow_id)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        steps = json.loads(workflow.steps_json)
        if not steps:
            raise ValueError("Workflow contains no steps")

        run = WorkflowRun(
            workflow_id=workflow.id,
            status="running",
            current_step_index=0,
            total_steps=len(steps),
            input_data_json=json.dumps(input_data),
            context_data_json=json.dumps(input_data),
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Enqueue the first step
        self._enqueue_step(run, steps[0], input_data, db)
        return run

    def _enqueue_step(
        self,
        run: WorkflowRun,
        step_config: dict[str, Any],
        merged_params: dict[str, Any],
        db: Session,
    ) -> None:
        task_type = step_config["task_type"]
        task = task_queue.submit_task(task_type, merged_params)
        run.current_task_id = task.id
        db.add(run)
        db.commit()
        db.refresh(run)

    def progress_workflow_if_ready(self, run_id: str) -> None:
        """Polls active task state and advances to next step on completion."""
        with Session(engine) as db:
            run = db.get(WorkflowRun, run_id)
            if not run or run.status != "running" or not run.current_task_id:
                return

            from app.database.models import Task

            current_task = db.get(Task, run.current_task_id)
            if not current_task:
                return

            if current_task.status == "failed":
                run.status = "failed"
                run.error_message = (
                    f"Step {run.current_step_index + 1} failed: {current_task.error_message}"
                )
                run.completed_at = datetime.now(UTC)
                db.add(run)
                db.commit()
                return

            if current_task.status == "cancelled":
                run.status = "cancelled"
                run.completed_at = datetime.now(UTC)
                db.add(run)
                db.commit()
                return

            if current_task.status == "completed":
                # Merge task result into context
                context = json.loads(run.context_data_json)
                if current_task.result:
                    task_result = json.loads(current_task.result)
                    context.update(task_result)

                run.context_data_json = json.dumps(context)
                next_index = run.current_step_index + 1

                workflow = db.get(Workflow, run.workflow_id)
                steps = json.loads(workflow.steps_json) if workflow else []

                if next_index >= len(steps):
                    # Workflow is finished
                    run.status = "completed"
                    run.current_step_index = next_index
                    run.completed_at = datetime.now(UTC)
                    db.add(run)
                    db.commit()
                    logger.info(f"WorkflowRun {run.id} completed successfully.")
                else:
                    # Advance to next step
                    run.current_step_index = next_index
                    next_step = steps[next_index]
                    db.add(run)
                    db.commit()

                    # Merge previous outputs into next step input parameters
                    step_input = {**context}
                    if "text_to_speech" == next_step["task_type"]:
                        step_input["text"] = context.get("summary", "")

                    self._enqueue_step(run, next_step, step_input, db)


workflow_engine = WorkflowEngine()
