from app.infrastructure.vector_store.chroma_store import ChromaVectorStore
from app.infrastructure.vector_store.pgvector_store import _row_values
from app.domain.entities import DocumentChunk


class FakeEmbedder:
    def embed(self, texts):
        return [[0.1, 0.2] for _ in texts]


class FakeCollection:
    def count(self):
        return 2

    def query(self, **_):
        return {
            "documents": [["AIDA has pools", "unrelated result"]],
            "metadatas": [[
                {"chunk_id": "one", "document_id": "doc-one", "ordinal": 0, "source_name": "DarGlobal", "source_url": "https://example/aida", "title": "AIDA", "category": "project"},
                {"chunk_id": "two", "document_id": "doc-two", "ordinal": 0, "source_name": "Wasalt", "source_url": "https://example/listing", "title": "Listing", "category": "property_listing"},
            ]],
            "distances": [[0.12, 0.84]],
        }


def test_retrieval_discards_results_below_similarity_threshold() -> None:
    store = object.__new__(ChromaVectorStore)
    store._collection = FakeCollection()
    store._embedder = FakeEmbedder()
    results = store.query("Does AIDA have pools?", limit=5, minimum_score=0.5)
    assert len(results) == 1
    assert results[0].chunk.title == "AIDA"
    assert results[0].score == 0.88


def test_pgvector_row_serialization_preserves_retrieval_metadata() -> None:
    chunk = DocumentChunk(
        chunk_id="chunk", document_id="document", text="AIDA has pools", ordinal=0,
        source_name="DarGlobal", source_url="https://example.test/aida", title="AIDA",
        metadata={"category": "project", "location": "Muscat"},
    )
    row = _row_values(chunk, [0.1, 0.2])
    assert row["category"] == "project"
    assert row["chunk_metadata"] == {"category": "project", "location": "Muscat"}
    assert row["embedding"] == [0.1, 0.2]
