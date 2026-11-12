import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from sse_starlette.sse import EventSourceResponse

from app.core.security import verify_local_token
from app.database.engine import get_db
from app.database.models import Agent, ToolExecution
from app.services.agents.agent_runner import agent_runner
from app.services.agents.tools import TOOL_REGISTRY

router = APIRouter(prefix="/agents", tags=["Agents"], dependencies=[Depends(verify_local_token)])


class AgentCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    system_prompt: str
    tools: list[str] = Field(default_factory=list)


class ApprovalDecision(BaseModel):
    decision: str = Field(description="'approve' or 'reject'")


@router.get("/tools")
def list_available_tools():
    return [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
            "requires_approval": t.requires_approval,
        }
        for t in TOOL_REGISTRY.values()
    ]


@router.post("", response_model=Agent)
def create_agent(req: AgentCreate, db: Session = Depends(get_db)):
    for tool_name in req.tools:
        if tool_name not in TOOL_REGISTRY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown tool: '{tool_name}'",
            )

    agent = Agent(
        name=req.name,
        description=req.description,
        system_prompt=req.system_prompt,
        tools_json=json.dumps(req.tools),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("", response_model=list[Agent])
def list_agents(db: Session = Depends(get_db)):
    return db.exec(select(Agent).order_by(Agent.created_at.desc())).all()  # type: ignore


@router.get("/executions", response_model=list[ToolExecution])
def list_tool_executions(db: Session = Depends(get_db)):
    return db.exec(
        select(ToolExecution).order_by(ToolExecution.created_at.desc())  # type: ignore
    ).all()


@router.post("/executions/{execution_id}/decision")
def decide_tool_approval(
    execution_id: str,
    req: ApprovalDecision,
    db: Session = Depends(get_db),
):
    execution = db.get(ToolExecution, execution_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tool execution not found"
        )
    if execution.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Execution is not pending approval (status: {execution.status})",
        )

    if req.decision.lower() == "reject":
        execution.status = "rejected"
        execution.completed_at = datetime.now(UTC)
        db.add(execution)
        db.commit()
        return {"status": "rejected"}

    # Execute approved tool
    execution.status = "approved"
    tool = TOOL_REGISTRY.get(execution.tool_name)
    if not tool:
        execution.status = "failed"
        execution.error_message = f"Tool '{execution.tool_name}' no longer registered"
        db.add(execution)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=execution.error_message,
        )

    try:
        args = json.loads(execution.arguments_json)
        result = tool.handler(**args)
        execution.result_json = json.dumps(result)
        execution.status = "completed"
    except Exception as e:
        execution.status = "failed"
        execution.error_message = str(e)
    finally:
        execution.completed_at = datetime.now(UTC)
        db.add(execution)
        db.commit()

    return {
        "status": execution.status,
        "result": execution.result_json,
        "error": execution.error_message,
    }


class AgentRunRequest(BaseModel):
    prompt: str = Field(min_length=1)
    max_iterations: int = 5


@router.post("/{agent_id}/run")
async def run_autonomous_agent(agent_id: str, req: AgentRunRequest):
    """Executes the autonomous agent tool-calling reasoning loop over SSE."""
    return EventSourceResponse(
        agent_runner.run_agent(
            agent_id=agent_id,
            user_prompt=req.prompt,
            max_iterations=req.max_iterations,
        )
    )
