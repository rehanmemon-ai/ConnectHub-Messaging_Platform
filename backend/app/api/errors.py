import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import request_id_context

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        details: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []
        self.headers = headers or {}


def error_content(error: ApiError) -> dict[str, Any]:
    return {
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details,
            "request_id": request_id_context.get(),
        }
    }


async def api_error_handler(_: Request, error: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content=error_content(error),
        headers=error.headers,
    )


async def validation_error_handler(_: Request, error: RequestValidationError) -> JSONResponse:
    details: list[dict[str, Any]] = []
    for item in error.errors():
        location = [str(part) for part in item.get("loc", ()) if part != "body"]
        details.append(
            {
                "field": ".".join(location),
                "code": str(item.get("type", "invalid")),
                "message": str(item.get("msg", "Invalid value.")),
            }
        )
    api_error = ApiError(
        422, "validation_error", "The request contains invalid values.", details=details
    )
    return await api_error_handler(_, api_error)


async def unexpected_error_handler(_: Request, error: Exception) -> JSONResponse:
    logger.exception("Unexpected API error", exc_info=error)
    return await api_error_handler(
        _, ApiError(500, "internal_error", "An unexpected error occurred.")
    )
