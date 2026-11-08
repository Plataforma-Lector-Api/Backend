from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.content import ContentPublic


class LibraryItem(BaseModel):
    added_at: datetime
    content: ContentPublic


class RecommendationItem(ContentPublic):
    match_score: int = 0
