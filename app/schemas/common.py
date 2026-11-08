from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageMeta(BaseModel):
    page: int = Field(ge=1)
    limit: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class Page(BaseModel, Generic[T]):  # noqa: UP046
    data: list[T]
    meta: PageMeta


class Message(BaseModel):
    message: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
