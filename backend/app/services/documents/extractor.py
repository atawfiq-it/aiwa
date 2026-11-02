import logging
from pathlib import Path
from typing import Any

import pymupdf
import pymupdf4llm

logger = logging.getLogger(__name__)


class DocumentExtractor:
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token count estimation (~4 characters per token)."""
        return max(1, len(text) // 4)

    def extract_pdf_with_budget(
        self,
        file_path: Path,
        max_token_budget: int = 3000,
    ) -> dict[str, Any]:
        """Extracts text as Markdown page by page until the token budget is reached."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            doc = pymupdf.open(str(file_path))
        except Exception as e:
            raise ValueError(f"Corrupted or invalid PDF file: {e}") from e

        total_pages = len(doc)
        extracted_pages = []
        accumulated_text = []
        total_tokens = 0
        is_truncated = False

        for page_num in range(total_pages):
            try:
                page_md = pymupdf4llm.to_markdown(doc, pages=[page_num])
            except Exception as e:
                logger.warning(f"Failed extracting page {page_num + 1}: {e}")
                continue

            page_tokens = self.estimate_tokens(page_md)

            if total_tokens + page_tokens > max_token_budget and page_num > 0:
                is_truncated = True
                break

            accumulated_text.append(f"--- Page {page_num + 1} ---\n{page_md}")
            extracted_pages.append(page_num + 1)
            total_tokens += page_tokens

        doc.close()

        final_content = "\n\n".join(accumulated_text)
        if is_truncated:
            truncation_notice = (
                f"\n\n> **[Notice]**: Context window limit reached. "
                f"Extracted {len(extracted_pages)} of {total_pages} pages."
            )
            final_content += truncation_notice

        return {
            "content": final_content,
            "total_pages": total_pages,
            "extracted_pages": len(extracted_pages),
            "estimated_tokens": total_tokens,
            "is_truncated": is_truncated,
        }


document_extractor = DocumentExtractor()
