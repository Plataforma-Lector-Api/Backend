from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.repositories.users import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest
from app.utils.serializers import serialize_doc, to_object_id


class AuthService:
    def __init__(self, db: AsyncDatabase) -> None:
        self.users = UserRepository(db)
        self.refresh_tokens = db.refresh_tokens

    async def register(self, data: RegisterRequest) -> dict[str, Any]:
        now = datetime.now(UTC)
        document = {
            "name": data.name.strip(),
            "email": data.email.lower().strip(),
            "password_hash": hash_password(data.password),
            "role": "reader",
            "status": "active",
            "avatar_url": None,
            "bio": None,
            "created_at": now,
            "updated_at": now,
            "last_login_at": None,
        }
        user_id = await self.users.create(document)
        user = await self.users.find_by_id(user_id)
        return self._public_user(user)

    async def login(self, data: LoginRequest) -> dict[str, Any]:
        user = await self.users.find_by_email(data.email)
        if user is None or not verify_password(data.password, user["password_hash"]):
            raise AppError(
                401,
                "INVALID_CREDENTIALS",
                "Correo o contraseña incorrectos",
            )
        if user.get("status") != "active":
            raise AppError(403, "USER_DISABLED", "La cuenta está deshabilitada")

        await self.users.update_last_login(user["_id"])
        user = await self.users.find_by_id(user["_id"])
        tokens = await self._issue_tokens(user)
        return {**tokens, "user": self._public_user(user)}

    async def refresh(self, refresh_token: str) -> dict[str, Any]:
        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError as exc:
            raise AppError(
                401,
                "INVALID_REFRESH_TOKEN",
                "El refresh token no es válido o expiró",
            ) from exc

        if payload.get("type") != "refresh":
            raise AppError(401, "INVALID_REFRESH_TOKEN", "Tipo de token incorrecto")

        record = await self.refresh_tokens.find_one(
            {
                "token_hash": hash_token(refresh_token),
                "revoked_at": None,
                "expires_at": {"$gt": datetime.now(UTC)},
            }
        )
        if record is None:
            raise AppError(401, "REFRESH_TOKEN_REVOKED", "El refresh token fue revocado")

        user = await self.users.find_by_id(payload["sub"])
        if user is None or user.get("status") != "active":
            raise AppError(401, "USER_NOT_FOUND", "El usuario ya no está disponible")

        await self.refresh_tokens.update_one(
            {"_id": record["_id"]},
            {"$set": {"revoked_at": datetime.now(UTC)}},
        )
        tokens = await self._issue_tokens(user)
        return {**tokens, "user": self._public_user(user)}

    async def logout(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        await self.refresh_tokens.update_one(
            {"token_hash": hash_token(refresh_token)},
            {"$set": {"revoked_at": datetime.now(UTC)}},
        )

    async def _issue_tokens(self, user: dict[str, Any]) -> dict[str, str]:
        user_id = str(user["_id"])
        access_token = create_access_token(user_id, user["role"])
        refresh_token = create_refresh_token(user_id, user["role"])
        await self.refresh_tokens.insert_one(
            {
                "user_id": to_object_id(user_id),
                "token_hash": hash_token(refresh_token),
                "expires_at": datetime.now(UTC)
                + timedelta(days=settings.refresh_token_expire_days),
                "revoked_at": None,
                "created_at": datetime.now(UTC),
            }
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    @staticmethod
    def _public_user(user: dict[str, Any] | None) -> dict[str, Any]:
        if user is None:
            raise AppError(404, "USER_NOT_FOUND", "El usuario no existe")
        user.pop("password_hash", None)
        return serialize_doc(user)
