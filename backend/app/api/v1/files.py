import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlmodel import Session

from app.core.config import settings
from app.core.security import verify_local_token
from app.database.engine import get_db
from app.database.models import Attachment
from app.services.documents.extractor import document_extractor

router = APIRouter(prefix="/files", tags=["Files"], dependencies=[Depends(verify_local_token)])


@router.post("/upload", response_model=Attachment)
async def upload_file(
    file: UploadFile,
    db: Session = Depends(get_db),
):
    safe_filename = Path(file.filename).name  # Prevent directory traversal attacks
    file_id = str(uuid.uuid4())
    stored_name = f"{file_id}_{safe_filename}"
    destination_path = settings.UPLOADS_DIR / stored_name

    # Stream write directly to disk to minimize memory footprint
    try:
        with open(destination_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store file: {e}",
        ) from e
    finally:
        await file.close()

    attachment = Attachment(
        id=file_id,
        file_name=safe_filename,
        file_path=str(destination_path),
        mime_type=file.content_type or "application/octet-stream",
        file_size_bytes=destination_path.stat().st_size,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


@router.post("/{attachment_id}/extract")
def extract_document(
    attachment_id: str,
    max_tokens: int = 3000,
    db: Session = Depends(get_db),
):
    attachment = db.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    file_path = Path(attachment.file_path)
    if not file_path.suffix.lower() == ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Currently only PDF extraction is supported",
        )

    try:
        return document_extractor.extract_pdf_with_budget(
            file_path=file_path,
            max_token_budget=max_tokens,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
