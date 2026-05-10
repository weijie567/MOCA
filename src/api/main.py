from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routers import auth, orders, refund_cases, tickets
from src.api.schemas.common import ApiResponse, ErrorDetail, FORBIDDEN, INTERNAL_ERROR, UNAUTHORIZED, VALIDATION_ERROR
from src.config import settings
from src.db.session import get_session


async def _session_context() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


def _error_response(request: Request, status_code: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    response = ApiResponse(
        success=False,
        error=ErrorDetail(code=code, message=message, details=details or {}),
        trace_id=getattr(request.state, "trace_id", None),
    )
    return JSONResponse(status_code=status_code, content=response.model_dump(mode="json"))


def create_app() -> FastAPI:
    app = FastAPI(title=settings.project_name, version=settings.project_version)

    @app.middleware("http")
    async def trace_middleware(request: Request, call_next):
        request.state.trace_id = str(uuid.uuid4())
        request.state.run_id = str(uuid.uuid4())
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Trace-Id"] = request.state.trace_id
        response.headers["X-Run-Id"] = request.state.run_id
        response.headers["X-Latency-Ms"] = str(round((time.perf_counter() - start) * 1000))
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            detail = exc.detail
        elif exc.status_code == 401:
            detail = {"code": UNAUTHORIZED, "message": str(exc.detail)}
        elif exc.status_code == 403:
            detail = {"code": FORBIDDEN, "message": str(exc.detail)}
        else:
            detail = {"code": INTERNAL_ERROR, "message": str(exc.detail)}
        return _error_response(
            request,
            exc.status_code,
            detail.get("code", INTERNAL_ERROR),
            detail.get("message", "Request failed"),
            detail.get("details"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            request,
            422,
            VALIDATION_ERROR,
            "Validation failed",
            {"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return _error_response(request, 500, INTERNAL_ERROR, "Internal server error", {"reason": str(exc)})

    @app.get("/health", response_model=ApiResponse)
    async def health(request: Request, session: AsyncSession = Depends(get_session)) -> ApiResponse:
        await session.execute(text("SELECT 1"))
        return ApiResponse(
            success=True,
            data={"status": "healthy", "database": "connected"},
            trace_id=request.state.trace_id,
        )

    app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth")
    app.include_router(orders.router, prefix=f"{settings.api_v1_prefix}/orders")
    app.include_router(refund_cases.router, prefix=f"{settings.api_v1_prefix}/refund-cases")
    app.include_router(tickets.router, prefix=f"{settings.api_v1_prefix}/tickets")
    return app


app = create_app()
