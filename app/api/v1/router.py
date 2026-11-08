from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    collections,
    contents,
    queries,
    reviews,
    stats,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(contents.router)
api_router.include_router(collections.router)
api_router.include_router(reviews.router)
api_router.include_router(stats.router)
api_router.include_router(admin.router)
api_router.include_router(queries.router)
