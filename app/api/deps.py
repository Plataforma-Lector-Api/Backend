from __future__ import annotations

from typing import Any

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.asynchronous.database import AsyncDatabase

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.security import decode_token
from app.repositories.users import UserRepository

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Pega aquí el access token JWT (sin la palabra Bearer).",
)


async def _resolve_user(token: str, db: AsyncDatabase) -> dict[str, Any]:
    try:
        payload = decode_token(token)
    except jwt.PyJWTError as exc:
        raise AppError(401, "INVALID_TOKEN", "El token no es válido o expiró") from exc

    if payload.get("type") != "access":
        raise AppError(401, "INVALID_TOKEN", "Se requiere un access token")

    user = await UserRepository(db).find_by_id(payload.get("sub", ""))
    if user is None or user.get("status") != "active":
        raise AppError(401, "USER_NOT_FOUND", "El usuario no existe o está deshabilitado")
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncDatabase = Depends(get_db),
) -> dict[str, Any]:
    if credentials is None:
        raise AppError(401, "UNAUTHORIZED", "Debes iniciar sesión")
    return await _resolve_user(credentials.credentials, db)


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncDatabase = Depends(get_db),
) -> dict[str, Any] | None:
    if credentials is None:
        return None
    return await _resolve_user(credentials.credentials, db)


async def require_admin(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise AppError(403, "FORBIDDEN", "Se requiere rol de administrador")
    return user


def user_id_of(user: dict[str, Any]) -> str:
    return str(user["_id"])
