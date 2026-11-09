import json
import logging
from pathlib import Path
from typing import Any

import httpx
from sqlmodel import Session

from app.database.models import Attachment, Task
from app.services.documents.extractor import document_extractor
from app.services.tasks.queue import register_task_handler
from app.supervisors.model_supervisor import model_supervisor

logger = logging.getLogger(__name__)


@register_task_handler("pdf_extraction")
async def handle_pdf_extraction(task: Task, db: Session) -> dict[str, Any]:
    params = json.loads(task.parameters)
    attachment_id = params["attachment_id"]
    max_tokens = params.get("max_tokens", 4000)

    attachment = db.get(Attachment, attachment_id)
    if not attachment:
        raise FileNotFoundError(f"Attachment '{attachment_id}' not found")

    file_path = Path(attachment.file_path)
    extraction = document_extractor.extract_pdf_with_budget(
        file_path=file_path,
        max_token_budget=max_tokens,
    )
    return {
        "text_content": extraction["content"],
        "extracted_pages": extraction["extracted_pages"],
        "total_pages": extraction["total_pages"],
    }


@register_task_handler("llm_summarize")
async def handle_llm_summarize(task: Task, db: Session) -> dict[str, Any]:
    params = json.loads(task.parameters)
    text_to_summarize = params["text_content"]

    if not model_supervisor.active_model:
        raise RuntimeError("No LLM loaded in Model Supervisor for summarization")

    prompt = (
        "You are an executive assistant. Please provide a clear, concise, and professional "
        "summary of the following document content suitable for spoken audio:\n\n"
        f"{text_to_summarize[:8000]}"
    )

    url = f"{model_supervisor.base_url}/v1/chat/completions"
    payload = {
        "messages": [
            {"role": "system", "content": "You are a concise executive brief writer."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 512,
        "stream": False,
    }

    timeout_config = httpx.Timeout(connect=15.0, read=None, write=30.0, pool=None)
    async with httpx.AsyncClient(timeout=timeout_config) as client:
        res = await client.post(url, json=payload)
        if res.status_code != 200:
            raise RuntimeError(f"LLM summarization failed: {res.text}")

        res_data = res.json()
        summary = res_data["choices"][0]["message"]["content"]
        return {"summary": summary}
