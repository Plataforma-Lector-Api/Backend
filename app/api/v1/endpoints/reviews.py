from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, user_id_of
from app.core.database import get_db
from app.schemas.common import Message, Page
from app.schemas.review import ReviewCreate, ReviewPublic
from app.services.reviews import ReviewService
from app.utils.pagination import page_meta

router = APIRouter(prefix="/contents", tags=["Reviews"])


@router.get(
    "/{content_id}/reviews",
    response_model=Page[ReviewPublic],
    summary="Reseñas de un contenido",
)
async def list_reviews(
    content_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db=Depends(get_db),
):
    data, total = await ReviewService(db).list(
        content_id=content_id,
        page=page,
        limit=limit,
    )
    return {"data": data, "meta": page_meta(page=page, limit=limit, total=total)}


@router.post(
    "/{content_id}/reviews",
    response_model=ReviewPublic,
    summary="Crear o actualizar mi reseña",
)
async def upsert_review(
    content_id: str,
    payload: ReviewCreate,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await ReviewService(db).upsert(
        user_id=user_id_of(user),
        content_id=content_id,
        data=payload,
    )


@router.delete(
    "/{content_id}/reviews/me",
    response_model=Message,
    summary="Eliminar mi reseña",
)
async def delete_review(
    content_id: str,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    await ReviewService(db).delete(
        user_id=user_id_of(user),
        content_id=content_id,
    )
    return {"message": "Reseña eliminada correctamente"}
