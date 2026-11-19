import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_pgvector_configuration_requires_a_postgresql_url() -> None:
    with pytest.raises(ValidationError, match="VECTOR_STORE=pgvector requires"):
        Settings(vector_store="pgvector", database_url="")


def test_pgvector_configuration_accepts_a_postgresql_url() -> None:
    settings = Settings(vector_store="pgvector", database_url="postgresql+psycopg://user:password@host/database")
    assert settings.vector_store == "pgvector"


def test_pgvector_configuration_rejects_an_incompatible_embedding_dimension() -> None:
    with pytest.raises(ValidationError, match="EMBEDDING_DIMENSION=384"):
        Settings(
            vector_store="pgvector", database_url="postgresql+psycopg://user:password@host/database",
            embedding_dimension=768,
        )
