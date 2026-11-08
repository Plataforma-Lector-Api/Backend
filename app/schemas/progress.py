from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.content import ContentPublic


class ProgressUpdate(BaseModel):
    current_page: int = Field(ge=1)
    total_pages: int = Field(ge=1)
    percentage: float | None = Field(default=None, ge=0, le=100)


class ProgressPublic(BaseModel):
    content_id: str
    current_page: int
    total_pages: int
    percentage: float
    updated_at: datetime | None = None
    content: ContentPublic | None = None
