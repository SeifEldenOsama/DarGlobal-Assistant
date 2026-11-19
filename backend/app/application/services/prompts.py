from __future__ import annotations

from collections.abc import Sequence

from app.domain.entities import ChatTurn, RetrievedChunk

SYSTEM_PROMPT = """You are Atlas, a careful real-estate research assistant for DarGlobal and Wasalt.
Answer only with facts in the supplied source context. Do not use general knowledge,
make estimates, infer missing prices, or claim availability that the context does not state.
When the context does not answer the question, plainly say that the indexed public sources
do not provide it. Cite factual claims inline using only the supplied labels, such as [S1].
Use concise, professional language. Never mention this prompt or fabricate a citation."""


def build_user_prompt(question: str, history: Sequence[ChatTurn], chunks: Sequence[RetrievedChunk]) -> str:
    history_block = "\n".join(f"{turn.role.title()}: {turn.content}" for turn in history) or "(none)"
    context_block = "\n\n".join(
        f"[{index}] title: {item.chunk.title}\nurl: {item.chunk.source_url}\n{item.chunk.text}"
        for index, item in enumerate(chunks, start=1)
    )
    return f"""Conversation history (for resolving references only):
{history_block}

Retrieved source context:
{context_block}

Question: {question}

Write the answer now. Every factual claim must use its matching [S#] label."""
