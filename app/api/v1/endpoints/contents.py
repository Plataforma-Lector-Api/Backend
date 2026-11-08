from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user, get_optional_user, require_admin, user_id_of
from app.core.database import get_db
from app.schemas.common import Message, Page
from app.schemas.content import (
    AuthorStat,
    ContentCreate,
    ContentPublic,
    ContentSearchItem,
    ContentUpdate,
    FileMetadata,
)
from app.services.contents import ContentService
from app.services.files import FileService
from app.utils.pagination import page_meta

router = APIRouter(prefix="/contents", tags=["Contents"])


def _parse_tags(value: str | None) -> list[str] | None:
    if not value:
        return None
    tags = [tag.strip().lower() for tag in value.split(",") if tag.strip()]
    return tags or None


@router.get(
    "",
    response_model=Page[ContentPublic],
    summary="Catálogo filtrado y paginado (Consulta 2)",
    description=(
        "Consulta MongoDB #2: `$match` + `$in` + `$gte/$lte` + `$facet` + `$sort` "
        "para filtros combinados y paginación en una sola operación."
    ),
    tags=["Contents", "Consultas MongoDB"],
)
async def list_contents(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=50),
    tags: str | None = Query(None, description="Etiquetas separadas por coma"),
    content_type: str | None = Query(None, alias="type"),
    year_from: int | None = Query(None, ge=0),
    year_to: int | None = Query(None, ge=0),
    language: str | None = None,
    sort: str = Query("-created_at"),
    user=Depends(get_optional_user),
    db=Depends(get_db),
):
    data, total = await ContentService(db).list(
        page=page,
        limit=limit,
        tags=_parse_tags(tags),
        content_type=content_type,
        year_from=year_from,
        year_to=year_to,
        language=language,
        sort=sort,
        user_id=user_id_of(user) if user else None,
    )
    return {"data": data, "meta": page_meta(page=page, limit=limit, total=total)}


@router.get(
    "/search",
    response_model=Page[ContentSearchItem],
    summary="Búsqueda full-text (Consulta 1)",
    description=(
        "Consulta MongoDB #1: índice text + `$text` + `$meta: textScore` para "
        "ordenar por relevancia."
    ),
    tags=["Contents", "Consultas MongoDB"],
)
async def search_contents(
    q: str = Query(..., min_length=1, description="Texto a buscar"),
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=50),
    user=Depends(get_optional_user),
    db=Depends(get_db),
):
    data, total = await ContentService(db).search(
        query=q,
        page=page,
        limit=limit,
        user_id=user_id_of(user) if user else None,
    )
    return {"data": data, "meta": page_meta(page=page, limit=limit, total=total)}


@router.get(
    "/popular",
    response_model=list[ContentPublic],
    summary="Contenidos populares (Consulta 3)",
    description="Consulta MongoDB #3: `$sort` por popularidad + `$limit`.",
    tags=["Contents", "Consultas MongoDB"],
)
async def popular_contents(
    limit: int = Query(10, ge=1, le=50),
    user=Depends(get_optional_user),
    db=Depends(get_db),
):
    return await ContentService(db).popular(
        limit=limit,
        user_id=user_id_of(user) if user else None,
    )


@router.get(
    "/top-rated",
    response_model=list[ContentPublic],
    summary="Contenidos mejor valorados (Consulta 4)",
    description=(
        "Consulta MongoDB #4: `$group` + `$avg` + `$match` + `$lookup` para calcular "
        "el promedio real de reseñas."
    ),
    tags=["Contents", "Consultas MongoDB"],
)
async def top_rated_contents(
    min_reviews: int = Query(1, ge=0, le=100),
    limit: int = Query(10, ge=1, le=50),
    user=Depends(get_optional_user),
    db=Depends(get_db),
):
    return await ContentService(db).top_rated(
        min_reviews=min_reviews,
        limit=limit,
        user_id=user_id_of(user) if user else None,
    )


@router.get(
    "/by-author",
    response_model=list[AuthorStat],
    summary="Contenidos por autor (Consulta 5)",
    description="Consulta MongoDB #5: `$group` + `$sum` + `$avg` + `$push`.",
    tags=["Contents", "Consultas MongoDB"],
)
async def contents_by_author(
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
):
    return await ContentService(db).by_author(limit=limit)


@router.post(
    "",
    response_model=ContentPublic,
    status_code=201,
    summary="Crear contenido (admin)",
    tags=["Contents", "Admin"],
)
async def create_content(
    payload: ContentCreate,
    user=Depends(require_admin),
    db=Depends(get_db),
):
    return await ContentService(db).create(payload, user_id=user_id_of(user))


@router.patch(
    "/{content_id}",
    response_model=ContentPublic,
    summary="Actualizar contenido (admin)",
    tags=["Contents", "Admin"],
)
async def update_content(
    content_id: str,
    payload: ContentUpdate,
    user=Depends(require_admin),
    db=Depends(get_db),
):
    return await ContentService(db).update(
        content_id,
        payload,
        user_id=user_id_of(user),
    )


@router.delete(
    "/{content_id}",
    response_model=Message,
    summary="Eliminar contenido (admin)",
    tags=["Contents", "Admin"],
)
async def delete_content(
    content_id: str,
    user=Depends(require_admin),  # noqa: ARG001
    db=Depends(get_db),
):
    await ContentService(db).delete(content_id)
    return {"message": "Contenido eliminado correctamente"}


@router.get(
    "/{content_id}",
    response_model=ContentPublic,
    summary="Detalle de un contenido",
)
async def get_content(
    content_id: str,
    user=Depends(get_optional_user),
    db=Depends(get_db),
):
    return await ContentService(db).get(
        content_id,
        user_id=user_id_of(user) if user else None,
    )


@router.post(
    "/{content_id}/file",
    response_model=FileMetadata,
    summary="Subir o reemplazar el PDF de un contenido (admin)",
    tags=["Contents", "Admin", "Files"],
)
async def upload_content_file(
    content_id: str,
    file: UploadFile = File(...),
    user=Depends(require_admin),
    db=Depends(get_db),
):
    data = await file.read()
    service = FileService(db)
    await service.upload(
        user_id=user_id_of(user),
        content_id=content_id,
        filename=file.filename or "documento.pdf",
        content_type=file.content_type,
        data=data,
    )
    return await service.get_metadata(content_id)


@router.get(
    "/{content_id}/file/metadata",
    response_model=FileMetadata,
    summary="Metadatos del PDF de un contenido",
    tags=["Files"],
)
async def get_content_file_metadata(
    content_id: str,
    user=Depends(get_current_user),  # noqa: ARG001
    db=Depends(get_db),
):
    return await FileService(db).get_metadata(content_id)


@router.get(
    "/{content_id}/file",
    summary="Descargar o visualizar el PDF de un contenido",
    tags=["Files"],
)
async def download_content_file(
    content_id: str,
    user=Depends(get_current_user),  # noqa: ARG001
    db=Depends(get_db),
):
    stream, filename, content_type = await FileService(db).get_download(content_id)

    async def iterator():
        while True:
            chunk = await stream.read(64 * 1024)
            if not chunk:
                break
            yield chunk

    return StreamingResponse(
        iterator(),
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete(
    "/{content_id}/file",
    response_model=Message,
    summary="Eliminar el PDF de un contenido (admin)",
    tags=["Contents", "Admin", "Files"],
)
async def delete_content_file(
    content_id: str,
    user=Depends(require_admin),  # noqa: ARG001
    db=Depends(get_db),
):
    await FileService(db).delete(content_id)
    return {"message": "PDF eliminado correctamente"}
