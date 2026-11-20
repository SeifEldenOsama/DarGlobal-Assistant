from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.routes import get_container, router


class FakeVectors:
    def health(self):
        return {"collection": "test", "chunk_count": 0}

    def source_statistics(self):
        return [{"source_name": "DarGlobal", "chunk_count": 2}]

    def projects(self, limit):
        return []


class FakeSettings:
    app_env = "test"


class FakeChatUseCase:
    def delete(self, conversation_id: str) -> None:
        pass


class FakeContainer:
    vectors = FakeVectors()
    settings = FakeSettings()

    def chat_use_case(self):
        return FakeChatUseCase()


def make_client() -> TestClient:
    app = FastAPI()
    app.state.container = FakeContainer()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_health_endpoint_reports_vector_status() -> None:
    response = make_client().get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["vector_store"]["chunk_count"] == 0


def test_chat_rejects_empty_question_before_service_execution() -> None:
    response = make_client().post("/api/v1/chat", json={"question": ""})
    assert response.status_code == 422


def test_delete_conversation_returns_no_content() -> None:
    import uuid
    conv_id = str(uuid.uuid4())
    response = make_client().delete(f"/api/v1/conversations/{conv_id}")
    assert response.status_code == 204
