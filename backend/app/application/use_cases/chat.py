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
_GREETINGS = frozenset({"hello", "hi", "hey", "good morning", "good afternoon", "good evening", "howdy", "greetings"})
_HOW_ARE_YOU = frozenset({
    "how are you", "how are you doing", "how are things", "how is it going",
    "hows it going", "how are you today", "how do you do", "how have you been",
})
_IDENTITY_QUERIES = frozenset({
    "who are you", "what are you", "what can you do", "what do you do",
    "tell me about yourself", "what is atlas", "who is atlas",
})
_REAL_ESTATE_TERMS = frozenset({
    "aida", "amenities", "amenity", "apartment", "atlas", "bathroom", "bedroom", "buy",
    "community", "completion", "compound", "cost", "dar global", "darglobal", "developer",
    "district", "dubai", "estate", "floor", "golf", "handover", "home", "house", "invest",
    "investing", "investment", "jeddah", "lease", "listing", "location", "luxury", "mansion",
    "muscat", "neighborhood", "ocean", "oman", "payment", "penthouse", "pool", "price",
    "project", "property", "qatar", "real estate", "rent", "residence", "residences",
    "riyadh", "sale", "saudi", "sea", "sell", "square meter", "sqm", "studio", "tower",
    "townhouse", "unit", "view", "villa", "wasalt",
})
_INTRODUCTION = re.compile(r"^(?:my name is|call me)\s+(?P<name>[\w][\w' -]{0,48})$", re.IGNORECASE)


def sanitize_response_text(text: str) -> str:
    if not text:
        return ""
    # Strip opening RAG meta-phrases
    meta_patterns = [
        r"^(?:Based on the (?:provided|supplied|indexed|available) (?:sources|context|information|documents|records),?\s*)+",
        r"^(?:According to the (?:provided|supplied|indexed|available) (?:sources|context|information|documents|records),?\s*)+",
        r"^(?:From the (?:provided|supplied|indexed) (?:sources|context|documents|records),?\s*)+",
        r"^(?:As per the (?:provided|supplied|indexed) (?:sources|context|documents|records),?\s*)+",
    ]
    for pattern in meta_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Clean out quadruple or multiple asterisks (e.g. **** or ***)
    text = re.sub(r"\*{3,}", "", text)

    # Clean double asterisks used for bold headers to keep plain text clean in UI
    text = re.sub(r"\*\*([^\*\n]+)\*\*", r"\1", text)
    text = re.sub(r"\*{2,}", "", text)

    # Capitalize first character if needed
    stripped = text.strip()
    if stripped and stripped[0].islower():
        stripped = stripped[0].upper() + stripped[1:]
    return stripped


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
            answer = (
                "I couldn't find verified public details for that specific request in our records right now. "
                "I'm here to help you explore DarGlobal and Wasalt luxury developments, properties, locations, "
                "amenities, and published pricing. Please feel free to ask about any specific project or location!"
            )
            self._conversations.append(conversation_id, "user", question)
            self._conversations.append(conversation_id, "assistant", answer)
            return ChatResult(conversation_id, answer, [], 0)

        history = self._conversations.history(conversation_id, self._history_limit)
        prompt = build_user_prompt(question, history, retrieved)
        raw_answer = await self._llm.generate(SYSTEM_PROMPT, prompt)
        answer = sanitize_response_text(raw_answer)
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

    def delete(self, conversation_id: str) -> None:
        self._conversations.delete(conversation_id)


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
        return f"Hello! It's a pleasure to connect with you. {_SCOPE_INVITATION}"
    if normalized in _HOW_ARE_YOU:
        return f"I'm doing wonderfully, thank you for asking! {_SCOPE_INVITATION}"
    if normalized in _IDENTITY_QUERIES:
        return f"I am Atlas, your luxury real estate assistant. {_SCOPE_INVITATION}"
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
            "I'd be delighted to assist you! Whenever you'd like, I'm here to help you explore "
            "DarGlobal and Wasalt projects, locations, amenities, and published prices. What would you like to explore?"
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
    "I'm here to assist you with exploring luxury properties, developments, locations, amenities, and published pricing. How can I assist you today?"
)
