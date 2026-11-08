from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.core.exceptions import AppError
from app.utils.mongo import aggregate
from app.utils.serializers import to_object_id

SORT_OPTIONS: dict[str, dict[str, int]] = {
    "-created_at": {"created_at": -1},
    "created_at": {"created_at": 1},
    "-popularity": {"popularity": -1, "rating_avg": -1},
    "popularity": {"popularity": 1},
    "-rating": {"rating_avg": -1, "rating_count": -1},
    "-published_at": {"published_at": -1},
    "title": {"title": 1},
}


class ContentRepository:
    def __init__(self, db: AsyncDatabase) -> None:
        self.collection = db.contents

    async def create(self, document: dict[str, Any]) -> str:
        result = await self.collection.insert_one(document)
        return str(result.inserted_id)

    async def find_by_id(self, content_id: str | ObjectId) -> dict[str, Any] | None:
        return await self.collection.find_one({"_id": to_object_id(content_id)})

    async def update(self, content_id: str | ObjectId, data: dict[str, Any]) -> dict[str, Any]:
        data["updated_at"] = datetime.now(UTC)
        result = await self.collection.find_one_and_update(
            {"_id": to_object_id(content_id)},
            {"$set": data},
            return_document=ReturnDocument.AFTER,
        )
        if result is None:
            raise AppError(404, "CONTENT_NOT_FOUND", "El contenido no existe")
        return result

    async def delete(self, content_id: str | ObjectId) -> bool:
        result = await self.collection.delete_one({"_id": to_object_id(content_id)})
        return result.deleted_count > 0

    async def list_contents(
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
    ) -> tuple[list[dict[str, Any]], int]:
        match: dict[str, Any] = {}
        if status:
            match["status"] = status
        if tags:
            match["tags"] = {"$in": tags}
        if content_type:
            match["type"] = content_type
        if language:
            match["language"] = language
        if year_from or year_to:
            date_filter: dict[str, Any] = {}
            if year_from:
                date_filter["$gte"] = datetime(year_from, 1, 1, tzinfo=UTC)
            if year_to:
                date_filter["$lte"] = datetime(year_to, 12, 31, 23, 59, 59, tzinfo=UTC)
            match["published_at"] = date_filter

        sort_spec = SORT_OPTIONS.get(sort, SORT_OPTIONS["-created_at"])
        pipeline = [
            {"$match": match},
            {
                "$facet": {
                    "data": [
                        {"$sort": sort_spec},
                        {"$skip": (page - 1) * limit},
                        {"$limit": limit},
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

    async def search_text(
        self,
        *,
        query: str,
        page: int,
        limit: int,
    ) -> tuple[list[dict[str, Any]], int]:
        pipeline = [
            {"$match": {"$text": {"$search": query}, "status": "published"}},
            {"$addFields": {"score": {"$meta": "textScore"}}},
            {"$sort": {"score": -1, "popularity": -1}},
            {
                "$facet": {
                    "data": [
                        {"$skip": (page - 1) * limit},
                        {"$limit": limit},
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

    async def popular(self, limit: int = 10) -> list[dict[str, Any]]:
        cursor = (
            self.collection.find({"status": "published"})
            .sort([("popularity", -1), ("rating_avg", -1)])
            .limit(limit)
        )
        return [doc async for doc in cursor]

    async def top_rated(self, *, min_reviews: int = 1, limit: int = 10) -> list[dict[str, Any]]:
        pipeline = [
            {
                "$group": {
                    "_id": "$content_id",
                    "avg_rating": {"$avg": "$rating"},
                    "review_count": {"$sum": 1},
                }
            },
            {"$match": {"review_count": {"$gte": min_reviews}}},
            {"$sort": {"avg_rating": -1, "review_count": -1}},
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
            {
                "$replaceRoot": {
                    "newRoot": {
                        "$mergeObjects": [
                            "$content",
                            {
                                "rating_avg": {"$round": ["$avg_rating", 2]},
                                "rating_count": "$review_count",
                            },
                        ]
                    }
                }
            },
        ]
        return await aggregate(
            self.collection.database.reviews,
            pipeline,
            length=limit,
        )

    async def by_author(self, limit: int = 20) -> list[dict[str, Any]]:
        pipeline = [
            {"$match": {"status": "published"}},
            {
                "$group": {
                    "_id": "$author",
                    "total": {"$sum": 1},
                    "avg_popularity": {"$avg": "$popularity"},
                    "titles": {"$push": "$title"},
                }
            },
            {"$sort": {"total": -1, "avg_popularity": -1}},
            {"$limit": limit},
            {
                "$project": {
                    "_id": 0,
                    "author": "$_id",
                    "total": 1,
                    "avg_popularity": {"$round": ["$avg_popularity", 1]},
                    "titles": {"$slice": ["$titles", 5]},
                }
            },
        ]
        return await aggregate(self.collection, pipeline, length=limit)

    async def tag_stats(self, limit: int = 20) -> list[dict[str, Any]]:
        pipeline = [
            {"$match": {"status": "published"}},
            {"$unwind": "$tags"},
            {
                "$group": {
                    "_id": "$tags",
                    "total": {"$sum": 1},
                    "avg_rating": {"$avg": "$rating_avg"},
                    "total_popularity": {"$sum": "$popularity"},
                }
            },
            {"$sort": {"total": -1, "total_popularity": -1}},
            {"$limit": limit},
            {
                "$project": {
                    "_id": 0,
                    "tag": "$_id",
                    "total": 1,
                    "avg_rating": {"$round": ["$avg_rating", 2]},
                    "total_popularity": 1,
                }
            },
        ]
        return await aggregate(self.collection, pipeline, length=limit)

    async def increment_popularity(self, content_id: str | ObjectId, delta: int) -> None:
        await self.collection.update_one(
            {"_id": to_object_id(content_id)},
            [
                {
                    "$set": {
                        "popularity": {
                            "$max": [0, {"$add": [{"$ifNull": ["$popularity", 0]}, delta]}]
                        }
                    }
                }
            ],
        )

    async def update_rating(
        self,
        content_id: str | ObjectId,
        avg_rating: float,
        count: int,
    ) -> None:
        await self.collection.update_one(
            {"_id": to_object_id(content_id)},
            {"$set": {"rating_avg": avg_rating, "rating_count": count}},
        )

    async def count(self, query: dict[str, Any] | None = None) -> int:
        return await self.collection.count_documents(query or {})

    async def contents_per_type(self) -> list[dict[str, Any]]:
        pipeline = [
            {"$group": {"_id": "$type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$project": {"_id": 0, "type": "$_id", "count": 1}},
        ]
        return await aggregate(self.collection, pipeline, length=20)
