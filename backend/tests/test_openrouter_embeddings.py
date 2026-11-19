from unittest.mock import Mock, patch

import pytest

from app.core.errors import ConfigurationError, ExternalServiceError
from app.infrastructure.embeddings.openrouter import OpenRouterEmbedder


def _response(payload: dict) -> Mock:
    response = Mock()
    response.status_code = 200
    response.is_error = False
    response.json.return_value = payload
    return response


@patch("app.infrastructure.embeddings.openrouter.httpx.Client")
def test_openrouter_embedder_verifies_and_normalises_vectors(client_factory: Mock) -> None:
    client = client_factory.return_value.__enter__.return_value
    client.request.side_effect = [
        _response({"data": [{"id": "nvidia/nemotron-3-embed-1b:free"}]}),
        _response({"data": [{"index": 0, "embedding": [3, 4]}]}),
    ]
    embedder = OpenRouterEmbedder("test-key", "nvidia/nemotron-3-embed-1b:free", 2, 10)

    assert embedder.embed(["AIDA amenities"]) == [[0.6, 0.8]]
    assert client.request.call_count == 2


def test_openrouter_embedder_requires_a_key() -> None:
    with pytest.raises(ConfigurationError, match="OPENROUTER_API_KEY"):
        OpenRouterEmbedder(None, "nvidia/nemotron-3-embed-1b:free", 2, 10).embed(["hello"])


@patch("app.infrastructure.embeddings.openrouter.httpx.Client")
def test_openrouter_embedder_rejects_a_wrong_dimension(client_factory: Mock) -> None:
    client = client_factory.return_value.__enter__.return_value
    client.request.side_effect = [
        _response({"data": [{"id": "nvidia/nemotron-3-embed-1b:free"}]}),
        _response({"data": [{"index": 0, "embedding": [1]}]}),
    ]
    embedder = OpenRouterEmbedder("test-key", "nvidia/nemotron-3-embed-1b:free", 2, 10)

    with pytest.raises(ExternalServiceError, match="unexpected dimension"):
        embedder.embed(["AIDA amenities"])
