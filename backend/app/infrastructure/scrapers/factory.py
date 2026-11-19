from __future__ import annotations

from app.core.config import Settings
from app.infrastructure.scrapers.darglobal import DarGlobalScraper
from app.infrastructure.scrapers.wasalt import WasaltScraper


def make_scrapers(settings: Settings) -> dict[str, DarGlobalScraper | WasaltScraper]:
    arguments = {
        "user_agent": settings.scraper_user_agent,
        "delay_seconds": settings.scraper_delay_seconds,
        "timeout_seconds": settings.scraper_timeout_seconds,
        "max_pages": settings.scraper_max_pages_per_source,
    }
    return {"darglobal": DarGlobalScraper(**arguments), "wasalt": WasaltScraper(**arguments)}
