from __future__ import annotations

from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.core.exceptions import AppError
from app.repositories.contents import ContentRepository
from app.repositories.reviews import ReviewRepository
from app.schemas.review import ReviewCreate
from app.utils.serializers import serialize_doc, serialize_docs


class ReviewService:
    def __init__(self, db: AsyncDatabase) -> None:
        self.reviews = ReviewRepository(db)
        self.contents = ContentRepository(db)

    async def upsert(
        self,
        *,
        user_id: str,
        content_id: str,
        data: ReviewCreate,
    ) -> dict[str, Any]:
        content = await self.contents.find_by_id(content_id)
        if content is None or content.get("status") != "published":
            raise AppError(404, "CONTENT_NOT_FOUND", "El contenido no existe")

        review = await self.reviews.upsert(
            user_id=user_id,
            content_id=content_id,
            rating=data.rating,
            comment=data.comment,
        )
        await self._refresh_content_rating(content_id)
        return serialize_doc(review)

    async def list(
        self,
        *,
        content_id: str,
        page: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        content = await self.contents.find_by_id(content_id)
        if content is None:
            raise AppError(404, "CONTENT_NOT_FOUND", "El contenido no existe")
        documents, total = await self.reviews.list_for_content(
            content_id=content_id,
            page=page,
            limit=limit,
        )
        return serialize_docs(documents), total

    async def delete(self, *, user_id: str, content_id: str) -> None:
        deleted = await self.reviews.delete(user_id=user_id, content_id=content_id)
        if not deleted:
            raise AppError(404, "REVIEW_NOT_FOUND", "No tienes una reseña en este contenido")
        await self._refresh_content_rating(content_id)

    async def _refresh_content_rating(self, content_id: str) -> None:
        avg_rating, count = await self.reviews.recompute_content_rating(content_id)
        await self.contents.update_rating(content_id, avg_rating, count)
