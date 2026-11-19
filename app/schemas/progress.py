from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.content import ContentPublic


class ProgressUpdate(BaseModel):
    current_page: int = Field(ge=1)
    total_pages: int = Field(ge=1)
    percentage: float | None = Field(default=None, ge=0, le=100)
    location: str | None = Field(
        default=None,
        max_length=500,
        description="CFI de EPUB para reanudar la lectura en el punto exacto.",
    )


class ProgressPublic(BaseModel):
    content_id: str
    current_page: int
    total_pages: int
    percentage: float
    location: str | None = None
    updated_at: datetime | None = None
    content: ContentPublic | None = None
