from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, JSON, String, Text, create_engine, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool

from app.domain.entities import DocumentChunk, RetrievedChunk
from app.infrastructure.embeddings.sentence_transformer import SentenceTransformerEmbedder

EMBEDDING_DIMENSIONS = 384  # sentence-transformers/all-MiniLM-L6-v2 output size


class VectorBase(DeclarativeBase):
    pass


class VectorChunkRow(VectorBase):
    __tablename__ = "vector_chunks"

    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(64), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    source_name: Mapped[str] = mapped_column(String(64), index=True)
    source_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[str] = mapped_column(Text)
    chunk_metadata: Mapped[dict[str, str]] = mapped_column(JSON)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc),
    )


class PgVectorStore:
    """Serverless-safe PostgreSQL vector store for Supabase's pgvector extension."""

    def __init__(self, database_url: str, embedder: SentenceTransformerEmbedder) -> None:
        self._engine = create_engine(
            database_url,
            pool_pre_ping=True,
            poolclass=NullPool,
            connect_args={
                "options": "-csearch_path=public,extensions",
                # Supabase's transaction pooler is incompatible with named
                # prepared statements kept by a client connection.
                "prepare_threshold": None,
            },
        )
        self._prepare_database()
        self._sessions = sessionmaker(self._engine, expire_on_commit=False)
        self._embedder = embedder

    def _prepare_database(self) -> None:
        # Supabase documents pgvector in the extensions schema. Creating it is
        # idempotent; projects without the permission receive a clear startup error.
        with self._engine.begin() as connection:
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS extensions"))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions"))
        VectorBase.metadata.create_all(self._engine)

    def upsert(self, chunks: Sequence[DocumentChunk]) -> int:
        if not chunks:
            return 0
        embeddings = self._embedder.embed([chunk.text for chunk in chunks])
        with self._sessions.begin() as session:
            for chunk, embedding in zip(chunks, embeddings, strict=True):
                values = _row_values(chunk, embedding)
                statement = insert(VectorChunkRow).values(**values)
                statement = statement.on_conflict_do_update(
                    index_elements=[VectorChunkRow.chunk_id],
                    set_={key: value for key, value in values.items() if key != "chunk_id"},
                )
                session.execute(statement)
        return len(chunks)

    def query(self, question: str, limit: int, minimum_score: float) -> list[RetrievedChunk]:
        query_embedding = self._embedder.embed([question])[0]
        distance = VectorChunkRow.embedding.cosine_distance(query_embedding)
        statement = select(VectorChunkRow, distance.label("distance")).order_by(distance).limit(limit)
        with self._sessions() as session:
            rows = session.execute(statement).all()
        results: list[RetrievedChunk] = []
        for row, value in rows:
            score = max(0.0, 1.0 - float(value))
            if score < minimum_score:
                continue
            chunk = DocumentChunk(
                chunk_id=row.chunk_id, document_id=row.document_id, text=row.content, ordinal=row.ordinal,
                source_name=row.source_name, source_url=row.source_url, title=row.title,
                metadata=dict(row.chunk_metadata),
            )
            results.append(RetrievedChunk(chunk=chunk, score=score))
        return results

    def source_statistics(self) -> list[dict[str, object]]:
        statement = select(VectorChunkRow.source_name, func.count()).group_by(VectorChunkRow.source_name).order_by(VectorChunkRow.source_name)
        with self._sessions() as session:
            return [{"source_name": name, "chunk_count": count} for name, count in session.execute(statement).all()]

    def projects(self, limit: int) -> list[dict[str, str]]:
        statement = select(VectorChunkRow).where(VectorChunkRow.category == "project").order_by(VectorChunkRow.title).limit(limit * 3)
        with self._sessions() as session:
            rows = session.scalars(statement).all()
        projects: dict[str, dict[str, str]] = {}
        for row in rows:
            projects.setdefault(row.title, {
                "name": row.chunk_metadata.get("project_name", row.title),
                "location": row.chunk_metadata.get("location", ""),
                "description": row.content[:350],
                "source_url": row.source_url,
            })
        return list(projects.values())[:limit]

    def reset(self) -> None:
        with self._sessions.begin() as session:
            session.query(VectorChunkRow).delete()

    def health(self) -> dict[str, object]:
        with self._sessions() as session:
            count = session.scalar(select(func.count()).select_from(VectorChunkRow)) or 0
        return {"provider": "pgvector", "embedding_dimensions": EMBEDDING_DIMENSIONS, "chunk_count": count}


def _row_values(chunk: DocumentChunk, embedding: list[float]) -> dict[str, object]:
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "ordinal": chunk.ordinal,
        "source_name": chunk.source_name,
        "source_url": chunk.source_url,
        "title": chunk.title,
        "category": str(chunk.metadata.get("category", "")),
        "content": chunk.text,
        "chunk_metadata": dict(chunk.metadata),
        "embedding": embedding,
        "updated_at": datetime.now(timezone.utc),
    }
