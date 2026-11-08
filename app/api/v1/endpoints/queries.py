from __future__ import annotations

from fastapi import APIRouter

from app.schemas.stats import QueryInfo
from app.services.query_catalog import QUERY_CATALOG

router = APIRouter(prefix="/queries", tags=["Consultas MongoDB"])


@router.get(
    "",
    response_model=list[QueryInfo],
    summary="Catálogo de las 10 consultas MongoDB",
    description=(
        "Devuelve la documentación viva de las 10 consultas: endpoint, operadores "
        "de MongoDB utilizados e índice que las soporta."
    ),
)
async def list_queries():
    return QUERY_CATALOG
