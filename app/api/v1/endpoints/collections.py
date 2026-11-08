from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, user_id_of
from app.core.database import get_db
from app.schemas.collection import LibraryItem, RecommendationItem
from app.schemas.common import Message, Page
from app.services.collections import CollectionService
from app.utils.pagination import page_meta

router = APIRouter(prefix="/collections", tags=["Collections"])


@router.get(
    "/me",
    response_model=Page[LibraryItem],
    summary="Mi biblioteca personal (Consulta 8)",
    description=(
        "Consulta MongoDB #8: `$match` por usuario + `$lookup` con contents + "
        "`$unwind` + `$facet` para paginar."
    ),
    tags=["Collections", "Consultas MongoDB"],
)
async def my_collection(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=50),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    data, total = await CollectionService(db).list(
        user_id=user_id_of(user),
        page=page,
        limit=limit,
    )
    return {"data": data, "meta": page_meta(page=page, limit=limit, total=total)}


@router.get(
    "/me/recommendations",
    response_model=list[RecommendationItem],
    summary="Recomendaciones personalizadas (Consulta 9)",
    description=(
        "Consulta MongoDB #9: `$lookup` con pipeline + `$setIntersection` + "
        "`$size` + `$reduce` + `$addToSet` para recomendar por etiquetas afines."
    ),
    tags=["Collections", "Consultas MongoDB"],
)
async def my_recommendations(
    limit: int = Query(10, ge=1, le=30),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await CollectionService(db).recommendations(
        user_id=user_id_of(user),
        limit=limit,
    )


@router.post(
    "/{content_id}",
    response_model=Message,
    status_code=201,
    summary="Guardar un contenido en mi biblioteca",
)
async def add_to_collection(
    content_id: str,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    await CollectionService(db).add(user_id=user_id_of(user), content_id=content_id)
    return {"message": "Contenido agregado a tu biblioteca"}


@router.delete(
    "/{content_id}",
    response_model=Message,
    summary="Quitar un contenido de mi biblioteca",
)
async def remove_from_collection(
    content_id: str,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    removed = await CollectionService(db).remove(
        user_id=user_id_of(user),
        content_id=content_id,
    )
    if not removed:
        from app.core.exceptions import AppError

        raise AppError(404, "NOT_SAVED", "El contenido no está en tu biblioteca")
    return {"message": "Contenido eliminado de tu biblioteca"}
