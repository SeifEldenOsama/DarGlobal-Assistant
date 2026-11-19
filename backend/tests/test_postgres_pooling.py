from sqlalchemy.pool import NullPool

from app.infrastructure.persistence.conversations import _engine_options


def test_postgresql_conversations_use_short_lived_connections() -> None:
    options = _engine_options("postgresql+psycopg://user:password@host/database")
    assert options["poolclass"] is NullPool
    assert options["connect_args"] == {}


def test_sqlite_conversations_keep_the_required_thread_option() -> None:
    options = _engine_options("sqlite:///./data/app.db")
    assert "poolclass" not in options
    assert options["connect_args"] == {"check_same_thread": False}
