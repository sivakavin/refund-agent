from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Any

from docx import Document
from fastembed import TextEmbedding
from pypdf import PdfReader
from supabase import Client

logger = logging.getLogger(__name__)
TABLE_NAME = "refund_policy_chunks"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".markdown"}


class PolicyRagService:
    """Downloads private policy files from Supabase Storage and searches their indexed chunks."""

    def __init__(
        self,
        client: Client,
        bucket: str = "refund-policies",
        top_k: int = 4,
        min_similarity: float = 0.25,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ):
        self.client = client
        self.bucket = bucket
        self.top_k = top_k
        self.min_similarity = min_similarity
        self.chunk_size = chunk_size
        self.chunk_overlap = min(chunk_overlap, max(0, chunk_size - 1))
        self._embedding_model: TextEmbedding | None = None

    def _model(self) -> TextEmbedding:
        if self._embedding_model is None:
            self._embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL)
        return self._embedding_model

    def _list_files(self, prefix: str = "", depth: int = 0) -> list[dict[str, Any]]:
        if depth > 8:
            logger.warning("Skipping deeply nested policy folder: %s", prefix)
            return []
        storage = self.client.storage.from_(self.bucket)
        entries = storage.list(prefix)
        files: list[dict[str, Any]] = []
        for entry in entries or []:
            name = entry.get("name")
            if not name or name == ".emptyFolderPlaceholder":
                continue
            path = f"{prefix}/{name}".strip("/")
            if entry.get("id") is None and entry.get("metadata") is None:
                files.extend(self._list_files(path, depth + 1))
            else:
                if Path(name).suffix.lower() in SUPPORTED_SUFFIXES:
                    files.append({**entry, "path": path})
                else:
                    logger.info("Skipping unsupported policy file: %s", path)
        return files

    @staticmethod
    def _extract_text(file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            reader = PdfReader(str(file_path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        if suffix == ".docx":
            document = Document(str(file_path))
            return "\n".join(paragraph.text for paragraph in document.paragraphs)
        return file_path.read_text(encoding="utf-8", errors="replace")

    def _chunks(self, text: str) -> list[str]:
        text = re.sub(r"\x00", " ", text).strip()
        if not text:
            return []
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + self.chunk_size // 2, end)
                if boundary > start:
                    end = boundary
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start = max(start + 1, end - self.chunk_overlap)
        return chunks

    @staticmethod
    def _version(file_info: dict[str, Any]) -> str:
        return str(
            file_info.get("updated_at")
            or file_info.get("created_at")
            or (file_info.get("metadata") or {}).get("eTag")
            or ""
        )

    def _is_current(self, path: str, version: str) -> bool:
        result = (
            self.client.table(TABLE_NAME)
            .select("source_version")
            .eq("storage_path", path)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return bool(rows) and rows[0].get("source_version", "") == version

    def _index_file(self, file_info: dict[str, Any]) -> int:
        path = file_info["path"]
        version = self._version(file_info)
        if self._is_current(path, version):
            return 0

        raw = self.client.storage.from_(self.bucket).download(path)
        with tempfile.TemporaryDirectory(prefix="refund-policy-") as temp_dir:
            local_path = Path(temp_dir) / Path(path).name
            local_path.write_bytes(raw)
            chunks = self._chunks(self._extract_text(local_path))

        if not chunks:
            self.client.table(TABLE_NAME).delete().eq("storage_path", path).execute()
            logger.warning("Policy document has no extractable text: %s", path)
            return 0

        vectors = list(self._model().embed(chunks))
        rows = [
            {
                "storage_path": path,
                "document_name": Path(path).name,
                "source_version": version,
                "chunk_index": index,
                "content": chunk,
                "embedding": vector.tolist() if hasattr(vector, "tolist") else list(vector),
            }
            for index, (chunk, vector) in enumerate(zip(chunks, vectors))
        ]
        self.client.table(TABLE_NAME).delete().eq("storage_path", path).execute()
        self.client.table(TABLE_NAME).upsert(
            rows,
            on_conflict="storage_path,chunk_index",
        ).execute()
        return len(rows)

    def refresh_index(self) -> int:
        """Index or refresh supported files in the configured private Storage bucket."""
        try:
            files = self._list_files()
            current_paths = {file_info["path"] for file_info in files}
            indexed_chunks = 0
            for file_info in files:
                try:
                    indexed_chunks += self._index_file(file_info)
                except Exception:
                    logger.exception("Could not index policy document %s", file_info["path"])

            indexed = (
                self.client.table(TABLE_NAME)
                .select("storage_path")
                .execute()
                .data
                or []
            )
            for path in {row.get("storage_path") for row in indexed} - current_paths:
                if path:
                    self.client.table(TABLE_NAME).delete().eq("storage_path", path).execute()

            logger.info(
                "Policy index ready: %s documents found, %s chunks indexed",
                len(files),
                indexed_chunks,
            )
            return indexed_chunks
        except Exception:
            logger.exception(
                "Policy indexing is unavailable. Check the %r Storage bucket and migration.",
                self.bucket,
            )
            return 0

    def search(self, question: str) -> dict[str, Any]:
        """Return relevant policy passages for the chat model to use as grounded context."""
        if not question.strip():
            return {"found": False, "message": "Enter a policy question to search."}
        try:
            query_vector = next(self._model().query_embed(question))
            vector = query_vector.tolist() if hasattr(query_vector, "tolist") else list(query_vector)
            result = self.client.rpc(
                "match_refund_policy",
                {"query_embedding": vector, "match_count": self.top_k},
            ).execute()
            passages = [
                {
                    "document": row["document_name"],
                    "storage_path": row["storage_path"],
                    "similarity": round(float(row["similarity"]), 3),
                    "text": row["content"],
                }
                for row in (result.data or [])
                if float(row.get("similarity", 0)) >= self.min_similarity
            ]
            if not passages:
                return {
                    "found": False,
                    "message": "No relevant policy passages were found in the indexed Supabase documents.",
                }
            return {"found": True, "passages": passages}
        except Exception:
            logger.exception("Policy search failed")
            return {
                "found": False,
                "message": "Policy search is temporarily unavailable. Do not guess policy details.",
            }
