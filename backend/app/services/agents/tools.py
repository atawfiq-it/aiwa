import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from app.services.agents.sandbox import python_sandbox
from app.services.embeddings.rag_service import rag_service


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
    requires_approval: bool = False
    handler: Callable[..., Any] = Field(exclude=True)


TOOL_REGISTRY: dict[str, ToolDefinition] = {}


def register_tool(
    name: str,
    description: str,
    parameters: dict[str, Any],
    requires_approval: bool = False,
):
    def decorator(fn: Callable[..., Any]):
        TOOL_REGISTRY[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            requires_approval=requires_approval,
            handler=fn,
        )
        return fn

    return decorator


# Tool 1: Sandboxed Python Execution (Requires User Approval)
@register_tool(
    name="execute_python",
    description=(
        "Run Python code in a secure isolated sandbox to perform computations "
        "or data transformations."
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python source code to execute.",
            }
        },
        "required": ["code"],
    },
    requires_approval=True,  # Interactive Human-In-The-Loop
)
def tool_execute_python(code: str) -> str:
    res = python_sandbox.execute(code)
    return json.dumps(res)


# Tool 2: Knowledge Base Search (Safe / Pre-approved)
@register_tool(
    name="search_knowledge_base",
    description="Search indexed documents and knowledge bases for factual context.",
    parameters={
        "type": "object",
        "properties": {
            "kb_id": {"type": "string", "description": "Target knowledge base ID."},
            "query": {"type": "string", "description": "Semantic query string."},
        },
        "required": ["kb_id", "query"],
    },
    requires_approval=False,
)
def tool_search_kb(kb_id: str, query: str) -> str:
    results = rag_service.search_similar(kb_id=kb_id, query=query, limit=3)
    return json.dumps(results)


def get_openai_tools_schema(allowed_names: list[str]) -> list[dict[str, Any]]:
    """Converts registered tools into OpenAI-compatible schema for llama.cpp."""
    schemas = []
    for name in allowed_names:
        tool = TOOL_REGISTRY.get(name)
        if tool:
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
    return schemas
