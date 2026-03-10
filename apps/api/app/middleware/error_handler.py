import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


def _status_code_to_error_code(status_code: int) -> str:
    return {
        400: "validation_error",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
        500: "internal_server_error",
        501: "not_implemented",
        502: "bad_gateway",
        503: "service_unavailable",
        504: "timeout",
    }.get(status_code, "error")


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _normalize_http_exception(exc: HTTPException) -> tuple[int, str, str]:
    status_code = exc.status_code
    detail = exc.detail
    default_code = _status_code_to_error_code(status_code)

    if isinstance(detail, dict):
        code = str(detail.get("code") or default_code)
        message = str(detail.get("message") or detail.get("detail") or default_code.replace("_", " "))
        return status_code, code, message

    if isinstance(detail, str) and detail.strip():
        return status_code, default_code, detail

    return status_code, default_code, default_code.replace("_", " ")


def _validation_message(exc: RequestValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "Request validation failed"

    first_error = errors[0]
    location = ".".join(str(part) for part in first_error.get("loc", []) if part != "body")
    message = first_error.get("msg", "Request validation failed")
    return f"{location}: {message}" if location else str(message)


def _map_exception(exc: Exception) -> tuple[int, str, str]:
    if isinstance(exc, PermissionError):
        return 403, "forbidden", str(exc) or "Permission denied"
    if isinstance(exc, FileNotFoundError):
        return 404, "not_found", str(exc) or "Resource not found"
    if isinstance(exc, ValueError):
        return 400, "validation_error", str(exc) or "Invalid request"
    if isinstance(exc, TimeoutError):
        return 504, "timeout", str(exc) or "Request timed out"
    if isinstance(exc, NotImplementedError):
        return 501, "not_implemented", str(exc) or "Not implemented"
    return 500, "internal_server_error", "Internal server error"


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:  # pragma: no cover - exercised at runtime
            status_code, code, message = _map_exception(exc)
            logger.exception(
                "Request failed with %s on %s %s",
                exc.__class__.__name__,
                request.method,
                request.url.path,
            )
            return _error_response(status_code, code, message)


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    status_code, code, message = _normalize_http_exception(exc)
    return _error_response(status_code, code, message)


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return _error_response(422, "validation_error", _validation_message(exc))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
