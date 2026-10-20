from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorOut(BaseModel):
    """Единый формат ошибок API (кроме 422 валидации FastAPI)."""

    error: ErrorBody


class APIError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def not_found(what: str) -> APIError:
    return APIError(status.HTTP_404_NOT_FOUND, "not_found", f"{what} не найден")


def not_implemented(stage: str) -> APIError:
    return APIError(
        status.HTTP_501_NOT_IMPLEMENTED,
        "not_implemented",
        f"Контракт зафиксирован, реализация — {stage}",
        details={"planned_stage": stage},
    )


# Описания задаются явно: фразы http.HTTPStatus различаются между версиями Python
# (413 в 3.13 — «Content Too Large»), а контракт не должен от этого зависеть.
ERROR_DESCRIPTIONS = {
    400: "Некорректный запрос",
    401: "Нужна авторизация",
    404: "Объект не найден",
    409: "Конфликт с уже выполненным запросом",
    413: "Файл слишком большой",
    501: "Контракт зафиксирован, реализация на следующем этапе",
}


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    return {
        code: {"model": ErrorOut, "description": ERROR_DESCRIPTIONS.get(code, "Ошибка")}
        for code in codes
    }


async def _handle_api_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, APIError)  # noqa: S101 — регистрируется только для APIError
    body = ErrorOut(error=ErrorBody(code=exc.code, message=exc.message, details=exc.details))
    return JSONResponse(
        status_code=exc.status_code,
        content=body.model_dump(exclude_none=True),
        headers=exc.headers,
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(APIError, _handle_api_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)


async def _handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    # FastAPI's default response can echo a full CSV, token, or arbitrary input.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": error["loc"], "type": error["type"], "msg": "Некорректное значение"}
                for error in exc.errors()
            ]
        },
    )
