"""Centralized HTTP error mapping. Never include secrets in responses."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger, redact
from app.services.qloo.client import QlooError

logger = get_logger(__name__)


def _error_body(*, code: str, message: str, details: dict | None = None) -> dict:
    payload: dict = {"error": {"code": code, "message": redact(message)}}
    if details:
        payload["error"]["details"] = details
    return payload


def _json_safe(value: Any) -> Any:
    """Make Pydantic/FastAPI error payloads JSON-serializable (no Exception objects)."""
    if isinstance(value, Exception):
        return {"type": type(value).__name__, "message": redact(str(value))}
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return redact(str(value))


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(QlooError)
    async def qloo_error_handler(_: Request, exc: QlooError) -> JSONResponse:
        status = exc.status_code or 502
        if status < 400 or status > 599:
            status = 502
        logger.warning("qloo_error status=%s message=%s", status, redact(str(exc)))
        return JSONResponse(
            status_code=status,
            content=_error_body(code="qloo_upstream", message=str(exc)),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=_error_body(code="validation", message=str(exc)),
        )

    @app.exception_handler(PermissionError)
    async def permission_error_handler(
        _: Request, exc: PermissionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content=_error_body(code="forbidden", message=str(exc)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_body(
                code="request_validation",
                message="Request validation failed",
                details={"issues": _json_safe(exc.errors())},
            ),
        )

    @app.exception_handler(SQLAlchemyError)
    async def db_error_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("database_error type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content=_error_body(
                code="database_unavailable",
                message="Database temporarily unavailable",
            ),
        )
