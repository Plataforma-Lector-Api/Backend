from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewPublic(BaseModel):
    id: str
    user_id: str
    user_name: str | None = None
    content_id: str
    rating: int
    comment: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
