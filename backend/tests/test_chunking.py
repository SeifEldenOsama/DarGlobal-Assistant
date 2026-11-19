from app.application.services.chunking import SemanticChunker
from app.application.services.cleaning import normalized_document


def test_chunker_preserves_source_metadata_and_chunks_on_paragraph_boundaries() -> None:
    document = normalized_document(
        source_name="DarGlobal", source_url="https://darglobal.co.uk/landing-page/aida", title="AIDA",
        content="AIDA is in Muscat.\n\nAmenities include pools and parks.\n\nThe community is gated.",
        category="project", location="Muscat", metadata={"project_name": "AIDA"},
    )
    chunks = SemanticChunker(chunk_size=43, overlap=5).split(document)
    assert len(chunks) >= 2
    assert chunks[0].metadata["project_name"] == "AIDA"
    assert all(chunk.source_url == document.source_url for chunk in chunks)
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)
