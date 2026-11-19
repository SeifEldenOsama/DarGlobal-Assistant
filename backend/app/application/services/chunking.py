from __future__ import annotations

import hashlib
import re

from app.domain.entities import DocumentChunk, SourceDocument

_PARAGRAPHS = re.compile(r"\n\s*\n")


class SemanticChunker:
    """Paragraph-first chunker; only overlong paragraphs are split by words."""

    def __init__(self, chunk_size: int, overlap: int) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, document: SourceDocument) -> list[DocumentChunk]:
        paragraphs = [p.strip() for p in _PARAGRAPHS.split(document.content) if p.strip()]
        units = [piece for paragraph in paragraphs for piece in self._split_long_paragraph(paragraph)]
        groups: list[str] = []
        current: list[str] = []
        current_length = 0
        for unit in units:
            added_length = len(unit) + (2 if current else 0)
            if current and current_length + added_length > self.chunk_size:
                groups.append("\n\n".join(current))
                current = self._overlap_units(current)
                current_length = len("\n\n".join(current))
            current.append(unit)
            current_length += len(unit) + (2 if len(current) > 1 else 0)
        if current:
            groups.append("\n\n".join(current))
        return [self._chunk(document, text, ordinal) for ordinal, text in enumerate(groups)]

    def _split_long_paragraph(self, paragraph: str) -> list[str]:
        if len(paragraph) <= self.chunk_size:
            return [paragraph]
        words = paragraph.split()
        fragments: list[str] = []
        part: list[str] = []
        length = 0
        for word in words:
            if part and length + len(word) + 1 > self.chunk_size:
                fragments.append(" ".join(part))
                part = self._tail_words(part)
                length = len(" ".join(part))
            part.append(word)
            length += len(word) + (1 if len(part) > 1 else 0)
        if part:
            fragments.append(" ".join(part))
        return fragments

    def _tail_words(self, words: list[str]) -> list[str]:
        selected: list[str] = []
        size = 0
        for word in reversed(words):
            if size + len(word) + 1 > self.overlap:
                break
            selected.append(word)
            size += len(word) + 1
        return list(reversed(selected))

    def _overlap_units(self, units: list[str]) -> list[str]:
        selected: list[str] = []
        size = 0
        for unit in reversed(units):
            if size + len(unit) + 2 > self.overlap:
                break
            selected.append(unit)
            size += len(unit) + 2
        return list(reversed(selected))

    @staticmethod
    def _chunk(document: SourceDocument, text: str, ordinal: int) -> DocumentChunk:
        digest = hashlib.sha256(f"{document.document_id}:{ordinal}:{text}".encode()).hexdigest()
        metadata = {
            **document.metadata,
            "document_id": document.document_id,
            "category": document.category,
            "source_name": document.source_name,
            "source_url": document.source_url,
            "title": document.title,
        }
        if document.location:
            metadata["location"] = document.location
        return DocumentChunk(
            chunk_id=digest, document_id=document.document_id, text=text, ordinal=ordinal,
            source_name=document.source_name, source_url=document.source_url,
            title=document.title, metadata=metadata,
        )
