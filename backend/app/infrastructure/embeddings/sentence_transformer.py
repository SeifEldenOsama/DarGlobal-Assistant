from __future__ import annotations

from collections.abc import Sequence


class SentenceTransformerEmbedder:
    """Lazy local embedder so API startup does not download a model."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        vectors = self._model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return vectors.tolist()
