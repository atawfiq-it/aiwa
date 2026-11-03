from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.security import verify_local_token
from app.database.engine import get_db
from app.database.models import Attachment, DocumentRecord, KnowledgeBase
from app.services.documents.extractor import document_extractor
from app.services.embeddings.rag_service import rag_service

router = APIRouter(
    prefix="/knowledge-bases",
    tags=["Knowledge Bases"],
    dependencies=[Depends(verify_local_token)],
)


class KBCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class IndexDocumentRequest(BaseModel):
    attachment_id: str


class SearchQuery(BaseModel):
    query: str
    limit: int = 4


@router.post("", response_model=KnowledgeBase)
def create_knowledge_base(req: KBCreate, db: Session = Depends(get_db)):
    kb = KnowledgeBase(name=req.name, description=req.description)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


@router.get("", response_model=list[KnowledgeBase])
def list_knowledge_bases(db: Session = Depends(get_db)):
    return db.exec(select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc())).all()  # type: ignore


@router.post("/{kb_id}/documents", response_model=DocumentRecord)
def index_document_into_kb(
    kb_id: str,
    req: IndexDocumentRequest,
    db: Session = Depends(get_db),
):
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )

    attachment = db.get(Attachment, req.attachment_id)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    file_path = Path(attachment.file_path)
    extraction = document_extractor.extract_pdf_with_budget(file_path, max_token_budget=50000)

    doc_record = DocumentRecord(
        knowledge_base_id=kb_id,
        file_name=attachment.file_name,
        file_path=attachment.file_path,
        status="indexing",
    )
    db.add(doc_record)
    db.commit()
    db.refresh(doc_record)

    # Index into LanceDB
    num_chunks = rag_service.index_document(
        kb_id=kb_id,
        doc_id=doc_record.id,
        file_name=attachment.file_name,
        markdown_text=extraction["content"],
    )

    doc_record.num_chunks = num_chunks
    doc_record.status = "indexed"
    kb.updated_at = datetime.now(UTC)
    db.add(doc_record)
    db.add(kb)
    db.commit()
    db.refresh(doc_record)

    return doc_record


@router.post("/{kb_id}/search")
def search_knowledge_base(
    kb_id: str,
    query: SearchQuery,
    db: Session = Depends(get_db),
):
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )

    results = rag_service.search_similar(kb_id=kb_id, query=query.query, limit=query.limit)
    return {"results": results, "count": len(results)}
