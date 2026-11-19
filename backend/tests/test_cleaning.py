from app.application.services.cleaning import canonical_url, clean_text, normalized_document


def test_canonical_url_removes_tracking_and_fragment() -> None:
    assert canonical_url("HTTPS://Example.com/home/?utm_source=x&region=sa#features") == "https://example.com/home?region=sa"


def test_normalized_document_has_stable_clean_content() -> None:
    document = normalized_document(
        source_name="Wasalt", source_url="https://wasalt.sa/en/a/?utm_campaign=test",
        title="  Sample\t listing ", content="First   line\n\n\nSecond line", category="property_listing",
    )
    assert document.source_url == "https://wasalt.sa/en/a"
    assert document.title == "Sample listing"
    assert document.content == "First line\n\nSecond line"
    assert len(document.document_id) == 64
