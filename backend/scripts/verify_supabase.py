"""Fail-fast connection and pgvector validation for Vercel/Supabase setup."""

from __future__ import annotations

from sqlalchemy import create_engine, text

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    if settings.vector_store != "pgvector":
        raise SystemExit("Set VECTOR_STORE=pgvector before running this check.")
    engine = create_engine(settings.resolved_database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        version = connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
        if not version:
            raise SystemExit("pgvector is not enabled. In Supabase: Database → Extensions → enable vector.")
        print(f"Supabase connection verified; pgvector {version} is enabled.")


if __name__ == "__main__":
    main()
