from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, JSON, String, Text, create_engine, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.errors import ConfigurationError
from app.domain.entities import DocumentChunk, RetrievedChunk
from app.domain.ports import Embedder


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
    # An unbounded vector column permits a deliberate model change. Queries
    # filter on embedding_profile, so incompatible vectors are never compared.
    embedding: Mapped[list[float]] = mapped_column(Vector())
    embedding_profile: Mapped[str] = mapped_column(String(512), index=True, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc),
    )


class PgVectorStore:
    """Serverless-safe PostgreSQL vector store for Supabase's pgvector extension."""

    def __init__(
        self, database_url: str, embedder: Embedder, embedding_dimension: int, embedding_profile: str,
    ) -> None:
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
        self._embedding_dimension = embedding_dimension
        self._embedding_profile = embedding_profile

    def _prepare_database(self) -> None:
        # Supabase documents pgvector in the extensions schema. Creating it is
        # idempotent; projects without the permission receive a clear startup error.
        with self._engine.begin() as connection:
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS extensions"))
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions"))
        VectorBase.metadata.create_all(self._engine)
        # Earlier releases created vector(384). This safe widening preserves
        # existing values and makes the store compatible with configured models.
        with self._engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE vector_chunks ADD COLUMN IF NOT EXISTS embedding_profile varchar(512) NOT NULL DEFAULT ''"
            ))
            connection.execute(text(
                "ALTER TABLE vector_chunks ALTER COLUMN embedding TYPE vector USING embedding::vector"
            ))

    _EMBED_BATCH_SIZE = 35  # max texts per embedding API call
    _DB_BATCH_SIZE = 100    # max rows per DB transaction
    _EMBED_BATCH_DELAY = 1.0  # seconds between embedding batches

    def upsert(self, chunks: Sequence[DocumentChunk]) -> int:
        if not chunks:
            return 0
        # Batch embedding calls to stay within API request-size limits.
        all_embeddings: list[list[float]] = []
        texts = [chunk.text for chunk in chunks]
        for batch_idx, start in enumerate(range(0, len(texts), self._EMBED_BATCH_SIZE)):
            if batch_idx > 0:
                time.sleep(self._EMBED_BATCH_DELAY)
            batch = texts[start : start + self._EMBED_BATCH_SIZE]
            batch_embeddings = self._embedder.embed(batch)
            if len(batch_embeddings) != len(batch) or any(
                len(e) != self._embedding_dimension for e in batch_embeddings
            ):
                raise ConfigurationError(
                    "The embedding provider returned an unexpected vector dimension. "
                    "Check EMBEDDING_MODEL and EMBEDDING_DIMENSION."
                )
            all_embeddings.extend(batch_embeddings)
        # Batch DB writes to avoid long-running transactions that may timeout
        # on remote connection poolers (e.g. Supabase transaction pooler).
        pairs = list(zip(chunks, all_embeddings, strict=True))
        for db_start in range(0, len(pairs), self._DB_BATCH_SIZE):
            db_batch = pairs[db_start : db_start + self._DB_BATCH_SIZE]
            with self._sessions.begin() as session:
                for chunk, embedding in db_batch:
                    values = _row_values(chunk, embedding, self._embedding_profile)
                    statement = insert(VectorChunkRow).values(**values)
                    statement = statement.on_conflict_do_update(
                        index_elements=[VectorChunkRow.chunk_id],
                        set_={key: value for key, value in values.items() if key != "chunk_id"},
                    )
                    session.execute(statement)
        return len(chunks)

    def query(self, question: str, limit: int, minimum_score: float) -> list[RetrievedChunk]:
        with self._sessions() as session:
            available = session.scalar(
                select(func.count()).select_from(VectorChunkRow).where(
                    VectorChunkRow.embedding_profile == self._embedding_profile,
                )
            ) or 0
        if available == 0:
            return []
        query_embedding = self._embedder.embed([question])[0]
        if len(query_embedding) != self._embedding_dimension:
            raise ConfigurationError(
                "The embedding provider returned an unexpected vector dimension. Check EMBEDDING_MODEL and EMBEDDING_DIMENSION."
            )
        distance = VectorChunkRow.embedding.cosine_distance(query_embedding)
        statement = (
            select(VectorChunkRow, distance.label("distance"))
            .where(VectorChunkRow.embedding_profile == self._embedding_profile)
            .order_by(distance)
            .limit(min(limit, available))
        )
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
        statement = (
            select(VectorChunkRow.source_name, func.count())
            .where(VectorChunkRow.embedding_profile == self._embedding_profile)
            .group_by(VectorChunkRow.source_name)
            .order_by(VectorChunkRow.source_name)
        )
        with self._sessions() as session:
            return [{"source_name": name, "chunk_count": count} for name, count in session.execute(statement).all()]

    def projects(self, limit: int) -> list[dict[str, str]]:
        statement = (
            select(VectorChunkRow)
            .where(
                VectorChunkRow.category == "project",
                VectorChunkRow.embedding_profile == self._embedding_profile,
            )
            .order_by(VectorChunkRow.title)
            .limit(limit * 3)
        )
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
            count = session.scalar(
                select(func.count()).select_from(VectorChunkRow).where(
                    VectorChunkRow.embedding_profile == self._embedding_profile,
                )
            ) or 0
        return {
            "provider": "pgvector",
            "embedding_dimensions": self._embedding_dimension,
            "chunk_count": count,
        }


def _row_values(chunk: DocumentChunk, embedding: list[float], embedding_profile: str = "") -> dict[str, object]:
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
        "embedding_profile": embedding_profile,
        "updated_at": datetime.now(timezone.utc),
    }
