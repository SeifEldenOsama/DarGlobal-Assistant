from __future__ import annotations

from dataclasses import dataclass

from app.application.services.chunking import SemanticChunker
from app.application.use_cases.chat import AnswerQuestion
from app.application.use_cases.ingest import IngestDocuments
from app.core.config import Settings
from app.domain.ports import VectorStore
from app.infrastructure.embeddings.sentence_transformer import SentenceTransformerEmbedder
from app.infrastructure.llm.openrouter import OpenRouterLanguageModel
from app.infrastructure.persistence.conversations import SqlAlchemyConversationStore
from app.infrastructure.scrapers.factory import make_scrapers
from app.infrastructure.vector_store.chroma_store import ChromaVectorStore
from app.infrastructure.vector_store.pgvector_store import PgVectorStore


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    vectors: VectorStore
    conversations: SqlAlchemyConversationStore
    language_model: OpenRouterLanguageModel

    @classmethod
    def build(cls, settings: Settings) -> "AppContainer":
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        embedder = SentenceTransformerEmbedder(settings.embedding_model)
        vectors: VectorStore
        if settings.vector_store == "pgvector":
            vectors = PgVectorStore(settings.resolved_database_url, embedder)
        else:
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
