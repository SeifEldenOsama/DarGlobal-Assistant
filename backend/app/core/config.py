from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WORKSPACE_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Runtime configuration. Every operational choice is environment-driven."""

    # Local runs start from backend/, while the shared developer .env lives at
    # the repository root. Runtime environment variables always take priority.
    model_config = SettingsConfigDict(env_file=_WORKSPACE_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    api_cors_origins: str = "http://localhost:5173,http://localhost:8080"
    request_max_bytes: int = Field(default=32_768, ge=1_024, le=1_000_000)
    data_dir: Path = Path("/app/data")
    database_url: str | None = None
    chroma_collection: str = "real_estate_documents"
    vector_store: Literal["chroma", "pgvector"] = "chroma"
    embedding_dimension: int = Field(default=384, ge=1, le=4096)

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = Field(default=1100, ge=300, le=4000)
    chunk_overlap: int = Field(default=180, ge=0, le=1000)
    retrieval_top_k: int = Field(default=5, ge=1, le=12)
    retrieval_min_score: float = Field(default=0.32, ge=0, le=1)
    conversation_history_limit: int = Field(default=8, ge=0, le=20)

    openrouter_api_key: str | None = None
    openrouter_model: str = "openrouter/free"
    openrouter_timeout_seconds: float = Field(default=35, ge=5, le=120)

    scraper_user_agent: str = "DarGlobalWasaltResearchBot/1.0"
    scraper_delay_seconds: float = Field(default=1.5, ge=0.25, le=20)
    scraper_timeout_seconds: float = Field(default=20, ge=5, le=90)
    scraper_max_pages_per_source: int = Field(default=25, ge=1, le=250)

    @field_validator("api_cors_origins")
    @classmethod
    def validate_origins(cls, value: str) -> str:
        for origin in (item.strip() for item in value.split(",") if item.strip()):
            AnyHttpUrl(origin)
        return value

    @model_validator(mode="after")
    def validate_vector_store_configuration(self) -> "Settings":
        if self.vector_store == "pgvector" and not (self.database_url or "").startswith("postgresql"):
            raise ValueError("VECTOR_STORE=pgvector requires a PostgreSQL DATABASE_URL.")
        if self.vector_store == "pgvector" and self.embedding_dimension != 384:
            raise ValueError("VECTOR_STORE=pgvector currently requires EMBEDDING_DIMENSION=384.")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.api_cors_origins.split(",") if item.strip()]

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'app.db'}"

    @property
    def chroma_path(self) -> Path:
        return self.data_dir / "chroma"


@lru_cache
def get_settings() -> Settings:
    return Settings()
