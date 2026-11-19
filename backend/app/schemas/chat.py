from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(min_length=2, max_length=4_000, description="A real-estate question")
    conversation_id: UUID | None = Field(default=None, description="Client-generated conversation UUID")


class CitationResponse(BaseModel):
    label: str
    title: str
    source_name: str
    source_url: str
    snippet: str


class ChatResponse(BaseModel):
    conversation_id: UUID
    answer: str
    sources: list[CitationResponse]
    retrieved_count: int


class ConversationTurnResponse(BaseModel):
    role: str
    content: str
    created_at: datetime


class ConversationResponse(BaseModel):
    conversation_id: UUID
    messages: list[ConversationTurnResponse]
