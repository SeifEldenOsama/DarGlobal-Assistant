from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

_EXCLUDED = ("script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe")


def page_title(soup: BeautifulSoup) -> str:
    heading = soup.find("h1")
    if isinstance(heading, Tag):
        return heading.get_text(" ", strip=True)
    if soup.title:
        return soup.title.get_text(" ", strip=True)
    return "Untitled public real estate page"


def main_text(soup: BeautifulSoup) -> str:
    """Keep semantic article content and deliberately remove site chrome."""
    root = soup.find("main") or soup.find("article") or soup.body or soup
    for element in root.find_all(_EXCLUDED):
        element.decompose()
    lines = [line.strip() for line in root.get_text("\n", strip=True).splitlines()]
    deduplicated: list[str] = []
    for line in lines:
        if line and (not deduplicated or line != deduplicated[-1]):
            deduplicated.append(line)
    return "\n".join(deduplicated)


def find_location(text: str) -> str | None:
    # Public property pages typically place their location after the page heading.
    patterns = [
        r"(?:Location|Address)\s*:?\s*([^\n]{3,120})",
        r"(?:Riyadh|Jeddah|Muscat|Dubai|Doha|Benahav[ií]s|Al Marjan Island)[^\n]{0,90}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip() if match.lastindex else match.group(0).strip()
    return None


def labelled_value(text: str, label: str) -> str | None:
    match = re.search(rf"{re.escape(label)}\s*:?\s*([^\n]{{1,120}})", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None
