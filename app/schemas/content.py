from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

ContentType = Literal["book", "article", "thesis", "magazine", "other"]
ContentStatus = Literal["draft", "published", "archived"]


class ContentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=150)
    type: ContentType = "book"
    description: str = Field(default="", max_length=2000)
    cover_url: str | None = Field(default=None, max_length=500)
    external_url: str | None = Field(default=None, max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=10)
    language: str = Field(default="es", max_length=10)
    published_at: date | None = None
    status: ContentStatus = "published"


class ContentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    author: str | None = Field(default=None, min_length=1, max_length=150)
    type: ContentType | None = None
    description: str | None = Field(default=None, max_length=2000)
    cover_url: str | None = Field(default=None, max_length=500)
    external_url: str | None = Field(default=None, max_length=500)
    tags: list[str] | None = Field(default=None, max_length=10)
    language: str | None = Field(default=None, max_length=10)
    published_at: date | None = None
    status: ContentStatus | None = None


class ContentPublic(BaseModel):
    id: str
    title: str
    author: str
    type: str = "book"
    description: str = ""
    cover_url: str | None = None
    external_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    language: str = "es"
    published_at: datetime | date | None = None
    status: str = "published"
    popularity: int = 0
    rating_avg: float = 0
    rating_count: int = 0
    has_file: bool = False
    is_saved: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ContentSearchItem(ContentPublic):
    score: float = 0


class AuthorStat(BaseModel):
    author: str
    total: int
    avg_popularity: float
    titles: list[str] = Field(default_factory=list)


class TagStat(BaseModel):
    tag: str
    total: int
    avg_rating: float
    total_popularity: int


class MostSavedItem(BaseModel):
    content: ContentPublic
    saves: int


class FileMetadata(BaseModel):
    id: str
    filename: str
    content_type: str
    size: int
    upload_date: datetime | None = None
