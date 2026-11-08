from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_admin, user_id_of
from app.core.database import get_db
from app.repositories.users import UserRepository
from app.schemas.common import Page
from app.schemas.content import ContentPublic
from app.schemas.stats import DashboardResponse
from app.schemas.user import AdminUserUpdate, UserPublic
from app.services.contents import ContentService
from app.services.stats import StatsService
from app.utils.pagination import page_meta
from app.utils.serializers import serialize_doc, serialize_docs

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Dashboard administrativo (Consulta 10)",
    description=(
        "Consulta MongoDB #10: combina `$group`, `$dateToString`, `$facet`, `$count` "
        "y `$lookup` para métricas globales."
    ),
    tags=["Admin", "Consultas MongoDB"],
)
async def dashboard(
    user=Depends(require_admin),  # noqa: ARG001
    db=Depends(get_db),
):
    return await StatsService(db).dashboard()


@router.get(
    "/users",
    response_model=Page[UserPublic],
    summary="Listar usuarios (admin)",
)
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    user=Depends(require_admin),  # noqa: ARG001
    db=Depends(get_db),
):
    documents, total = await UserRepository(db).list_users(
        page=page,
        limit=limit,
        search=search,
    )
    return {
        "data": serialize_docs(documents),
        "meta": page_meta(page=page, limit=limit, total=total),
    }


@router.patch(
    "/users/{user_id}",
    response_model=UserPublic,
    summary="Actualizar rol o estado de un usuario (admin)",
)
async def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    admin=Depends(require_admin),  # noqa: ARG001
    db=Depends(get_db),
):
    updated = await UserRepository(db).update(
        user_id,
        payload.model_dump(exclude_unset=True),
    )
    updated.pop("password_hash", None)
    return serialize_doc(updated)


@router.get(
    "/contents",
    response_model=Page[ContentPublic],
    summary="Listar todos los contenidos, incluidos borradores (admin)",
)
async def list_all_contents(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str = Query("all"),
    user=Depends(require_admin),
    db=Depends(get_db),
):
    data, total = await ContentService(db).list(
        page=page,
        limit=limit,
        status=status,
        sort="-created_at",
        user_id=user_id_of(user),
    )
    return {"data": data, "meta": page_meta(page=page, limit=limit, total=total)}
