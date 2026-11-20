import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from sqlmodel import Session
from sse_starlette.sse import ServerSentEvent

from app.core.config import settings
from app.database.engine import engine
from app.database.models import Agent
from app.services.agents.tools import TOOL_REGISTRY, get_openai_tools_schema
from app.supervisors.model_supervisor import ModelState, model_supervisor

logger = logging.getLogger(__name__)

# Active human approval events: run_id -> asyncio.Event
PENDING_APPROVALS: dict[str, asyncio.Event] = {}
APPROVAL_DECISIONS: dict[str, dict[str, Any]] = {}


class AgentRunner:
    async def run_agent(
        self,
        agent_id: str,
        user_prompt: str,
        require_human_approval: bool = False,
        max_iterations: int = 5,
    ) -> AsyncGenerator[ServerSentEvent, None]:
        """Runs the autonomous agent reasoning loop emitting structured DAG nodes over SSE."""
        if model_supervisor.state != ModelState.READY or not model_supervisor.active_model:
            yield ServerSentEvent(
                event="dag_node",
                data=json.dumps(
                    {
                        "node_id": "step_wakeup",
                        "node_type": "planning",
                        "title": "⚡ Loading LLM On-Demand",
                        "content": "Reclaiming memory from previous processes and loading LLM...",
                        "status": "running",
                    }
                ),
            )
            try:
                await model_supervisor.ensure_loaded_on_demand()
            except Exception as e:
                yield ServerSentEvent(event="error", data=json.dumps({"error": str(e)}))
                return

        run_id = uuid.uuid4().hex[:8]
        workspace_dir = settings.DATA_DIR / "workspaces" / run_id
        workspace_dir.mkdir(parents=True, exist_ok=True)

        with Session(engine) as db:
            agent = db.get(Agent, agent_id)
            if not agent:
                yield ServerSentEvent(
                    event="error",
                    data=json.dumps({"error": "Agent configuration not found."}),
                )
                return

        allowed_tools = json.loads(agent.tools_json) if agent.tools_json else []
        tools_schema = get_openai_tools_schema(allowed_tools)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": agent.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 1. Emit Agent Initialized Event
        yield ServerSentEvent(
            event="agent_started",
            data=json.dumps(
                {
                    "run_id": run_id,
                    "agent_name": agent.name,
                    "tools": allowed_tools,
                    "workspace_path": str(workspace_dir.resolve()),
                }
            ),
        )

        # 2. Emit Goal Node
        yield ServerSentEvent(
            event="dag_node",
            data=json.dumps(
                {
                    "node_id": "step_goal",
                    "node_type": "goal",
                    "title": "🎯 Task Goal",
                    "content": user_prompt,
                    "status": "completed",
                }
            ),
        )

        # 3. Emit Planning Strategy Node
        yield ServerSentEvent(
            event="dag_node",
            data=json.dumps(
                {
                    "node_id": "step_plan",
                    "node_type": "planning",
                    "title": f"🧠 Strategy: {agent.name}",
                    "content": (
                        f"Initializing reasoning loop with bound tools: "
                        f"{', '.join(allowed_tools) if allowed_tools else 'None'}. "
                        "Evaluating constraints and test boundaries..."
                    ),
                    "status": "completed",
                }
            ),
        )

        timeout_config = httpx.Timeout(connect=15.0, read=180.0, write=30.0, pool=None)

        async with httpx.AsyncClient(timeout=timeout_config) as client:
            for iteration in range(max_iterations):
                step_id = f"step_{iteration + 1}"
                t0 = time.time()

                payload = {
                    "messages": messages,
                    "tools": tools_schema if tools_schema else None,
                    "tool_choice": "auto" if tools_schema else None,
                    "temperature": 0.2,
                    "stream": False,
                }

                try:
                    res = await client.post(
                        f"{model_supervisor.base_url}/v1/chat/completions",
                        json=payload,
                    )
                except Exception as e:
                    yield ServerSentEvent(
                        event="error",
                        data=json.dumps({"error": f"Failed connecting to model: {e}"}),
                    )
                    return

                if res.status_code != 200:
                    yield ServerSentEvent(
                        event="error",
                        data=json.dumps(
                            {"error": f"LLM error (HTTP {res.status_code}): {res.text}"}
                        ),
                    )
                    return

                res_json = res.json()
                choice = res_json["choices"][0]["message"]
                content = choice.get("content", "") or ""
                tool_calls = choice.get("tool_calls", [])

                # If the agent decided to call one or more tools
                if tool_calls:
                    for tc in tool_calls:
                        func_name = tc["function"]["name"]
                        raw_args = tc["function"]["arguments"]

                        try:
                            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        except json.JSONDecodeError:
                            args = {"code": raw_args}

                        # Emit Tool Call Action Node
                        yield ServerSentEvent(
                            event="dag_node",
                            data=json.dumps(
                                {
                                    "node_id": f"{step_id}_tool",
                                    "node_type": "tool_call",
                                    "title": f"⚡ Action: {func_name}",
                                    "tool_name": func_name,
                                    "arguments": args,
                                    "status": "running",
                                }
                            ),
                        )

                        # Check Human-in-the-Loop Breakpoint
                        if require_human_approval:
                            yield ServerSentEvent(
                                event="approval_required",
                                data=json.dumps(
                                    {
                                        "run_id": run_id,
                                        "tool_name": func_name,
                                        "arguments": args,
                                    }
                                ),
                            )

                            # Wait for user decision
                            event = asyncio.Event()
                            PENDING_APPROVALS[run_id] = event
                            try:
                                await asyncio.wait_for(event.wait(), timeout=120.0)
                            except TimeoutError:
                                yield ServerSentEvent(
                                    event="error",
                                    data=json.dumps(
                                        {"error": "Human approval timed out after 120s."}
                                    ),
                                )
                                return
                            finally:
                                PENDING_APPROVALS.pop(run_id, None)

                            decision = APPROVAL_DECISIONS.pop(run_id, {"action": "approve"})
                            if decision.get("action") == "reject":
                                tool_result = "Execution rejected by user."
                            else:
                                if "modified_args" in decision:
                                    args = decision["modified_args"]

                        # Execute registered tool
                        tool_def = TOOL_REGISTRY.get(func_name)
                        if not tool_def:
                            tool_result = f"Error: Tool '{func_name}' is not registered."
                        else:
                            try:
                                tool_result = tool_def.handler(**args)
                            except Exception as e:
                                tool_result = f"Execution error: {e}"

                        duration_ms = round((time.time() - t0) * 1000)

                        # Emit Observation Node
                        yield ServerSentEvent(
                            event="dag_node",
                            data=json.dumps(
                                {
                                    "node_id": f"{step_id}_obs",
                                    "node_type": "observation",
                                    "title": f"📦 Observation ({func_name})",
                                    "output": tool_result,
                                    "duration_ms": duration_ms,
                                    "status": "completed",
                                }
                            ),
                        )

                        # Append results to message context
                        messages.append(
                            {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [tc],
                            }
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.get("id", "call_default"),
                                "name": func_name,
                                "content": str(tool_result),
                            }
                        )
                else:
                    # Final synthesis reached: Emit solely via agent_completed
                    # Final synthesis reached: Persist completed run to SQLite
                    from app.database.models import AgentRunRecord

                    task_title = (
                        user_prompt.strip().split("\n")[0][:40] + "..."
                        if len(user_prompt.strip().split("\n")[0]) > 40
                        else user_prompt.strip().split("\n")[0]
                    )

                    with Session(engine) as db:
                        saved_record = AgentRunRecord(
                            id=run_id,
                            title=task_title or f"Task by {agent.name}",
                            agent_id=agent.id,
                            agent_name=agent.name,
                            prompt=user_prompt,
                            final_report=content,
                        )
                        db.add(saved_record)
                        db.commit()

                    yield ServerSentEvent(
                        event="agent_completed",
                        data=json.dumps(
                            {
                                "final_answer": content,
                                "run_id": run_id,
                                "title": task_title,
                            }
                        ),
                    )
                    return

            yield ServerSentEvent(
                event="error",
                data=json.dumps({"error": "Reached maximum reasoning turn limit."}),
            )


agent_runner = AgentRunner()
