from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_optional_user, user_id_of
from app.core.database import get_db
from app.schemas.content import MostSavedItem, TagStat
from app.services.contents import ContentService

router = APIRouter(prefix="/stats", tags=["Stats"])


@router.get(
    "/tags",
    response_model=list[TagStat],
    summary="Estadísticas por etiqueta (Consulta 6)",
    description="Consulta MongoDB #6: `$unwind` + `$group` + `$avg` + `$sum`.",
    tags=["Stats", "Consultas MongoDB"],
)
async def tag_stats(
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
):
    return await ContentService(db).tag_stats(limit=limit)


@router.get(
    "/most-saved",
    response_model=list[MostSavedItem],
    summary="Contenidos más guardados (Consulta 7)",
    description=("Consulta MongoDB #7: `$group` sobre collections + `$sum` + `$sort` + `$lookup`."),
    tags=["Stats", "Consultas MongoDB"],
)
async def most_saved(
    limit: int = Query(10, ge=1, le=50),
    user=Depends(get_optional_user),
    db=Depends(get_db),
):
    return await ContentService(db).most_saved(
        limit=limit,
        user_id=user_id_of(user) if user else None,
    )
