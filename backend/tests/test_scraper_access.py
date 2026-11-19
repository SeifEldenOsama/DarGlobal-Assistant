from app.infrastructure.scrapers.base import _is_access_interstitial, _parse_sitemap, _sitemap_directives


def test_detects_access_control_interstitial_without_parsing_it_as_content() -> None:
    page = '<html><meta name="robots" content="noindex,nofollow"><script src="/_Incapsula_Resource"></script></html>'
    assert _is_access_interstitial(page)


def test_regular_real_estate_html_is_not_misclassified_as_access_control() -> None:
    page = "<html><main><h1>AIDA</h1><p>Public project information and amenities.</p></main></html>"
    assert not _is_access_interstitial(page)


def test_sitemap_discovery_extracts_robots_declarations_and_namespaced_urls() -> None:
    directives = _sitemap_directives("User-agent: *\nSitemap: /sitemap.xml", "https://example.test")
    urls, is_index = _parse_sitemap(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.test/project/aida</loc></url></urlset>'
    )
    assert directives == ["https://example.test/sitemap.xml"]
    assert urls == ["https://example.test/project/aida"]
    assert not is_index
