from __future__ import annotations

from collections.abc import Iterable

from app.application.services.chunking import SemanticChunker
from app.domain.entities import SourceDocument
from app.domain.ports import VectorStore


class IngestDocuments:
    def __init__(self, chunker: SemanticChunker, vector_store: VectorStore) -> None:
        self._chunker = chunker
        self._vectors = vector_store

    def execute(self, documents: Iterable[SourceDocument], rebuild: bool = False) -> dict[str, int]:
        if rebuild:
            self._vectors.reset()
        unique = {document.document_id: document for document in documents if document.content}
        chunks = [chunk for document in unique.values() for chunk in self._chunker.split(document)]
        stored = self._vectors.upsert(chunks)
        return {"documents": len(unique), "chunks": stored}
