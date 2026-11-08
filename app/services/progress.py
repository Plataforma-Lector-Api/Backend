from __future__ import annotations

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.core.exceptions import AppError
from app.repositories.collections import CollectionRepository
from app.repositories.contents import ContentRepository
from app.repositories.progress import ProgressRepository
from app.schemas.progress import ProgressUpdate
from app.services.decorators import decorate_content
from app.utils.serializers import serialize_doc


class ProgressService:
    def __init__(self, db: AsyncDatabase) -> None:
        self.progress = ProgressRepository(db)
        self.contents = ContentRepository(db)
        self.collections = CollectionRepository(db)

    async def upsert(
        self,
        *,
        user_id: str,
        content_id: str,
        data: ProgressUpdate,
    ) -> dict[str, Any]:
        content = await self.contents.find_by_id(content_id)
        if content is None:
            raise AppError(404, "CONTENT_NOT_FOUND", "El contenido no existe")

        percentage = data.percentage
        if percentage is None:
            percentage = min(100.0, round((data.current_page / data.total_pages) * 100, 1))

        document = await self.progress.upsert(
            user_id=user_id,
            content_id=content_id,
            current_page=data.current_page,
            total_pages=data.total_pages,
            percentage=percentage,
        )
        return serialize_doc(document)

    async def get(self, *, user_id: str, content_id: str) -> dict[str, Any] | None:
        document = await self.progress.get(user_id=user_id, content_id=content_id)
        return serialize_doc(document) if document else None

    async def list(self, *, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        documents = await self.progress.list_for_user(user_id=user_id, limit=limit)
        result: list[dict[str, Any]] = []
        for document in documents:
            content = await decorate_content(document["content"], self.collections, user_id)
            result.append(
                {
                    "content_id": str(document["content_id"]),
                    "current_page": document["current_page"],
                    "total_pages": document["total_pages"],
                    "percentage": document["percentage"],
                    "updated_at": document["updated_at"],
                    "content": content,
                }
            )
        return result
