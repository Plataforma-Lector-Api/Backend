from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import AppError
from app.utils.mongo import aggregate
from app.utils.serializers import to_object_id


class UserRepository:
    def __init__(self, db: AsyncDatabase) -> None:
        self.collection = db.users

    async def create(self, document: dict[str, Any]) -> str:
        try:
            result = await self.collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise AppError(409, "EMAIL_EXISTS", "El correo ya está registrado") from exc
        return str(result.inserted_id)

    async def find_by_email(self, email: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"email": email.lower().strip()})

    async def find_by_id(self, user_id: str | ObjectId) -> dict[str, Any] | None:
        return await self.collection.find_one({"_id": to_object_id(user_id)})

    async def update_last_login(self, user_id: str | ObjectId) -> None:
        await self.collection.update_one(
            {"_id": to_object_id(user_id)},
            {"$set": {"last_login_at": datetime.now(UTC)}},
        )

    async def update(self, user_id: str | ObjectId, data: dict[str, Any]) -> dict[str, Any]:
        data["updated_at"] = datetime.now(UTC)
        result = await self.collection.find_one_and_update(
            {"_id": to_object_id(user_id)},
            {"$set": data},
            return_document=ReturnDocument.AFTER,
        )
        if result is None:
            raise AppError(404, "USER_NOT_FOUND", "El usuario no existe")
        return result

    async def list_users(
        self,
        *,
        page: int,
        limit: int,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if search:
            query = {
                "$or": [
                    {"name": {"$regex": search, "$options": "i"}},
                    {"email": {"$regex": search, "$options": "i"}},
                ]
            }
        total = await self.collection.count_documents(query)
        cursor = (
            self.collection.find(query, {"password_hash": 0})
            .sort("created_at", -1)
            .skip((page - 1) * limit)
            .limit(limit)
        )
        return [doc async for doc in cursor], total

    async def count(self) -> int:
        return await self.collection.count_documents({})

    async def count_by_month(self) -> list[dict[str, Any]]:
        pipeline = [
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
            {"$project": {"_id": 0, "month": "$_id", "count": 1}},
        ]
        return await aggregate(self.collection, pipeline, length=24)
