from __future__ import annotations

import argparse
import asyncio
import json
import sys

import structlog

from app.container import AppContainer
from app.core.config import get_settings
from app.core.logging import configure_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run public-source ingestion independently of the web API.")
    parser.add_argument("command", choices=["ingest"])
    parser.add_argument("--source", choices=["darglobal", "wasalt", "all"], default="all")
    parser.add_argument("--rebuild", action="store_true", help="Delete and rebuild the Chroma collection.")
    return parser.parse_args()


async def ingest(source: str, rebuild: bool) -> dict[str, object]:
    settings = get_settings()
    configure_logging(settings.log_level)
    container = AppContainer.build(settings)
    selected = container.scrapers()
    names = list(selected) if source == "all" else [source]
    documents = []
    failures: dict[str, str] = {}
    for name in names:
        try:
            fetched = await selected[name].scrape()
            documents.extend(fetched)
            structlog.get_logger().info("source_scraped", source=name, document_count=len(fetched))
        except Exception as error:
            failures[name] = str(error)
            structlog.get_logger().exception("source_ingestion_failed", source=name)
    result = container.ingest_use_case().execute(documents, rebuild=rebuild)
    return {**result, "source_failures": failures}


def main() -> None:
    args = parse_args()
    result = asyncio.run(ingest(args.source, args.rebuild))
    print(json.dumps(result, indent=2))
    if result["source_failures"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
