from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.domain.entities import SourceDocument

_WHITESPACE = re.compile(r"[ \t\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def canonical_url(url: str) -> str:
    """Drop fragment and analytics query parameters without changing useful paths."""
    parts = urlsplit(url.strip())
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if not key.lower().startswith(("utm_", "fbclid", "gclid"))]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def clean_text(value: str) -> str:
    lines = [_WHITESPACE.sub(" ", line).strip() for line in value.replace("\r\n", "\n").split("\n")]
    # Keep a paragraph boundary for the semantic chunker while collapsing visual noise.
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def stable_document_id(source_name: str, source_url: str, content: str) -> str:
    material = f"{source_name}|{canonical_url(source_url)}|{content}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def normalized_document(
    *, source_name: str, source_url: str, title: str, content: str, category: str,
    location: str | None = None, metadata: Mapping[str, str] | None = None,
    scraped_at: datetime | None = None,
) -> SourceDocument:
    clean_content = clean_text(content)
    normalized_url = canonical_url(source_url)
    clean_title = clean_text(title) or normalized_url
    return SourceDocument(
        document_id=stable_document_id(source_name, normalized_url, clean_content),
        source_name=source_name,
        source_url=normalized_url,
        title=clean_title,
        content=clean_content,
        category=category,
        location=clean_text(location) if location else None,
        metadata={str(key): clean_text(str(value)) for key, value in (metadata or {}).items() if value},
        scraped_at=scraped_at or datetime.now(timezone.utc),
    )
