from __future__ import annotations

from dataclasses import dataclass

from app.application.services.prompts import SYSTEM_PROMPT, build_user_prompt
from app.domain.entities import Citation, ChatTurn
from app.domain.ports import ConversationStore, LanguageModel, VectorStore


@dataclass(frozen=True, slots=True)
class ChatResult:
    conversation_id: str
    answer: str
    citations: list[Citation]
    retrieved_count: int


class AnswerQuestion:
    def __init__(
        self, vector_store: VectorStore, language_model: LanguageModel,
        conversations: ConversationStore, top_k: int, minimum_score: float, history_limit: int,
    ) -> None:
        self._vectors = vector_store
        self._llm = language_model
        self._conversations = conversations
        self._top_k = top_k
        self._minimum_score = minimum_score
        self._history_limit = history_limit

    async def execute(self, conversation_id: str, question: str) -> ChatResult:
        retrieved = self._vectors.query(question, self._top_k, self._minimum_score)
        if not retrieved:
            answer = "I couldn't find enough relevant information in the indexed public sources to answer that reliably."
            self._conversations.append(conversation_id, "user", question)
            self._conversations.append(conversation_id, "assistant", answer)
            return ChatResult(conversation_id, answer, [], 0)

        history = self._conversations.history(conversation_id, self._history_limit)
        prompt = build_user_prompt(question, history, retrieved)
        answer = await self._llm.generate(SYSTEM_PROMPT, prompt)
        citations = [
            Citation(
                label=f"S{index}", title=item.chunk.title, source_name=item.chunk.source_name,
                source_url=item.chunk.source_url, snippet=item.chunk.text[:280].rsplit(" ", 1)[0] + "…",
            )
            for index, item in enumerate(retrieved, start=1)
        ]
        self._conversations.append(conversation_id, "user", question)
        self._conversations.append(conversation_id, "assistant", answer)
        return ChatResult(conversation_id, answer, citations, len(retrieved))

    def history(self, conversation_id: str) -> list[ChatTurn]:
        return self._conversations.history(conversation_id, 100)
