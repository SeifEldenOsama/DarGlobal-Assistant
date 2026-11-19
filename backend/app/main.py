from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routes import router as v1_router
from app.container import AppContainer
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.container = AppContainer.build(settings)
    structlog.get_logger().info("application_started", environment=settings.app_env)
    yield
    structlog.get_logger().info("application_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="DarGlobal & Wasalt Real Estate Assistant API", version="1.0.0",
        description="Grounded real-estate answers with public-source citations.", lifespan=lifespan,
    )
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
        allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.request_max_bytes:
            return JSONResponse(status_code=413, content={"error": {"code": "request_too_large", "message": "Request body is too large."}})
        request_id = request.headers.get("x-request-id", str(uuid4()))
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        structlog.get_logger().info(
            "request_completed", request_id=request_id, method=request.method, path=request.url.path,
            status_code=response.status_code, duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return response

    @app.exception_handler(AppError)
    async def handled_error(_: Request, error: AppError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"error": {"code": error.code, "message": error.message}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "Invalid request.", "details": error.errors()}})

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, error: Exception) -> JSONResponse:
        structlog.get_logger().exception("unexpected_error", error_type=type(error).__name__)
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "An unexpected error occurred."}})

    app.include_router(v1_router, prefix="/api/v1")
    return app


app = create_app()
