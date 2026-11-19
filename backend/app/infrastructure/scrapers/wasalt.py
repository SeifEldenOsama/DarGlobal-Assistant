from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.application.services.cleaning import normalized_document
from app.domain.entities import SourceDocument
from app.infrastructure.scrapers.base import PublicWebsiteScraper
from app.infrastructure.scrapers.html import find_location, labelled_value, main_text, page_title


class WasaltScraper(PublicWebsiteScraper):
    source_name = "Wasalt"
    base_url = "https://wasalt.sa"
    _listing_url = "https://wasalt.sa/en/properties-for-sale-in-saudi-arabia"

    async def discover_urls(self) -> list[str]:
        """Take only detail links rendered in the public listing's first page."""
        candidates = await self.sitemap_urls(("/en/property/", "/en/project/"))
        if self._allowed(self._listing_url):
            html = await self._get(self._listing_url)
            soup = BeautifulSoup(html, "html.parser")
            candidates.insert(0, self._listing_url)
            for anchor in soup.select("a[href]"):
                url = self.absolute_url(str(anchor["href"]))
                path = url.lower().split("?")[0]
                if self._same_site(url) and ("/en/property/" in path or "/en/project/" in path):
                    candidates.append(url)
        return list(dict.fromkeys(candidates))

    def parse_page(self, url: str, html: str) -> SourceDocument | None:
        soup = BeautifulSoup(html, "html.parser")
        title = page_title(soup)
        content = main_text(soup)
        if len(content) < 80:
            return None
        category = "project" if "/project/" in url else "property_listing" if "/property/" in url else "listing_index"
        metadata = {"source_type": "public_listing_page"}
        price = _price(content)
        if price:
            metadata["public_price"] = price
        bedrooms = labelled_value(content, "bedrooms")
        if bedrooms:
            metadata["bedrooms"] = bedrooms
        if category == "project":
            metadata["project_name"] = title
        return normalized_document(
            source_name=self.source_name, source_url=url, title=title, content=content, category=category,
            location=find_location(content), metadata=metadata,
        )


def _price(text: str) -> str | None:
    match = re.search(r"(?:Price\s*:\s*)?([\d,]+(?:\.\d+)?)\s*(SAR|SR|M)\b", text, re.IGNORECASE)
    if match:
        return " ".join(match.groups())
    return None
