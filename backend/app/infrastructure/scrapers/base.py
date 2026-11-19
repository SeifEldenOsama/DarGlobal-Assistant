from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Final
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

import httpx
import structlog

from app.core.errors import ExternalServiceError
from app.domain.entities import SourceDocument


class PublicWebsiteScraper(ABC):
    source_name: Final[str]
    base_url: Final[str]

    def __init__(self, user_agent: str, delay_seconds: float, timeout_seconds: float, max_pages: int) -> None:
        self._headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"}
        self._delay = delay_seconds
        self._timeout = timeout_seconds
        self._max_pages = max_pages
        self._robots: RobotFileParser | None = None
        self._sitemap_urls: list[str] = []
        self._last_request_at = 0.0
        self._logger = structlog.get_logger().bind(source=self.source_name)

    async def scrape(self) -> list[SourceDocument]:
        await self._load_robots()
        urls = await self.discover_urls()
        documents: list[SourceDocument] = []
        for url in urls[:self._max_pages]:
            if not self._allowed(url):
                self._logger.info("scrape_skipped_by_robots", url=url)
                continue
            try:
                html = await self._get(url)
                document = self.parse_page(url, html)
                if document and document.content:
                    documents.append(document)
            except ExternalServiceError as error:
                self._logger.warning("scrape_page_failed", url=url, reason=error.message)
            except Exception as error:  # A malformed public page must not stop the source run.
                self._logger.warning("scrape_page_parse_failed", url=url, error_type=type(error).__name__)
        return documents

    @abstractmethod
    async def discover_urls(self) -> list[str]: ...

    @abstractmethod
    def parse_page(self, url: str, html: str) -> SourceDocument | None: ...

    async def _load_robots(self) -> None:
        robots_url = urljoin(self.base_url, "/robots.txt")
        parser = RobotFileParser()
        try:
            text = await self._get(robots_url)
            parser.parse(text.splitlines())
            self._sitemap_urls = _sitemap_directives(text, self.base_url)
        except ExternalServiceError:
            # Without an accessible policy, do not crawl beyond explicitly configured public seed URLs.
            parser.parse(["User-agent: *", "Disallow: /"])
            self._logger.warning("robots_unavailable", url=robots_url)
        self._robots = parser

    async def sitemap_urls(self, allowed_path_fragments: tuple[str, ...]) -> list[str]:
        """Discover a bounded set of relevant public URLs from robots-declared XML sitemaps."""
        candidates: list[str] = []
        pending = self._sitemap_urls[:4]  # Never recursively fan out without a tight cap.
        visited: set[str] = set()
        while pending and len(visited) < 8:
            sitemap_url = pending.pop(0)
            if sitemap_url in visited or not self._same_site(sitemap_url):
                continue
            visited.add(sitemap_url)
            try:
                xml = await self._get(sitemap_url)
                locations, is_index = _parse_sitemap(xml)
            except ExternalServiceError as error:
                self._logger.warning("sitemap_fetch_failed", url=sitemap_url, reason=error.message)
                continue
            if is_index:
                pending.extend(url for url in locations if self._same_site(url))
                continue
            candidates.extend(
                url for url in locations
                if self._same_site(url) and any(fragment in url.lower() for fragment in allowed_path_fragments)
            )
            if len(candidates) >= self._max_pages * 3:
                break
        return list(dict.fromkeys(candidates))[: self._max_pages * 3]

    async def _get(self, url: str) -> str:
        for attempt in range(3):
            try:
                await self._respect_rate_limit()
                async with httpx.AsyncClient(headers=self._headers, timeout=self._timeout, follow_redirects=True) as client:
                    response = await client.get(url)
                if response.status_code in {401, 403}:
                    raise ExternalServiceError(
                        f"Access to public page was blocked (HTTP {response.status_code}); crawler stopped without bypassing it."
                    )
                response.raise_for_status()
                if _is_access_interstitial(response.text):
                    raise ExternalServiceError("Access-control interstitial received; crawler stopped without bypassing it.")
                return response.text
            except httpx.HTTPError as error:
                if attempt == 2:
                    raise ExternalServiceError(f"Could not fetch public page ({type(error).__name__}).") from error
                await asyncio.sleep(0.5 * (2 ** attempt))
        raise ExternalServiceError("Could not fetch public page.")

    async def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._delay:
            await asyncio.sleep(self._delay - elapsed)
        self._last_request_at = time.monotonic()

    def _allowed(self, url: str) -> bool:
        return bool(self._robots and self._robots.can_fetch(self._headers["User-Agent"], url))

    def _same_site(self, url: str) -> bool:
        return urlparse(url).netloc.lower() == urlparse(self.base_url).netloc.lower()

    def absolute_url(self, href: str) -> str:
        return urljoin(self.base_url, href)


def _is_access_interstitial(html: str) -> bool:
    lowered = html.lower()
    signals = ("_incapsula_resource", "cf-chl-", "captcha", "access denied")
    return any(signal in lowered for signal in signals) and len(lowered) < 20_000


def _sitemap_directives(robots_text: str, base_url: str) -> list[str]:
    return [
        urljoin(base_url, line.split(":", 1)[1].strip())
        for line in robots_text.splitlines()
        if line.lower().startswith("sitemap:") and line.split(":", 1)[1].strip()
    ]


def _parse_sitemap(xml: str) -> tuple[list[str], bool]:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return [], False
    tag = root.tag.rsplit("}", 1)[-1].lower()
    locations = [element.text.strip() for element in root.findall(".//{*}loc") if element.text and element.text.strip()]
    return locations, tag == "sitemapindex"
