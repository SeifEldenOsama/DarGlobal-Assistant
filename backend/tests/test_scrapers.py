from pathlib import Path

from app.infrastructure.scrapers.darglobal import DarGlobalScraper
from app.infrastructure.scrapers.wasalt import WasaltScraper

FIXTURES = Path(__file__).parent / "fixtures"


def test_darglobal_parser_extracts_public_project_content() -> None:
    html = (FIXTURES / "darglobal_aida.html").read_text(encoding="utf-8")
    scraper = DarGlobalScraper("test-agent", 0.1, 5, 5)
    document = scraper.parse_page("https://darglobal.co.uk/landing-page/aida", html)
    assert document is not None
    assert document.category == "project"
    assert document.metadata["project_name"] == "WELCOME TO AIDA"
    assert "Fitness Center" in document.content
    assert "Navigation" not in document.content


def test_wasalt_parser_preserves_public_price_as_metadata() -> None:
    html = (FIXTURES / "wasalt_property.html").read_text(encoding="utf-8")
    scraper = WasaltScraper("test-agent", 0.1, 5, 5)
    document = scraper.parse_page("https://wasalt.sa/en/property/sale/apartment-with-3-bedrooms-5958999", html)
    assert document is not None
    assert document.category == "property_listing"
    assert document.metadata["public_price"] == "340000 SAR"
    assert document.location is not None
    assert "Jeddah" in document.location
