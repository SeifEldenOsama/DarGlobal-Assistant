import pytest
from pydantic import ValidationError

from app.container import AppContainer
from app.core.config import Settings


def test_pgvector_configuration_requires_a_postgresql_url() -> None:
    with pytest.raises(ValidationError, match="VECTOR_STORE=pgvector requires"):
        Settings(vector_store="pgvector", database_url="")


def test_pgvector_configuration_accepts_a_postgresql_url() -> None:
    settings = Settings(vector_store="pgvector", database_url="postgresql+psycopg://user:password@host/database")
    assert settings.vector_store == "pgvector"


def test_sentence_transformer_configuration_rejects_an_incompatible_embedding_dimension() -> None:
    with pytest.raises(ValidationError, match="all-MiniLM-L6-v2"):
        Settings(
            vector_store="pgvector", database_url="postgresql+psycopg://user:password@host/database",
            embedding_provider="sentence_transformer",
            embedding_dimension=768,
        )


def test_openrouter_embedding_configuration_accepts_2048_dimensions() -> None:
    settings = Settings(
        vector_store="pgvector",
        database_url="postgresql+psycopg://user:password@host/database",
        embedding_provider="openrouter",
        embedding_model="nvidia/nemotron-3-embed-1b:free",
        embedding_dimension=2048,
    )
    assert settings.embedding_profile.endswith(":2048")


def test_pgvector_startup_does_not_create_a_local_data_directory(tmp_path, monkeypatch) -> None:
    """Vercel's application filesystem is read-only; Supabase needs no local data path."""
    target = tmp_path / "must-not-be-created"
    settings = Settings(
        vector_store="pgvector",
        database_url="postgresql+psycopg://user:password@host/database",
        data_dir=target,
    )

    class FakeVectorStore:
        pass

    monkeypatch.setattr(
        "app.infrastructure.vector_store.pgvector_store.PgVectorStore",
        lambda *_args: FakeVectorStore(),
    )
    monkeypatch.setattr("app.container.SqlAlchemyConversationStore", lambda *_args: object())

    AppContainer.build(settings)

    assert not target.exists()
