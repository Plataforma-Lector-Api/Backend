from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import AppError
from app.utils.mongo import aggregate
from app.utils.serializers import to_object_id


class CollectionRepository:
    def __init__(self, db: AsyncDatabase) -> None:
        self.collection = db.collections

    async def add(self, user_id: str | ObjectId, content_id: str | ObjectId) -> None:
        try:
            await self.collection.insert_one(
                {
                    "user_id": to_object_id(user_id),
                    "content_id": to_object_id(content_id),
                    "added_at": datetime.now(UTC),
                }
            )
        except DuplicateKeyError as exc:
            raise AppError(
                409,
                "ALREADY_SAVED",
                "El contenido ya está en tu biblioteca",
            ) from exc

    async def remove(self, user_id: str | ObjectId, content_id: str | ObjectId) -> bool:
        result = await self.collection.delete_one(
            {
                "user_id": to_object_id(user_id),
                "content_id": to_object_id(content_id),
            }
        )
        return result.deleted_count > 0

    async def exists(self, user_id: str | ObjectId, content_id: str | ObjectId) -> bool:
        document = await self.collection.find_one(
            {
                "user_id": to_object_id(user_id),
                "content_id": to_object_id(content_id),
            },
            {"_id": 1},
        )
        return document is not None

    async def saved_ids(self, user_id: str | ObjectId) -> set[str]:
        cursor = self.collection.find({"user_id": to_object_id(user_id)}, {"content_id": 1})
        return {str(document["content_id"]) async for document in cursor}

    async def list_for_user(
        self,
        *,
        user_id: str | ObjectId,
        page: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        pipeline = [
            {"$match": {"user_id": to_object_id(user_id)}},
            {"$sort": {"added_at": -1}},
            {
                "$facet": {
                    "data": [
                        {"$skip": (page - 1) * limit},
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
                                "added_at": 1,
                                "content": "$content",
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

    async def recommendations(
        self,
        *,
        user_id: str | ObjectId,
        limit: int,
    ) -> list[dict[str, Any]]:
        pipeline = [
            {"$match": {"user_id": to_object_id(user_id)}},
            {
                "$lookup": {
                    "from": "contents",
                    "localField": "content_id",
                    "foreignField": "_id",
                    "as": "saved_content",
                }
            },
            {"$unwind": "$saved_content"},
            {
                "$group": {
                    "_id": None,
                    "saved_ids": {"$addToSet": "$content_id"},
                    "tags": {"$addToSet": "$saved_content.tags"},
                }
            },
            {
                "$project": {
                    "saved_ids": 1,
                    "tags": {
                        "$reduce": {
                            "input": "$tags",
                            "initialValue": [],
                            "in": {"$setUnion": ["$$value", "$$this"]},
                        }
                    },
                }
            },
            {
                "$lookup": {
                    "from": "contents",
                    "let": {"tags": "$tags", "saved": "$saved_ids"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$status", "published"]},
                                        {"$not": {"$in": ["$_id", "$$saved"]}},
                                        {
                                            "$gt": [
                                                {
                                                    "$size": {
                                                        "$setIntersection": ["$tags", "$$tags"]
                                                    }
                                                },
                                                0,
                                            ]
                                        },
                                    ]
                                }
                            }
                        },
                        {
                            "$addFields": {
                                "match_score": {"$size": {"$setIntersection": ["$tags", "$$tags"]}}
                            }
                        },
                        {"$sort": {"match_score": -1, "popularity": -1}},
                        {"$limit": limit},
                    ],
                    "as": "recommendations",
                }
            },
            {"$unwind": "$recommendations"},
            {"$replaceRoot": {"newRoot": "$recommendations"}},
        ]
        return await aggregate(self.collection, pipeline, length=limit)

    async def count(self) -> int:
        return await self.collection.count_documents({})

    async def most_saved(self, limit: int = 10) -> list[dict[str, Any]]:
        pipeline = [
            {"$group": {"_id": "$content_id", "saves": {"$sum": 1}}},
            {"$sort": {"saves": -1}},
            {"$limit": limit},
            {
                "$lookup": {
                    "from": "contents",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "content",
                }
            },
            {"$unwind": "$content"},
            {"$match": {"content.status": "published"}},
            {"$project": {"_id": 0, "saves": 1, "content": "$content"}},
        ]
        return await aggregate(self.collection, pipeline, length=limit)
