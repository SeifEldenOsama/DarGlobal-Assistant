"""Ingest pre-collected JSONL corpus files into the pgvector store.

Usage (from backend/):
    python -m scripts.ingest_jsonl <path-to-jsonl> [--rebuild]

Each JSONL line must have at minimum: id, url, title, content.
Optional: site, language, content_chars.
Lines without meaningful content are silently skipped.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import structlog

# Ensure the backend package is importable when invoked as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.container import AppContainer
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.domain.entities import SourceDocument

# ---------------------------------------------------------------------------
# Content cleaning
# ---------------------------------------------------------------------------
# Strip markdown image references that are tracking pixels, ad beacons,
# analytics tags, or cookie-consent boilerplate.
_TRACKING_IMG = re.compile(
    r"!\[Image \d+[^\]]*\]\(https?://(?:"
    r"ad\.doubleclick\.net|"
    r"analytics\.twitter\.com|"
    r"t\.co/|"
    r"bat\.bing\.com|"
    r"www\.facebook\.com/tr"
    r")[^\)]*\)",
    re.IGNORECASE,
)
_COOKIE_BLOCK = re.compile(
    r"##?\s*We value our privacy.*?(?:ACCEPT|$)", re.DOTALL | re.IGNORECASE,
)
_CONSECUTIVE_BLANK = re.compile(r"\n{3,}")


def clean_content(raw: str) -> str:
    """Remove tracking pixels, ad beacons and cookie banners from scraped markdown."""
    text = _TRACKING_IMG.sub("", raw)
    text = _COOKIE_BLOCK.sub("", text)
    text = _CONSECUTIVE_BLANK.sub("\n\n", text).strip()
    return text


# ---------------------------------------------------------------------------
# Category inference
# ---------------------------------------------------------------------------
_PROJECT_SIGNALS = re.compile(
    r"(bedroom|villa|apartment|penthouse|residence|price|starting from|handover|payment plan|floor plan)",
    re.IGNORECASE,
)


def infer_category(title: str, url: str, content: str) -> str:
    lowurl = url.lower()
    if any(seg in lowurl for seg in ("/projects/", "/project/", "/properties/")):
        return "project"
    if any(seg in lowurl for seg in ("/press", "/news", "/blog", "/insights")):
        return "news"
    if "/investor" in lowurl or "/annual-report" in lowurl:
        return "investor"
    if "/faq" in lowurl:
        return "faq"
    if _PROJECT_SIGNALS.search(content[:1500]):
        return "project"
    return "general"


def infer_location(url: str, content: str) -> str | None:
    """Best-effort location from URL path segments or first content lines."""
    lowurl = url.lower()
    for label, keywords in [
        ("Dubai, UAE", ["dubai"]),
        ("Abu Dhabi, UAE", ["abu-dhabi"]),
        ("Muscat, Oman", ["oman", "muscat", "aida"]),
        ("Riyadh, Saudi Arabia", ["riyadh"]),
        ("Jeddah, Saudi Arabia", ["jeddah"]),
        ("AMAALA, Saudi Arabia", ["amaala"]),
        ("Qatar", ["qatar", "simaisma"]),
        ("London, UK", ["london"]),
        ("Marbella, Spain", ["marbella", "spain"]),
    ]:
        if any(kw in lowurl for kw in keywords):
            return label
    # Fallback: check first 500 chars of content
    snippet = content[:500].lower()
    for label, keywords in [
        ("Dubai, UAE", ["dubai"]),
        ("Muscat, Oman", ["muscat", "oman"]),
        ("Riyadh, Saudi Arabia", ["riyadh"]),
        ("Jeddah, Saudi Arabia", ["jeddah"]),
        ("Qatar", ["qatar"]),
        ("London, UK", ["london"]),
        ("Marbella, Spain", ["marbella"]),
    ]:
        if any(kw in snippet for kw in keywords):
            return label
    return None


# ---------------------------------------------------------------------------
# JSONL loading
# ---------------------------------------------------------------------------
_MIN_CONTENT_LENGTH = 80  # skip trivially short pages


def load_jsonl(path: Path) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    skipped = 0
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, raw_line in enumerate(fh, 1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError:
                structlog.get_logger().warning("bad_json_line", lineno=lineno)
                continue
            content = clean_content(record.get("content", ""))
            if len(content) < _MIN_CONTENT_LENGTH:
                skipped += 1
                continue
            url = record.get("url", "")
            title = record.get("title", "Untitled")
            site = record.get("site", "unknown")
            category = infer_category(title, url, content)
            location = infer_location(url, content)
            source_name = site.lower().replace(" ", "")
            doc = SourceDocument(
                document_id=record.get("id", f"{source_name}-{lineno:05d}"),
                source_name=source_name,
                source_url=url,
                title=title,
                content=content,
                category=category,
                location=location,
                metadata={
                    "language": record.get("language", "en"),
                    "category": category,
                    "source_name": source_name,
                    "source_url": url,
                    "title": title,
                    **({"location": location} if location else {}),
                    **({"project_name": title} if category == "project" else {}),
                },
            )
            documents.append(doc)
    structlog.get_logger().info(
        "jsonl_loaded", path=str(path), documents=len(documents), skipped=skipped,
    )
    return documents


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a JSONL corpus into the vector store.")
    parser.add_argument("files", nargs="+", type=Path, help="One or more .jsonl files to ingest.")
    parser.add_argument("--rebuild", action="store_true", help="Wipe existing vectors before ingesting.")
    parser.add_argument("--batch-size", type=int, default=20, help="Documents per embedding batch.")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    log = structlog.get_logger()

    log.info(
        "config",
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
        embedding_dimension=settings.embedding_dimension,
        vector_store=settings.vector_store,
        embedding_profile=settings.embedding_profile,
    )

    container = AppContainer.build(settings)
    ingest_uc = container.ingest_use_case()

    all_documents: list[SourceDocument] = []
    for filepath in args.files:
        if not filepath.exists():
            log.error("file_not_found", path=str(filepath))
            sys.exit(1)
        all_documents.extend(load_jsonl(filepath))

    if not all_documents:
        log.error("no_documents_loaded")
        sys.exit(1)

    log.info("ingesting", total_documents=len(all_documents), rebuild=args.rebuild)
    result = ingest_uc.execute(all_documents, rebuild=args.rebuild)
    log.info("ingestion_complete", **result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
