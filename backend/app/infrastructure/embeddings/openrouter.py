from __future__ import annotations

import math
import time
from collections.abc import Sequence
from typing import Any

import httpx

from app.core.errors import ConfigurationError, ExternalServiceError, RateLimitError


class OpenRouterEmbedder:
    """Small remote embedding adapter used by the Vercel deployment.

    It shares the existing backend-only OpenRouter credential, avoiding a
    bundled PyTorch runtime in the request function.
    """

    _base_url = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str | None, model: str, dimensions: int, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._timeout = timeout_seconds
        self._verified = False

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        self._verify_model()
        payload = {
            "model": self._model,
            "input": list(texts),
            "dimensions": self._dimensions,
            "encoding_format": "float",
        }
        response = self._request("POST", "/embeddings", payload)
        raw_items = response.get("data")
        if not isinstance(raw_items, list) or len(raw_items) != len(texts):
            raise ExternalServiceError("OpenRouter returned an invalid embedding response.")

        vectors: list[list[float] | None] = [None] * len(texts)
        for item in raw_items:
            if not isinstance(item, dict):
                raise ExternalServiceError("OpenRouter returned an invalid embedding response.")
            index = item.get("index")
            embedding = item.get("embedding")
            if not isinstance(index, int) or not 0 <= index < len(vectors):
                raise ExternalServiceError("OpenRouter returned an invalid embedding response.")
            vectors[index] = _normalise_embedding(embedding, self._dimensions)
        if any(vector is None for vector in vectors):
            raise ExternalServiceError("OpenRouter returned incomplete embeddings.")
        return [vector for vector in vectors if vector is not None]

    def _verify_model(self) -> None:
        if self._verified:
            return
        response = self._request("GET", "/embeddings/models")
        models = response.get("data")
        if not isinstance(models, list) or not any(
            isinstance(item, dict) and item.get("id") == self._model for item in models
        ):
            raise ConfigurationError(f"Configured OpenRouter embedding model '{self._model}' is unavailable.")
        self._verified = True

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._api_key:
            raise ConfigurationError("OpenRouter embeddings are not configured. Set OPENROUTER_API_KEY on the backend.")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/your-org/real-estate-ai-assistant",
            "X-Title": "DarGlobal & Wasalt Real Estate Assistant",
        }
        for attempt in range(3):
            try:
                with httpx.Client(base_url=self._base_url, timeout=self._timeout) as client:
                    response = client.request(method, path, json=payload, headers=headers)
                if response.status_code == 429:
                    if attempt == 2:
                        raise RateLimitError("The embedding model is temporarily rate-limited. Please try again shortly.")
                elif response.status_code >= 500:
                    if attempt == 2:
                        raise ExternalServiceError("OpenRouter embeddings are temporarily unavailable.")
                elif response.is_error:
                    raise ExternalServiceError("The embedding request was rejected.")
                else:
                    data = response.json()
                    if not isinstance(data, dict):
                        raise ExternalServiceError("OpenRouter returned an invalid embedding response.")
                    return data
            except httpx.HTTPError as error:
                if attempt == 2:
                    raise ExternalServiceError("Could not reach OpenRouter for embeddings.") from error
            time.sleep(0.5 * (2**attempt))
        raise ExternalServiceError("OpenRouter embedding request failed.")


def _normalise_embedding(value: object, expected_dimensions: int) -> list[float]:
    if not isinstance(value, list) or len(value) != expected_dimensions:
        raise ExternalServiceError("OpenRouter returned an embedding with an unexpected dimension.")
    try:
        vector = [float(component) for component in value]
    except (TypeError, ValueError) as error:
        raise ExternalServiceError("OpenRouter returned an invalid embedding.") from error
    magnitude = math.sqrt(sum(component * component for component in vector))
    if magnitude == 0:
        raise ExternalServiceError("OpenRouter returned an empty embedding.")
    return [component / magnitude for component in vector]
