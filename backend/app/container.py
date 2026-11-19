from __future__ import annotations

from dataclasses import dataclass

from app.application.services.chunking import SemanticChunker
from app.application.use_cases.chat import AnswerQuestion
from app.application.use_cases.ingest import IngestDocuments
from app.core.config import Settings
from app.core.errors import ConfigurationError
from app.domain.ports import Embedder, VectorStore
from app.infrastructure.embeddings.openrouter import OpenRouterEmbedder
from app.infrastructure.embeddings.sentence_transformer import SentenceTransformerEmbedder
from app.infrastructure.llm.openrouter import OpenRouterLanguageModel
from app.infrastructure.persistence.conversations import SqlAlchemyConversationStore
from app.infrastructure.scrapers.factory import make_scrapers


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    vectors: VectorStore
    conversations: SqlAlchemyConversationStore
    language_model: OpenRouterLanguageModel

    @classmethod
    def build(cls, settings: Settings) -> "AppContainer":
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        embedder = _make_embedder(settings)
        vectors: VectorStore
        if settings.vector_store == "pgvector":
            from app.infrastructure.vector_store.pgvector_store import PgVectorStore

            vectors = PgVectorStore(
                settings.resolved_database_url,
                embedder,
                settings.embedding_dimension,
                settings.embedding_profile,
            )
        else:
            try:
                from app.infrastructure.vector_store.chroma_store import ChromaVectorStore
            except ModuleNotFoundError as error:
                raise ConfigurationError(
                    "Chroma is a local-only dependency. Set VECTOR_STORE=pgvector for this deployment."
                ) from error
            vectors = ChromaVectorStore(settings.chroma_path, settings.chroma_collection, embedder)
        return cls(
            settings=settings,
            vectors=vectors,
            conversations=SqlAlchemyConversationStore(settings.resolved_database_url),
            language_model=OpenRouterLanguageModel(
                settings.openrouter_api_key, settings.openrouter_model, settings.openrouter_timeout_seconds,
            ),
        )

    def chat_use_case(self) -> AnswerQuestion:
        return AnswerQuestion(
            self.vectors, self.language_model, self.conversations, self.settings.retrieval_top_k,
            self.settings.retrieval_min_score, self.settings.conversation_history_limit,
        )

    def ingest_use_case(self) -> IngestDocuments:
        return IngestDocuments(SemanticChunker(self.settings.chunk_size, self.settings.chunk_overlap), self.vectors)

    def scrapers(self):
        return make_scrapers(self.settings)


def _make_embedder(settings: Settings) -> Embedder:
    if settings.embedding_provider == "openrouter":
        return OpenRouterEmbedder(
            settings.openrouter_api_key,
            settings.embedding_model,
            settings.embedding_dimension,
            settings.openrouter_timeout_seconds,
        )
    return SentenceTransformerEmbedder(settings.embedding_model)
