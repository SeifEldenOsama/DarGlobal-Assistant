from datetime import datetime, timezone

import pytest

from app.application.use_cases.chat import AnswerQuestion
from app.core.errors import ConfigurationError
from app.domain.entities import DocumentChunk, RetrievedChunk
from app.infrastructure.llm.openrouter import OpenRouterLanguageModel


class MemoryConversations:
    def __init__(self):
        self.items = []

    def history(self, _, __):
        return []

    def append(self, conversation_id, role, content):
        self.items.append((conversation_id, role, content))

    def delete(self, conversation_id):
        self.items = [(cid, r, c) for cid, r, c in self.items if cid != conversation_id]


class EmptyVectors:
    def __init__(self):
        self.calls = 0

    def query(self, *_):
        self.calls += 1
        return []


class NoCallLlm:
    async def generate(self, *_):
        raise AssertionError("The model must not be called when nothing was retrieved")


@pytest.mark.asyncio
async def test_chat_refuses_to_answer_without_grounded_context() -> None:
    conversations = MemoryConversations()
    vectors = EmptyVectors()
    use_case = AnswerQuestion(vectors, NoCallLlm(), conversations, 5, 0.4, 6)
    result = await use_case.execute("abc", "What is the price?")
    assert result.citations == []
    assert "couldn't find" in result.answer
    assert vectors.calls == 1
    assert len(conversations.items) == 2


@pytest.mark.asyncio
async def test_chat_acknowledgement_skips_retrieval_and_returns_a_courteous_reply() -> None:
    conversations = MemoryConversations()
    vectors = EmptyVectors()
    use_case = AnswerQuestion(vectors, NoCallLlm(), conversations, 5, 0.4, 6)

    result = await use_case.execute("abc", "okay thanks")

    assert result.citations == []
    assert result.retrieved_count == 0
    assert result.answer.startswith("You're welcome")
    assert vectors.calls == 0
    assert conversations.items == [
        ("abc", "user", "okay thanks"),
        ("abc", "assistant", result.answer),
    ]


@pytest.mark.asyncio
async def test_chat_personal_introduction_is_welcomed_without_retrieval() -> None:
    conversations = MemoryConversations()
    vectors = EmptyVectors()
    use_case = AnswerQuestion(vectors, NoCallLlm(), conversations, 5, 0.4, 6)

    result = await use_case.execute("abc", "my name is seif")

    assert result.answer.startswith("Nice to meet you, Seif.")
    assert "DarGlobal and Wasalt" not in result.answer
    assert vectors.calls == 0
    assert result.citations == []


@pytest.mark.asyncio
async def test_chat_kindly_redirects_an_out_of_scope_request_without_retrieval() -> None:
    conversations = MemoryConversations()
    vectors = EmptyVectors()
    use_case = AnswerQuestion(vectors, NoCallLlm(), conversations, 5, 0.4, 6)

    result = await use_case.execute("abc", "Can you write Python code for me?")

    assert "can't help with that topic directly" in result.answer
    assert "DarGlobal and Wasalt" in result.answer
    assert vectors.calls == 0
    assert result.citations == []


@pytest.mark.asyncio
async def test_chat_general_conversations_are_warm_and_inviting() -> None:
    conversations = MemoryConversations()
    vectors = EmptyVectors()
    use_case = AnswerQuestion(vectors, NoCallLlm(), conversations, 5, 0.4, 6)

    result_how = await use_case.execute("abc", "How are you?")
    assert "doing wonderfully" in result_how.answer
    assert "I'm here to assist you" in result_how.answer
    assert vectors.calls == 0

    result_who = await use_case.execute("abc", "Who are you?")
    assert "I am Atlas" in result_who.answer
    assert vectors.calls == 0


def test_sanitize_response_text_removes_rag_phrases_and_asterisks() -> None:
    from app.application.use_cases.chat import sanitize_response_text

    raw = "Based on the provided sources, the amenities for AIDA include:\n\n****Features:****\n- **Golf course** [S1]"
    cleaned = sanitize_response_text(raw)
    assert not cleaned.startswith("Based on the provided sources")
    assert cleaned.startswith("The amenities for AIDA include:")
    assert "****" not in cleaned
    assert "**" not in cleaned
    assert "[S1]" in cleaned


@pytest.mark.asyncio
async def test_openrouter_missing_key_is_configuration_error() -> None:
    model = OpenRouterLanguageModel(None, "openrouter/free", 5)
    with pytest.raises(ConfigurationError):
        await model.generate("system", "question")
