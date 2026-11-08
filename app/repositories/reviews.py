from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.utils.mongo import aggregate
from app.utils.serializers import to_object_id


class ReviewRepository:
    def __init__(self, db: AsyncDatabase) -> None:
        self.collection = db.reviews

    async def upsert(
        self,
        *,
        user_id: str | ObjectId,
        content_id: str | ObjectId,
        rating: int,
        comment: str | None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        result = await self.collection.find_one_and_update(
            {
                "user_id": to_object_id(user_id),
                "content_id": to_object_id(content_id),
            },
            {
                "$set": {
                    "rating": rating,
                    "comment": comment,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return result

    async def list_for_content(
        self,
        *,
        content_id: str | ObjectId,
        page: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        pipeline = [
            {"$match": {"content_id": to_object_id(content_id)}},
            {"$sort": {"created_at": -1}},
            {
                "$facet": {
                    "data": [
                        {"$skip": (page - 1) * limit},
                        {"$limit": limit},
                        {
                            "$lookup": {
                                "from": "users",
                                "localField": "user_id",
                                "foreignField": "_id",
                                "as": "user",
                            }
                        },
                        {
                            "$unwind": {
                                "path": "$user",
                                "preserveNullAndEmptyArrays": True,
                            }
                        },
                        {
                            "$project": {
                                "_id": 1,
                                "user_id": 1,
                                "content_id": 1,
                                "rating": 1,
                                "comment": 1,
                                "created_at": 1,
                                "updated_at": 1,
                                "user_name": "$user.name",
                            }
                        },
                    ],
                    "meta": [{"$count": "total"}],
                }
            },
        ]
        result = await aggregate(self.collection, pipeline, length=1)
        if not result:
            return [], 0
        facet = result[0]
        total = facet["meta"][0]["total"] if facet["meta"] else 0
        return facet["data"], total

    async def recompute_content_rating(self, content_id: str | ObjectId) -> tuple[float, int]:
        pipeline = [
            {"$match": {"content_id": to_object_id(content_id)}},
            {
                "$group": {
                    "_id": None,
                    "avg_rating": {"$avg": "$rating"},
                    "review_count": {"$sum": 1},
                }
            },
        ]
        result = await aggregate(self.collection, pipeline, length=1)
        if not result:
            return 0.0, 0
        return round(float(result[0]["avg_rating"]), 2), int(result[0]["review_count"])

    async def delete(self, *, user_id: str | ObjectId, content_id: str | ObjectId) -> bool:
        result = await self.collection.delete_one(
            {
                "user_id": to_object_id(user_id),
                "content_id": to_object_id(content_id),
            }
        )
        return result.deleted_count > 0

    async def count(self) -> int:
        return await self.collection.count_documents({})

    async def average_rating(self) -> float:
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "avg_rating": {"$avg": "$rating"},
                }
            }
        ]
        result = await aggregate(self.collection, pipeline, length=1)
        if not result:
            return 0.0
        return round(float(result[0]["avg_rating"]), 2)

    async def recent(self, limit: int = 5) -> list[dict[str, Any]]:
        pipeline = [
            {"$sort": {"created_at": -1}},
            {"$limit": limit},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "user_id",
                    "foreignField": "_id",
                    "as": "user",
                }
            },
            {
                "$lookup": {
                    "from": "contents",
                    "localField": "content_id",
                    "foreignField": "_id",
                    "as": "content",
                }
            },
            {
                "$unwind": {
                    "path": "$user",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$unwind": {
                    "path": "$content",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "rating": 1,
                    "comment": 1,
                    "created_at": 1,
                    "user_name": "$user.name",
                    "content_title": "$content.title",
                }
            },
        ]
        return await aggregate(self.collection, pipeline, length=limit)
