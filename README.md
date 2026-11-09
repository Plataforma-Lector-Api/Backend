# Lector+ API

API REST para una plataforma de lectura digital construida con **FastAPI + MongoDB**. Incluye autenticación JWT, catálogo, búsqueda full-text, biblioteca personal, reseñas, progreso de lectura, panel administrativo, almacenamiento de PDFs en **GridFS** y **10 consultas MongoDB** demostrables desde Swagger.

> Repositorio backend del proyecto **Plataforma Lector API**. El frontend vive en un repositorio separado (`Frontend`).

## Demo en vivo

| Servicio | URL |
|---|---|
| API | <https://lector-api-k2ak.onrender.com> |
| Swagger UI | <https://lector-api-k2ak.onrender.com/docs> |
| Frontend | <https://frontend-nine-nu-92.vercel.app> |

Credenciales de demostración: `admin@lector.com` / `Admin123!` (admin) y `lector@lector.com` / `Lector123!` (lector).

> El backend corre en el plan free de Render: se suspende tras 15 minutos sin tráfico y la primera petición puede tardar ~50 s.

---

## Stack

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.12+ |
| Framework | FastAPI + Pydantic v2 |
| Base de datos | MongoDB 7/8/9 (local o Atlas) |
| Driver | PyMongo Async (`AsyncMongoClient`) |
| Autenticación | JWT (PyJWT) + Argon2 (`pwdlib`) |
| Archivos | MongoDB GridFS (`pdfs.files` / `pdfs.chunks`) |
| Rate limiting | SlowAPI |
| Documentación | Swagger UI (`/docs`) + ReDoc (`/redoc`) |
| Calidad | Ruff + Pytest |

---

## Arquitectura

```
app/
├── api/
│   ├── deps.py                 # JWT, usuario actual, RBAC
│   └── v1/
│       ├── router.py
│       └── endpoints/          # auth, users, contents, collections,
│                               # reviews, stats, admin, queries
├── core/                       # config, database, security, errors, rate limit
├── repositories/               # acceso a MongoDB y pipelines de agregación
├── schemas/                    # modelos Pydantic de entrada/salida
├── scripts/
│   ├── indexes.py              # creación idempotente de índices
│   └── seed.py                 # datos demo + PDFs en GridFS
├── services/                   # lógica de negocio
├── utils/                      # serialización, paginación, helper async
└── main.py                     # app FastAPI, CORS, middleware, health checks
```

Flujo: **endpoint → service → repository → MongoDB**. Los endpoints validan con Pydantic, los servicios aplican reglas de negocio y los repositorios contienen las consultas.

### Colecciones

| Colección | Propósito |
|---|---|
| `users` | Usuarios, roles (`reader`/`admin`) y estado |
| `contents` | Catálogo de libros, artículos, tesis, revistas y ensayos |
| `collections` | Biblioteca personal (guardados por usuario) |
| `reviews` | Reseñas y calificaciones (1 por usuario/contenido) |
| `reading_progress` | Progreso de lectura por usuario/contenido |
| `refresh_tokens` | Refresh tokens con revocación y TTL |
| `pdfs.files` / `pdfs.chunks` | PDFs reales almacenados en GridFS |

---

## Las 10 consultas MongoDB

Todas están documentadas en Swagger bajo el tag **Consultas MongoDB** y disponibles en `GET /api/v1/queries`.

