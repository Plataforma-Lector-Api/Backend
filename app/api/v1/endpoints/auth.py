from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.common import Message
from app.schemas.user import UserPublic
from app.services.auth import AuthService
from app.utils.serializers import serialize_doc

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=201,
    summary="Registrar una cuenta",
)
async def register(payload: RegisterRequest, db=Depends(get_db)):
    return await AuthService(db).register(payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión y obtener tokens JWT",
)
@limiter.limit("10/minute")
async def login(request: Request, payload: LoginRequest, db=Depends(get_db)):  # noqa: ARG001
    return await AuthService(db).login(payload)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar el access token con el refresh token",
)
async def refresh(payload: RefreshRequest, db=Depends(get_db)):
    return await AuthService(db).refresh(payload.refresh_token)


@router.post("/logout", response_model=Message, summary="Cerrar sesión")
async def logout(payload: LogoutRequest, db=Depends(get_db)):
    await AuthService(db).logout(payload.refresh_token)
    return {"message": "Sesión cerrada correctamente"}


@router.get("/me", response_model=UserPublic, summary="Obtener el usuario autenticado")
async def me(user=Depends(get_current_user)):
    user.pop("password_hash", None)
    return serialize_doc(user)
