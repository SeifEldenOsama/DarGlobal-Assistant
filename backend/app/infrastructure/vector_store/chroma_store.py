from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.domain.entities import DocumentChunk, RetrievedChunk
from app.domain.ports import Embedder


class ChromaVectorStore:
    def __init__(
        self, directory: Path, collection_name: str, embedder: Embedder,
    ) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        # Disable optional anonymized telemetry for self-hosted deployments.
        self._client = chromadb.PersistentClient(
            path=str(directory), settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._name = collection_name
        self._collection = self._client.get_or_create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})
        self._embedder = embedder

    def upsert(self, chunks: Sequence[DocumentChunk]) -> int:
        if not chunks:
            return 0
        for batch in _batches(chunks, 100):
            self._collection.upsert(
                ids=[chunk.chunk_id for chunk in batch],
                documents=[chunk.text for chunk in batch],
                embeddings=self._embedder.embed([chunk.text for chunk in batch]),
                metadatas=[dict(chunk.metadata, chunk_id=chunk.chunk_id, ordinal=chunk.ordinal) for chunk in batch],
            )
        return len(chunks)

    def query(self, question: str, limit: int, minimum_score: float) -> list[RetrievedChunk]:
        if self._collection.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=self._embedder.embed([question]), n_results=min(limit, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        distances = result["distances"][0]
        retrieved: list[RetrievedChunk] = []
        for text, metadata, distance in zip(documents, metadatas, distances, strict=True):
            score = max(0.0, 1.0 - float(distance))
            if score < minimum_score:
                continue
            source_metadata = {str(key): str(value) for key, value in metadata.items()}
            chunk = DocumentChunk(
                chunk_id=source_metadata.pop("chunk_id"), document_id=source_metadata.pop("document_id"),
                text=text, ordinal=int(source_metadata.pop("ordinal")),
                source_name=source_metadata.pop("source_name"), source_url=source_metadata.pop("source_url"),
                title=source_metadata.pop("title"), metadata=source_metadata,
            )
            retrieved.append(RetrievedChunk(chunk=chunk, score=score))
        return retrieved

    def source_statistics(self) -> list[dict[str, object]]:
        records = self._collection.get(include=["metadatas"])
        counts = Counter(metadata["source_name"] for metadata in records["metadatas"])
        return [{"source_name": name, "chunk_count": count} for name, count in sorted(counts.items())]

    def projects(self, limit: int) -> list[dict[str, str]]:
        records = self._collection.get(where={"category": "project"}, include=["documents", "metadatas"])
        projects: dict[str, dict[str, str]] = {}
        for text, metadata in zip(records["documents"], records["metadatas"], strict=True):
            title = str(metadata["title"])
            projects.setdefault(title, {
                "name": str(metadata.get("project_name", title)), "location": str(metadata.get("location", "")),
                "description": text[:350], "source_url": str(metadata["source_url"]),
            })
        return list(projects.values())[:limit]

    def reset(self) -> None:
        try:
            self._client.delete_collection(self._name)
        except ValueError:
            pass
        self._collection = self._client.get_or_create_collection(name=self._name, metadata={"hnsw:space": "cosine"})

    def health(self) -> dict[str, object]:
        return {"collection": self._name, "chunk_count": self._collection.count()}


def _batches(items: Sequence[DocumentChunk], size: int) -> list[Sequence[DocumentChunk]]:
    return [items[index:index + size] for index in range(0, len(items), size)]