| # | Consulta | Endpoint | Operadores principales |
|---|---|---|---|
| 1 | Búsqueda full-text | `GET /api/v1/contents/search?q=algebra` | `$text`, `$meta: textScore`, `$facet` |
| 2 | Catálogo filtrado y paginado | `GET /api/v1/contents?tags=matematicas&type=book` | `$match`, `$in`, `$facet`, `$sort` |
| 3 | Contenidos populares | `GET /api/v1/contents/popular` | `$sort`, `$limit` |
| 4 | Mejor valorados | `GET /api/v1/contents/top-rated?min_reviews=2` | `$group`, `$avg`, `$lookup`, `$unwind` |
| 5 | Agrupados por autor | `GET /api/v1/contents/by-author` | `$group`, `$sum`, `$avg`, `$push` |
| 6 | Estadísticas por etiqueta | `GET /api/v1/stats/tags` | `$unwind`, `$group`, `$avg`, `$sum` |
| 7 | Más guardados | `GET /api/v1/stats/most-saved` | `$group`, `$sum`, `$lookup` |
| 8 | Mi biblioteca | `GET /api/v1/collections/me` | `$match`, `$lookup`, `$facet` |
| 9 | Recomendaciones | `GET /api/v1/collections/me/recommendations` | `$lookup` con pipeline, `$setIntersection`, `$reduce` |
| 10 | Dashboard admin | `GET /api/v1/admin/dashboard` | `$group`, `$dateToString`, `$facet`, `$lookup` |

Los índices que soportan estas consultas se crean automáticamente al arrancar (`app/scripts/indexes.py`): índice de texto con pesos, índices compuestos para filtros, multikey para etiquetas, únicos para guardados/reseñas/progreso y TTL para refresh tokens.

---

## Credenciales demo

| Rol | Correo | Contraseña |
|---|---|---|
| Admin | `admin@lector.com` | `Admin123!` |
| Lector | `lector@lector.com` | `Lector123!` |

El seed crea además 5 lectores, 26 contenidos, 43 reseñas, 37 guardados, 17 progresos y 3 PDFs reales en GridFS.

---

## Ejecución local

### 1. Requisitos

- Python 3.12+
- MongoDB local o una cadena de conexión de MongoDB Atlas

### 2. Instalar dependencias

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux/macOS
```

Edita `.env` con tu `MONGO_URI` y un `JWT_SECRET` seguro.

### 4. Cargar datos demo

```bash
python -m app.scripts.seed
```

### 5. Arrancar la API

```bash
uvicorn app.main:app --reload --port 8000
```

- Swagger: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Health: <http://localhost:8000/health>
- Readiness (MongoDB): <http://localhost:8000/ready>

### Docker

```bash
docker compose up --build
```

Esto levanta MongoDB y la API. Después ejecuta el seed dentro del contenedor:

```bash
docker compose exec api python -m app.scripts.seed
```

---

## Pruebas

```bash
# Lint y formato
ruff check app tests
ruff format --check app tests

# Tests unitarios e integración
pytest

# Smoke test end-to-end contra una API en ejecución
python tests/smoke_live.py
```

El smoke test verifica 46 comprobaciones: salud, Swagger, autenticación, las 10 consultas, CRUD, GridFS, reseñas, progreso y permisos.

---

## Despliegue gratuito

Arquitectura recomendada:

```
Vercel (React)  ──HTTPS──▶  Render (FastAPI)  ──TLS──▶  MongoDB Atlas M0
```

### MongoDB Atlas (M0 gratis)

1. Crea una cuenta en <https://www.mongodb.com/cloud/atlas/register>.
2. Crea un clúster **M0 Free** en la región más cercana.
3. En **Database Access**, crea un usuario con contraseña (rol `readWriteAnyDatabase` o `readWrite` sobre la base).
4. En **Network Access**, agrega `0.0.0.0/0` (Render no ofrece IP fija en el plan free).
5. En **Connect → Drivers**, copia la cadena `mongodb+srv://...` y añade el nombre de la base: `.../lector_plus?retryWrites=true&w=majority`.

### Render (free)

1. Crea una cuenta en <https://render.com> y conecta GitHub.
2. **New → Blueprint** y selecciona el repositorio `Plataforma-Lector-Api/Backend` (usa `render.yaml`).
3. Configura las variables:
   - `MONGO_URI`: cadena de Atlas.
   - `CORS_ORIGINS`: URL de Vercel, por ejemplo `https://frontend-nine-nu-92.vercel.app`.
   - `JWT_SECRET`: se genera automáticamente con el Blueprint.
