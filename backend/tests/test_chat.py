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


class EmptyVectors:
    def query(self, *_):
        return []


class NoCallLlm:
    async def generate(self, *_):
        raise AssertionError("The model must not be called when nothing was retrieved")


@pytest.mark.asyncio
async def test_chat_refuses_to_answer_without_grounded_context() -> None:
    conversations = MemoryConversations()
    use_case = AnswerQuestion(EmptyVectors(), NoCallLlm(), conversations, 5, 0.4, 6)
    result = await use_case.execute("abc", "What is the price?")
    assert result.citations == []
    assert "couldn't find" in result.answer
    assert len(conversations.items) == 2


@pytest.mark.asyncio
async def test_openrouter_missing_key_is_configuration_error() -> None:
    model = OpenRouterLanguageModel(None, "openrouter/free", 5)
    with pytest.raises(ConfigurationError):
        await model.generate("system", "question")
