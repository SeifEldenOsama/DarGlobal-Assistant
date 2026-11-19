from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request

from app.application.use_cases.chat import AnswerQuestion
from app.container import AppContainer
from app.schemas.catalog import ProjectsResponse, SourcesResponse
from app.schemas.chat import ChatRequest, ChatResponse, CitationResponse, ConversationResponse, ConversationTurnResponse

router = APIRouter()


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


@router.get("/health", tags=["operations"])
def health(container: AppContainer = Depends(get_container)) -> dict[str, object]:
    return {"status": "ok", "vector_store": container.vectors.health(), "environment": container.settings.app_env}


@router.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(payload: ChatRequest, container: AppContainer = Depends(get_container)) -> ChatResponse:
    conversation_id = payload.conversation_id or uuid4()
    result = await container.chat_use_case().execute(str(conversation_id), payload.question)
    return ChatResponse(
        conversation_id=conversation_id, answer=result.answer,
        sources=[CitationResponse(
            label=citation.label, title=citation.title, source_name=citation.source_name,
            source_url=citation.source_url, snippet=citation.snippet,
        ) for citation in result.citations],
        retrieved_count=result.retrieved_count,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse, tags=["chat"])
def conversation(conversation_id: UUID, container: AppContainer = Depends(get_container)) -> ConversationResponse:
    history = container.chat_use_case().history(str(conversation_id))
    return ConversationResponse(
        conversation_id=conversation_id,
        messages=[ConversationTurnResponse(role=item.role, content=item.content, created_at=item.created_at) for item in history],
    )


@router.get("/sources", response_model=SourcesResponse, tags=["catalog"])
def sources(container: AppContainer = Depends(get_container)) -> SourcesResponse:
    statistics = container.vectors.source_statistics()
    return SourcesResponse(sources=statistics, total_chunks=sum(int(item["chunk_count"]) for item in statistics))


@router.get("/projects", response_model=ProjectsResponse, tags=["catalog"])
def projects(container: AppContainer = Depends(get_container)) -> ProjectsResponse:
    return ProjectsResponse(projects=container.vectors.projects(limit=50))
