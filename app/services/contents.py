from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from gridfs import AsyncGridFSBucket
from pymongo.asynchronous.database import AsyncDatabase

from app.core.exceptions import AppError
from app.repositories.collections import CollectionRepository
from app.repositories.contents import ContentRepository
from app.repositories.progress import ProgressRepository
from app.repositories.reviews import ReviewRepository
from app.schemas.content import ContentCreate, ContentUpdate
from app.services.decorators import decorate_content, decorate_many
from app.utils.serializers import to_object_id


def normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        clean = tag.strip().lower()
        if clean and clean not in seen:
            seen.add(clean)
            normalized.append(clean)
    return normalized[:10]


def to_datetime(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


class ContentService:
    def __init__(self, db: AsyncDatabase) -> None:
        self.db = db
        self.contents = ContentRepository(db)
        self.collections = CollectionRepository(db)
        self.reviews = ReviewRepository(db)
        self.progress = ProgressRepository(db)

    async def list(
        self,
        *,
        page: int,
        limit: int,
        tags: list[str] | None = None,
        content_type: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        language: str | None = None,
        status: str | None = "published",
        sort: str = "-created_at",
        user_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        documents, total = await self.contents.list_contents(
            page=page,
            limit=limit,
            tags=tags,
            content_type=content_type,
            year_from=year_from,
            year_to=year_to,
            language=language,
            status=None if status == "all" else status,
            sort=sort,
        )
        return await decorate_many(documents, self.collections, user_id), total

    async def search(
        self,
        *,
        query: str,
        page: int,
        limit: int,
        user_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        documents, total = await self.contents.search_text(
            query=query,
            page=page,
            limit=limit,
        )
        return await decorate_many(documents, self.collections, user_id), total

    async def popular(self, *, limit: int, user_id: str | None = None) -> list[dict[str, Any]]:
        documents = await self.contents.popular(limit)
        return await decorate_many(documents, self.collections, user_id)

    async def top_rated(
        self,
        *,
        min_reviews: int,
        limit: int,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        documents = await self.contents.top_rated(min_reviews=min_reviews, limit=limit)
        return await decorate_many(documents, self.collections, user_id)

    async def by_author(self, *, limit: int) -> list[dict[str, Any]]:
        return await self.contents.by_author(limit)

    async def tag_stats(self, *, limit: int) -> list[dict[str, Any]]:
        return await self.contents.tag_stats(limit)

    async def most_saved(
        self,
        *,
        limit: int,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        documents = await self.collections.most_saved(limit)
        result: list[dict[str, Any]] = []
        for document in documents:
            content = await decorate_content(document["content"], self.collections, user_id)
            result.append({"content": content, "saves": document["saves"]})
        return result

    async def get(
        self,
        content_id: str,
        *,
        user_id: str | None = None,
        include_unpublished: bool = False,
    ) -> dict[str, Any]:
        document = await self.contents.find_by_id(content_id)
        if document is None:
            raise AppError(404, "CONTENT_NOT_FOUND", "El contenido no existe")
        if document.get("status") != "published" and not include_unpublished:
            raise AppError(404, "CONTENT_NOT_FOUND", "El contenido no está publicado")
        return await decorate_content(document, self.collections, user_id)

    async def create(self, data: ContentCreate, *, user_id: str) -> dict[str, Any]:
        now = datetime.now(UTC)
        payload = data.model_dump()
        payload["tags"] = normalize_tags(payload.get("tags"))
        payload["published_at"] = to_datetime(payload.get("published_at"))
        payload.update(
            {
                "popularity": 0,
                "rating_avg": 0.0,
                "rating_count": 0,
                "file_id": None,
                "created_by": to_object_id(user_id),
                "created_at": now,
                "updated_at": now,
            }
        )
        content_id = await self.contents.create(payload)
        return await self.get(content_id, user_id=user_id, include_unpublished=True)

    async def update(
        self,
        content_id: str,
        data: ContentUpdate,
        *,
        user_id: str,
    ) -> dict[str, Any]:
        payload = data.model_dump(exclude_unset=True)
        if "tags" in payload:
            payload["tags"] = normalize_tags(payload["tags"])
        if "published_at" in payload:
            payload["published_at"] = to_datetime(payload["published_at"])
        document = await self.contents.update(content_id, payload)
        return await decorate_content(document, self.collections, user_id)

    async def delete(self, content_id: str) -> None:
        document = await self.contents.find_by_id(content_id)
        if document is None:
            raise AppError(404, "CONTENT_NOT_FOUND", "El contenido no existe")

        object_id = to_object_id(content_id)
        if document.get("file_id"):
            try:
                bucket = AsyncGridFSBucket(self.db, bucket_name="pdfs")
                await bucket.delete(document["file_id"])
            except Exception:
                pass

        await self.db.collections.delete_many({"content_id": object_id})
        await self.db.reviews.delete_many({"content_id": object_id})
        await self.db.reading_progress.delete_many({"content_id": object_id})
        await self.contents.delete(content_id)
