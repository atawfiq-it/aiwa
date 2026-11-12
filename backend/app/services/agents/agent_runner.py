import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from sqlmodel import Session
from sse_starlette.sse import ServerSentEvent

from app.database.engine import engine
from app.database.models import Agent
from app.services.agents.tools import TOOL_REGISTRY, get_openai_tools_schema
from app.supervisors.model_supervisor import ModelState, model_supervisor

logger = logging.getLogger(__name__)


class AgentRunner:
    async def run_agent(
        self,
        agent_id: str,
        user_prompt: str,
        max_iterations: int = 5,
    ) -> AsyncGenerator[ServerSentEvent, None]:
        """Runs the autonomous agent tool-calling loop until completion."""
        if model_supervisor.state != ModelState.READY or not model_supervisor.active_model:
            yield ServerSentEvent(
                event="error",
                data=json.dumps({"error": "No LLM loaded in Model Supervisor."}),
            )
            return

        with Session(engine) as db:
            agent = db.get(Agent, agent_id)
            if not agent:
                yield ServerSentEvent(event="error", data=json.dumps({"error": "Agent not found."}))
                return

        allowed_tools = json.loads(agent.tools_json)
        tools_schema = get_openai_tools_schema(allowed_tools)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": agent.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        yield ServerSentEvent(
            event="agent_started",
            data=json.dumps({"agent_name": agent.name, "tools": allowed_tools}),
        )

        async with httpx.AsyncClient(timeout=180.0) as client:
            for iteration in range(max_iterations):
                logger.info(f"Agent '{agent.name}' reasoning turn {iteration + 1}...")

                payload = {
                    "messages": messages,
                    "tools": tools_schema if tools_schema else None,
                    "tool_choice": "auto" if tools_schema else None,
                    "temperature": 0.2,
                    "stream": False,
                }

                res = await client.post(
                    f"{model_supervisor.base_url}/v1/chat/completions",
                    json=payload,
                )
                if res.status_code != 200:
                    yield ServerSentEvent(
                        event="error",
                        data=json.dumps({"error": f"LLM error: {res.text}"}),
                    )
                    return

                res_json = res.json()
                choice = res_json["choices"][0]["message"]
                content = choice.get("content", "") or ""
                tool_calls = choice.get("tool_calls", [])

                # If the agent decided to call a tool
                if tool_calls:
                    for tc in tool_calls:
                        func_name = tc["function"]["name"]
                        raw_args = tc["function"]["arguments"]

                        try:
                            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        except json.JSONDecodeError:
                            args = {"code": raw_args}

                        yield ServerSentEvent(
                            event="tool_call_started",
                            data=json.dumps({"tool": func_name, "arguments": args}),
                        )

                        # Execute tool
                        tool_def = TOOL_REGISTRY.get(func_name)
                        if not tool_def:
                            tool_result = f"Error: Tool '{func_name}' not registered."
                        else:
                            try:
                                tool_result = tool_def.handler(**args)
                            except Exception as e:
                                tool_result = f"Tool execution failed: {e}"

                        yield ServerSentEvent(
                            event="tool_call_completed",
                            data=json.dumps({"tool": func_name, "output": tool_result}),
                        )

                        # Feed output back into conversation history
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
                    # Final synthesis reached
                    yield ServerSentEvent(
                        event="agent_completed",
                        data=json.dumps({"final_answer": content}),
                    )
                    return

            yield ServerSentEvent(
                event="error",
                data=json.dumps({"error": "Reached maximum reasoning limit."}),
            )


agent_runner = AgentRunner()
