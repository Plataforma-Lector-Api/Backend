from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import database, get_db
from app.core.exceptions import AppError
from app.core.rate_limit import limiter
from app.scripts.indexes import ensure_indexes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("lector")


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    await database.connect()
    await ensure_indexes(database.db)
    logger.info("MongoDB conectado a la base de datos '%s'", settings.mongo_db)
    yield
    await database.disconnect()
    logger.info("MongoDB desconectado")


DESCRIPTION = """
## Lector+ API

API REST para una plataforma de lectura construida con **FastAPI + MongoDB Atlas**.

### Autenticación
1. Usa `POST /api/v1/auth/login` con las credenciales de demostración.
2. Copia el `access_token`.
3. Pulsa **Authorize** en Swagger y pega el token.

Credenciales semilla:
- **Admin:** `admin@lector.com` / `Admin123!`
- **Lector:** `lector@lector.com` / `Lector123!`

### Las 10 consultas MongoDB
Están agrupadas bajo el tag **Consultas MongoDB** y documentadas también en
`GET /api/v1/queries`. Incluyen búsqueda full-text, filtros con `$facet`,
agregaciones con `$group`/`$avg`, `$lookup`, `$unwind`, recomendaciones con
`$setIntersection` y un dashboard con `$dateToString`.
"""


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %s (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={"name": "Plataforma Lector API", "url": "https://github.com/Plataforma-Lector-Api"},
    license_info={"name": "MIT"},
    openapi_tags=[
        {"name": "Auth", "description": "Registro, login, refresh y logout."},
        {"name": "Users", "description": "Perfil y progreso de lectura."},
        {"name": "Contents", "description": "Catálogo, búsqueda y CRUD de contenidos."},
        {"name": "Collections", "description": "Biblioteca personal y recomendaciones."},
        {"name": "Reviews", "description": "Reseñas y calificaciones."},
        {"name": "Stats", "description": "Estadísticas del catálogo."},
        {"name": "Admin", "description": "Panel administrativo y gestión de usuarios."},
        {"name": "Files", "description": "Subida y lectura de PDFs almacenados en GridFS."},
        {
            "name": "Consultas MongoDB",
            "description": (
                "Las 10 consultas demostrables del proyecto: texto, filtros, agregaciones, "
                "lookup, recomendaciones y dashboard."
            ),
        },
        {"name": "Health", "description": "Health checks para Render y UptimeRobot."},
    ],
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Request-ID"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Los datos enviados no son válidos",
                "details": exc.errors(),
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(
    request: Request,
    exc: RateLimitExceeded,  # noqa: ARG001
) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMITED",
                "message": "Demasiadas solicitudes. Intenta de nuevo en un minuto.",
                "details": None,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no controlado: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Ocurrió un error interno en el servidor",
                "details": None if settings.is_production else str(exc),
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "redoc": "/redoc",
        "api": settings.api_v1_prefix,
    }


@app.get("/health", tags=["Health"], summary="Liveness probe")
async def health():
    return {"status": "ok", "environment": settings.env}


@app.get("/ready", tags=["Health"], summary="Readiness probe (MongoDB)")
async def ready(db=Depends(get_db)):
    await db.command("ping")
    return {"status": "ready", "database": settings.mongo_db}


app.include_router(api_router, prefix=settings.api_v1_prefix)
