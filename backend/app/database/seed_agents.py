import json
import logging

from sqlmodel import Session, select

from app.database.engine import engine
from app.database.models import Agent

logger = logging.getLogger(__name__)

SCENARIO_AGENTS = [
    {
        "name": "Code Reviewer & Benchmark Agent",
        "description": "Audits Python code, constructs automated unit tests, and measures execution performance inside the sandbox.",
        "system_prompt": (
            "You are a Senior Security & Performance Code Reviewer. When given Python code:\n"
            "1. Inspect for bugs, security vulnerabilities, and boundary errors.\n"
            "2. Use the 'execute_python' tool to run the code inside the isolated sandbox to test execution and measure performance.\n"
            "3. Format your final report with:\n"
            "   - ## Code Defects & Vulnerabilities\n"
            "   - ## Sandbox Execution Results (Stdout/Stderr)\n"
            "   - ## Optimized Production Replacement\n"
            "Always invoke the 'execute_python' tool to verify code before rendering your conclusion."
        ),
        "tools_json": json.dumps(["execute_python"]),
    },
    {
        "name": "Research Analyst Agent",
        "description": "Queries local LanceDB knowledge bases, synthesizes comparative insights, and produces academic reports with citations.",
        "system_prompt": (
            "You are a Principal Research Analyst. When asked a research question:\n"
            "1. Use the 'search_knowledge_base' tool to query indexed documentation for relevant source material.\n"
            "2. Read and synthesize the extracted context.\n"
            "3. Produce a structured research brief formatted with:\n"
            "   - ## Executive Summary\n"
            "   - ## Key Findings & Technical Evidence\n"
            "   - ## Source Citations & References\n"
            "Always ground your reasoning in verifiable context retrieved from the knowledge base."
        ),
        "tools_json": json.dumps(["search_knowledge_base"]),
    },
]


def seed_scenario_agents_if_empty():
    with Session(engine) as db:
        for agent_data in SCENARIO_AGENTS:
            existing = db.exec(select(Agent).where(Agent.name == agent_data["name"])).first()
            if not existing:
                db.add(Agent(**agent_data))
        db.commit()
        logger.info("Autonomous Agent Scenarios verified.")
