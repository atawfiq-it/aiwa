import logging
import re
from typing import Any

import lancedb
from fastembed import TextEmbedding

from app.core.config import settings

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self):
        self.vector_dir = settings.DATA_DIR / "vector_store"
        self.vector_dir.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(self.vector_dir))
        self._embedder: TextEmbedding | None = None

    def _get_embedder(self) -> TextEmbedding:
        """Loads FastEmbed model using CPU/ONNX Runtime."""
        if self._embedder is None:
            logger.info("Initializing FastEmbed ONNX Runtime (CPU)...")
            self._embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        return self._embedder

    def chunk_markdown(self, text: str, max_chunk_size: int = 1000) -> list[str]:
        """Markdown-aware semantic chunking along headers and paragraph blocks."""
        # Split on headers (# Header, ## Subheader) or double line breaks
        sections = re.split(r"(?=(?:\n|^)#{1,4}\s+)", text)
        chunks = []

        for section in sections:
            section = section.strip()
            if not section:
                continue

            if len(section) <= max_chunk_size:
                chunks.append(section)
            else:
                # Sub-split long sections by paragraphs
                paragraphs = section.split("\n\n")
                current_chunk = []
                current_len = 0

                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue
                    if current_len + len(para) > max_chunk_size and current_chunk:
                        chunks.append("\n\n".join(current_chunk))
                        current_chunk = [para]
                        current_len = len(para)
                    else:
                        current_chunk.append(para)
                        current_len += len(para)

                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))

        return chunks

    def index_document(
        self,
        kb_id: str,
        doc_id: str,
        file_name: str,
        markdown_text: str,
    ) -> int:
        chunks = self.chunk_markdown(markdown_text)
        if not chunks:
            return 0

        embedder = self._get_embedder()
        embeddings = list(embedder.embed(chunks))

        records = [
            {
                "id": f"{doc_id}_{i}",
                "doc_id": doc_id,
                "file_name": file_name,
                "text": chunk,
                "vector": embeddings[i].tolist(),
            }
            for i, chunk in enumerate(chunks)
        ]

        table_name = f"kb_{kb_id.replace('-', '_')}"
        if table_name in self.db.table_names():
            table = self.db.open_table(table_name)
            table.add(records)
        else:
            self.db.create_table(table_name, data=records)

        return len(records)

    def search_similar(
        self,
        kb_id: str,
        query: str,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        table_name = f"kb_{kb_id.replace('-', '_')}"
        if table_name not in self.db.table_names():
            return []

        embedder = self._get_embedder()
        query_vector = list(embedder.embed([query]))[0].tolist()

        table = self.db.open_table(table_name)
        results = table.search(query_vector).limit(limit).to_list()

        return [
            {
                "text": row["text"],
                "file_name": row["file_name"],
                "doc_id": row["doc_id"],
                "score": float(row.get("_distance", 0.0)),
            }
            for row in results
        ]


rag_service = RAGService()