4. Tras el primer despliegue, ejecuta el seed desde la consola de Render:

   ```bash
   python -m app.scripts.seed
   ```

5. Verifica `https://lector-api-k2ak.onrender.com/health` y `/docs`.

> El plan free de Render suspende el servicio tras 15 minutos sin tráfico. La primera petición puede tardar ~50 s. Puedes usar UptimeRobot para mantenerlo activo.

### Vercel (frontend)

1. Crea una cuenta en <https://vercel.com> y conecta GitHub.
2. **Add New → Project** y selecciona `Plataforma-Lector-Api/Frontend`.
3. Variable de entorno: `VITE_API_URL=https://lector-api-k2ak.onrender.com/api/v1`.
4. Deploy. Después actualiza `CORS_ORIGINS` en Render con la URL final de Vercel.

---

## Variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `ENV` | `development` o `production` | `development` |
| `MONGO_URI` | Cadena de conexión de MongoDB | `mongodb://localhost:27017` |
| `MONGO_DB` | Nombre de la base de datos | `lector_plus` |
| `JWT_SECRET` | Secreto para firmar JWT | valor inseguro de desarrollo |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Vida del access token | `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Vida del refresh token | `7` |
| `CORS_ORIGINS` | Orígenes permitidos, separados por coma | `http://localhost:5173` |
| `RATE_LIMIT_ENABLED` | Activa el límite de peticiones | `true` |
| `MAX_PDF_MB` | Tamaño máximo de PDF | `15` |

---

## Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Registro |
| `POST` | `/api/v1/auth/login` | Login y tokens |
| `POST` | `/api/v1/auth/refresh` | Renovar access token |
| `POST` | `/api/v1/auth/logout` | Revocar refresh token |
| `GET` | `/api/v1/auth/me` | Usuario autenticado |
| `GET/PATCH` | `/api/v1/users/me` | Perfil |
| `GET/PUT` | `/api/v1/users/me/progress/{content_id}` | Progreso de lectura |
| `GET` | `/api/v1/contents` | Catálogo filtrado |
| `GET` | `/api/v1/contents/search` | Búsqueda full-text |
| `GET` | `/api/v1/contents/{id}` | Detalle |
| `POST/PATCH/DELETE` | `/api/v1/contents` | CRUD (admin) |
| `POST` | `/api/v1/contents/{id}/file` | Subir PDF (admin) |
| `GET` | `/api/v1/contents/{id}/file` | Leer/descargar PDF |
| `GET/POST/DELETE` | `/api/v1/contents/{id}/reviews` | Reseñas |
| `GET` | `/api/v1/collections/me` | Mi biblioteca |
| `POST/DELETE` | `/api/v1/collections/{content_id}` | Guardar/quitar |
| `GET` | `/api/v1/collections/me/recommendations` | Recomendaciones |
| `GET` | `/api/v1/admin/dashboard` | Dashboard (admin) |
| `GET` | `/api/v1/admin/users` | Usuarios (admin) |
| `GET` | `/api/v1/queries` | Catálogo de las 10 consultas |

La documentación completa e interactiva está en `/docs`.

---

## Seguridad

- Contraseñas con **Argon2**.
- Access tokens de 60 minutos y refresh tokens de 7 días con rotación y revocación.
- Refresh tokens almacenados como hash SHA-256, con índice TTL.
- Autorización por roles (`reader` / `admin`).
- Validación estricta con Pydantic v2.
- Rate limiting en login y endpoints sensibles.
- CORS restringido por variable de entorno.
- PDFs validados por extensión, firma `%PDF-` y tamaño máximo.
- Respuestas de error uniformes con `request_id`.

---

## Flujo de trabajo Git

- `main`: versión estable / producción.
- `feature/*`: nuevas funcionalidades.
- `docs/*`: documentación y entregables.
- Commits con Conventional Commits (`feat:`, `fix:`, `docs:`).
- Cada entrega se cierra con un Pull Request y un tag (`entrega-2`).

---

## Licencia

MIT.
