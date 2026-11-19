from __future__ import annotations

import re
from dataclasses import dataclass

from app.application.services.prompts import SYSTEM_PROMPT, build_user_prompt
from app.domain.entities import Citation, ChatTurn
from app.domain.ports import ConversationStore, LanguageModel, VectorStore

_ACKNOWLEDGEMENT_WORDS = frozenset({
    "all", "alright", "awesome", "good", "got", "great", "helpful", "it", "much",
    "nice", "okay", "ok", "perfect", "really", "right", "so", "sounds", "sure",
    "thank", "thanks", "that", "thats", "the", "understood", "very", "was", "well",
    "you",
})
_ACKNOWLEDGEMENT_POSITIVE_WORDS = frozenset({"good", "great", "helpful", "nice", "perfect", "awesome"})
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
    normalized = _normalize_conversation_text(cleaned)
    if _is_acknowledgement(normalized):
        if "thank" in normalized or "thanks" in normalized:
            return f"You're welcome! {_SCOPE_INVITATION}"
        if _ACKNOWLEDGEMENT_POSITIVE_WORDS.intersection(normalized.split()):
            return f"Glad to hear it! {_SCOPE_INVITATION}"
        return f"Of course. {_SCOPE_INVITATION}"
    if normalized in _GREETINGS:
        return f"Hello! {_SCOPE_INVITATION}"
    introduction = _INTRODUCTION.fullmatch(cleaned)
    if introduction:
        name = introduction.group("name").strip().title()
        return f"Nice to meet you, {name}. {_SCOPE_INVITATION}"
    if not any(term in normalized for term in _REAL_ESTATE_TERMS):
        if _is_unrelated_request(cleaned):
            return (
                "I'd be happy to help where I can, but I can't help with that topic directly. "
                "My role here is to share information grounded in DarGlobal and Wasalt's public "
                "real-estate sources, such as their projects, locations, amenities, and published prices."
            )
        return (
            "Thanks for sharing that. Whenever you'd like, I'd be glad to help you explore "
            "DarGlobal and Wasalt projects, locations, amenities, or publicly listed prices."
        )
    return None


def _normalize_conversation_text(message: str) -> str:
    normalized = message.casefold().replace("'", "").replace("’", "")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", normalized).split())


def _is_acknowledgement(normalized: str) -> bool:
    words = normalized.split()
    return bool(words) and len(words) <= 8 and set(words).issubset(_ACKNOWLEDGEMENT_WORDS)


def _is_unrelated_request(message: str) -> bool:
    normalized = message.casefold().strip()
    request_starters = (
        "can you ", "could you ", "would you ", "how do i ", "how can i ",
        "what is ", "what are ", "tell me ", "write ", "make ", "give me ",
        "explain ", "help me ",
    )
    return "?" in message or normalized.startswith(request_starters)


_SCOPE_INVITATION = (
    "I'm here to help with publicly indexed project, location, amenity, and published-price information."
)
