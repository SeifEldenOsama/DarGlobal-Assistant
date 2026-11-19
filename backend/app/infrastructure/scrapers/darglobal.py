from __future__ import annotations

from bs4 import BeautifulSoup

from app.application.services.cleaning import normalized_document
from app.domain.entities import SourceDocument
from app.infrastructure.scrapers.base import PublicWebsiteScraper
from app.infrastructure.scrapers.html import find_location, main_text, page_title


class DarGlobalScraper(PublicWebsiteScraper):
    source_name = "DarGlobal"
    base_url = "https://darglobal.co.uk"
    _projects_url = "https://darglobal.co.uk/projects"

    async def discover_urls(self) -> list[str]:
        """Use the public portfolio index, never guessed slugs or unbounded crawling."""
        candidates = await self.sitemap_urls(("/landing-page/", "/project/"))
        if self._allowed(self._projects_url):
            html = await self._get(self._projects_url)
            soup = BeautifulSoup(html, "html.parser")
            candidates.insert(0, self._projects_url)
            for anchor in soup.select("a[href]"):
                url = self.absolute_url(str(anchor["href"]))
                path = url.lower().split("?")[0]
                if self._same_site(url) and ("/landing-page/" in path or "/project/" in path):
                    candidates.append(url)
        return list(dict.fromkeys(candidates))

    def parse_page(self, url: str, html: str) -> SourceDocument | None:
        soup = BeautifulSoup(html, "html.parser")
        title = page_title(soup)
        content = main_text(soup)
        if len(content) < 80:
            return None
        location = find_location(content)
        category = "portfolio" if url == self._projects_url else "project"
        return normalized_document(
            source_name=self.source_name, source_url=url, title=title, content=content, category=category,
            location=location, metadata={"project_name": title, "source_type": "public_project_page"},
        )
