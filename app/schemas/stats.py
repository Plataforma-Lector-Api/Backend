from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryInfo(BaseModel):
    number: int
    name: str
    description: str
    method: str
    endpoint: str
    operators: list[str] = Field(default_factory=list)
    index: str


class DashboardResponse(BaseModel):
    totals: dict[str, int]
    average_rating: float
    users_per_month: list[dict[str, Any]]
    contents_per_type: list[dict[str, Any]]
    top_tags: list[dict[str, Any]]
    top_contents: list[dict[str, Any]]
    recent_reviews: list[dict[str, Any]]
