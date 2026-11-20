from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import NullPool

from app.domain.entities import ChatTurn


class Base(DeclarativeBase):
    pass


class ConversationRow(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    messages: Mapped[list["MessageRow"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class MessageRow(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    conversation: Mapped[ConversationRow] = relationship(back_populates="messages")


class SqlAlchemyConversationStore:
    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url, **_engine_options(database_url))
        Base.metadata.create_all(self._engine)
        self._sessions = sessionmaker(self._engine, expire_on_commit=False)

    def history(self, conversation_id: str, limit: int) -> list[ChatTurn]:
        with self._sessions() as session:
            statement = select(MessageRow).where(MessageRow.conversation_id == conversation_id).order_by(MessageRow.id.desc()).limit(limit)
            rows = list(reversed(session.scalars(statement).all()))
        return [ChatTurn(role=row.role, content=row.content, created_at=row.created_at) for row in rows]

    def append(self, conversation_id: str, role: str, content: str) -> None:
        with self._sessions.begin() as session:
            if session.get(ConversationRow, conversation_id) is None:
                session.add(ConversationRow(id=conversation_id))
            session.add(MessageRow(conversation_id=conversation_id, role=role, content=content))

    def delete(self, conversation_id: str) -> None:
        with self._sessions.begin() as session:
            row = session.get(ConversationRow, conversation_id)
            if row is not None:
                session.delete(row)


def _engine_options(database_url: str) -> dict[str, object]:
    options: dict[str, object] = {
        "connect_args": {"check_same_thread": False} if database_url.startswith("sqlite") else {},
    }
    if database_url.startswith("postgresql"):
        # Vercel Functions use Supabase's transaction pooler; avoid retaining
        # process-local database connections across function invocations.
        options["poolclass"] = NullPool
    return options
