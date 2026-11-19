from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping


@dataclass(frozen=True, slots=True)
class SourceDocument:
    document_id: str
    source_name: str
    source_url: str
    title: str
    content: str
    category: str
    location: str | None
    metadata: Mapping[str, str] = field(default_factory=dict)
    scraped_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    chunk_id: str
    document_id: str
    text: str
    ordinal: int
    source_name: str
    source_url: str
    title: str
    metadata: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk: DocumentChunk
    score: float


@dataclass(frozen=True, slots=True)
class Citation:
    label: str
    title: str
    source_name: str
    source_url: str
    snippet: str


@dataclass(frozen=True, slots=True)
class ChatTurn:
    role: str
    content: str
    created_at: datetime
