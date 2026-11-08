from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.utils.mongo import aggregate
from app.utils.serializers import to_object_id


class ProgressRepository:
    def __init__(self, db: AsyncDatabase) -> None:
        self.collection = db.reading_progress

    async def upsert(
        self,
        *,
        user_id: str | ObjectId,
        content_id: str | ObjectId,
        current_page: int,
        total_pages: int,
        percentage: float,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        result = await self.collection.find_one_and_update(
            {
                "user_id": to_object_id(user_id),
                "content_id": to_object_id(content_id),
            },
            {
                "$set": {
                    "current_page": current_page,
                    "total_pages": total_pages,
                    "percentage": round(percentage, 1),
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return result

    async def get(
        self,
        *,
        user_id: str | ObjectId,
        content_id: str | ObjectId,
    ) -> dict[str, Any] | None:
        return await self.collection.find_one(
            {
                "user_id": to_object_id(user_id),
                "content_id": to_object_id(content_id),
            }
        )

    async def list_for_user(
        self,
        *,
        user_id: str | ObjectId,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        pipeline = [
            {"$match": {"user_id": to_object_id(user_id)}},
            {"$sort": {"updated_at": -1}},
            {"$limit": limit},
            {
                "$lookup": {
                    "from": "contents",
                    "localField": "content_id",
                    "foreignField": "_id",
                    "as": "content",
                }
            },
            {"$unwind": "$content"},
            {
                "$project": {
                    "_id": 0,
                    "content_id": 1,
                    "current_page": 1,
                    "total_pages": 1,
                    "percentage": 1,
                    "updated_at": 1,
                    "content": "$content",
                }
            },
        ]
        return await aggregate(self.collection, pipeline, length=limit)
