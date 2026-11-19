from __future__ import annotations

import re
from dataclasses import dataclass

from app.application.services.prompts import SYSTEM_PROMPT, build_user_prompt
from app.domain.entities import Citation, ChatTurn
from app.domain.ports import ConversationStore, LanguageModel, VectorStore

_ACKNOWLEDGEMENTS = frozenset({
    "okay", "ok", "okay thanks", "ok thanks", "thanks", "thank you",
    "thank you so much", "got it", "great", "great thanks", "perfect",
})
_GREETINGS = frozenset({"hello", "hi", "hey", "good morning", "good afternoon", "good evening"})
_REAL_ESTATE_TERMS = frozenset({
    "aida", "amenities", "amenity", "apartment", "bathroom", "bedroom", "buy", "cost",
    "dar global", "darglobal", "developer", "golf", "home", "lease", "listing", "location",
    "penthouse", "pool", "price", "project", "property", "real estate", "rent", "sale", "sell",
    "square meter", "sqm", "studio", "townhouse", "unit", "villa", "wasalt",
})
_INTRODUCTION = re.compile(r"^(?:my name is|call me)\s+(?P<name>[\w][\w' -]{0,48})$", re.IGNORECASE)


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
        conversation_reply = _conversation_reply(question)
        if conversation_reply:
            self._conversations.append(conversation_id, "user", question)
            self._conversations.append(conversation_id, "assistant", conversation_reply)
            return ChatResult(conversation_id, conversation_reply, [], 0)

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


def _conversation_reply(message: str) -> str | None:
    """Respond warmly to conversation without inventing property information.

    Only questions that are plausibly about real estate reach retrieval. This
    keeps a source-grounded answer for domain questions with missing evidence,
    while preventing conversational or unrelated messages from receiving an
    impersonal RAG fallback.
    """
    cleaned = " ".join(message.split()).strip(" .,!?")
    normalized = cleaned.casefold()
    if normalized in _ACKNOWLEDGEMENTS:
        return f"You're welcome. {_SCOPE_INVITATION}"
    if normalized in _GREETINGS:
        return f"Hello! {_SCOPE_INVITATION}"
    introduction = _INTRODUCTION.fullmatch(cleaned)
    if introduction:
        name = introduction.group("name").strip().title()
        return f"Nice to meet you, {name}. {_SCOPE_INVITATION}"
    if not any(term in normalized for term in _REAL_ESTATE_TERMS):
        return (
            "I'm focused on source-grounded real-estate research for DarGlobal and Wasalt, "
            "so I can't help with that topic directly. "
            f"{_SCOPE_INVITATION}"
        )
    return None


_SCOPE_INVITATION = (
    "I'm here to help with publicly indexed project, location, amenity, and published-price information."
)
