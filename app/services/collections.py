from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.repositories.collections import CollectionRepository
from app.repositories.contents import ContentRepository
from app.services.decorators import decorate_content, decorate_many


class CollectionService:
    def __init__(self, db: AsyncDatabase) -> None:
        self.collections = CollectionRepository(db)
        self.contents = ContentRepository(db)

    async def add(self, *, user_id: str, content_id: str) -> None:
        content = await self.contents.find_by_id(content_id)
        if content is None or content.get("status") != "published":
            from app.core.exceptions import AppError

            raise AppError(404, "CONTENT_NOT_FOUND", "El contenido no existe")
        await self.collections.add(user_id, content_id)
        await self.contents.increment_popularity(content_id, 1)

    async def remove(self, *, user_id: str, content_id: str) -> bool:
        removed = await self.collections.remove(user_id, content_id)
        if removed:
            await self.contents.increment_popularity(content_id, -1)
        return removed

    async def list(
        self,
        *,
        user_id: str,
        page: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        documents, total = await self.collections.list_for_user(
            user_id=user_id,
            page=page,
            limit=limit,
        )
        items: list[dict[str, Any]] = []
        for document in documents:
            content = await decorate_content(document["content"], self.collections, user_id)
            added_at: datetime = document["added_at"]
            items.append({"added_at": added_at, "content": content})
        return items, total

    async def recommendations(
        self,
        *,
        user_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        documents = await self.collections.recommendations(user_id=user_id, limit=limit)
        if not documents:
            saved_ids = await self.collections.saved_ids(user_id)
            popular = await self.contents.popular(limit + len(saved_ids))
            documents = [document for document in popular if str(document["_id"]) not in saved_ids][
                :limit
            ]
        return await decorate_many(documents, self.collections, user_id)

    async def saved_ids(self, user_id: str) -> set[str]:
        return await self.collections.saved_ids(user_id)
