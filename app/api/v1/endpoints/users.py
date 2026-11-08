from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, user_id_of
from app.core.database import get_db
from app.repositories.users import UserRepository
from app.schemas.progress import ProgressPublic, ProgressUpdate
from app.schemas.user import UserPublic, UserUpdate
from app.services.progress import ProgressService
from app.utils.serializers import serialize_doc

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserPublic, summary="Ver mi perfil")
async def get_me(user=Depends(get_current_user)):
    user.pop("password_hash", None)
    return serialize_doc(user)


@router.patch("/me", response_model=UserPublic, summary="Actualizar mi perfil")
async def update_me(
    payload: UserUpdate,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    updated = await UserRepository(db).update(
        user["_id"],
        payload.model_dump(exclude_unset=True),
    )
    updated.pop("password_hash", None)
    return serialize_doc(updated)


@router.get(
    "/me/progress",
    response_model=list[ProgressPublic],
    summary="Ver mi progreso de lectura",
)
async def list_progress(
    limit: int = Query(20, ge=1, le=50),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await ProgressService(db).list(user_id=user_id_of(user), limit=limit)


@router.get(
    "/me/progress/{content_id}",
    response_model=ProgressPublic | None,
    summary="Ver mi progreso en un contenido",
)
async def get_progress(
    content_id: str,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await ProgressService(db).get(
        user_id=user_id_of(user),
        content_id=content_id,
    )


@router.put(
    "/me/progress/{content_id}",
    response_model=ProgressPublic,
    summary="Guardar mi progreso de lectura",
)
async def upsert_progress(
    content_id: str,
    payload: ProgressUpdate,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await ProgressService(db).upsert(
        user_id=user_id_of(user),
        content_id=content_id,
        data=payload,
    )
