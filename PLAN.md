# Plan de reconstrucción — Lector+ / Plataforma Lector API

> Documento de planificación para rehacer el proyecto `plataforma-lector-api` con una arquitectura profesional, MongoDB como base de datos, frontend y backend separados, 10 consultas demostrables, Swagger y despliegue gratuito.

## Decisiones confirmadas

| Tema | Decisión |
|---|---|
| Backend | FastAPI + Python 3.12 + Pydantic v2 + PyMongo Async |
| Frontend | React 19 + TypeScript + Vite + Tailwind + shadcn/ui |
| Base de datos | MongoDB Atlas M0 |
| PDFs | Subida real a **GridFS** + lector con `react-pdf` |
| Alcance | Completo: reseñas, rol admin, progreso de lectura |
| Consultas | Las 10 propuestas en este documento |
| Despliegue | Render + Vercel + Atlas |

---

## 1. Qué es el proyecto actual (análisis del repo antiguo)

### 1.1 Producto

**Lector+** es una plataforma web de lectura. El flujo actual permite:

- Registrarse e iniciar sesión (JWT).
- Ver contenidos populares.
- Buscar contenidos por etiqueta.
- Guardar contenidos en una colección personal.
- Subir contenidos al catálogo.
- Abrir un "modo lectura" (actualmente es un placeholder, no lee archivos reales).

### 1.2 Stack actual

| Capa | Tecnología |
|---|---|
| Backend | Python + Flask 3 |
| Driver MongoDB | PyMongo |
| Autenticación | JWT (PyJWT) |
| Frontend | HTML + CSS + JavaScript vanilla (SPA manual con `classList`) |
| Base de datos | MongoDB (`lector_nosql_db`) |
| Legado | Esquema MySQL/MariaDB en `proyecto_db.sql` |
| Despliegue | Render (se agregó Gunicorn) |

### 1.3 Modelo de datos actual

- `usuarios`: documento con el arreglo embebido `coleccion[]`.
- `contenidos`: documento con el arreglo embebido `etiquetas[]`.
- Índices: `usuarios.correo` único, `contenidos.etiquetas.nombre`, `contenidos.popularidad`.

### 1.4 Endpoints actuales (6)

1. `POST /api/auth/register`
2. `POST /api/auth/login`
3. `GET /api/contenidos?etiqueta=...`
4. `GET /api/contenidos/populares`
5. `POST /api/coleccion/agregar`
6. `GET /api/usuario/coleccion?id_usuario=...`
7. `POST /api/contenidos/crear`

> En la práctica son 7 rutas, pero varias no tienen autenticación real ni validación.

### 1.5 Fortalezas del proyecto actual

- La idea de producto está clara y es coherente.
- Ya usa MongoDB con documentos embebidos, `$push`, `$inc` e índices.
- Ya maneja JWT y CORS.
- Ya tuvo un despliegue en Render.
- El frontend, aunque básico, cubre el flujo completo.
- Tiene datos semilla y una migración desde MySQL que sirve como contexto académico.

### 1.6 Problemas y deuda técnica

| Problema | Impacto | Solución propuesta |
|---|---|---|
| `SECRET_KEY` hardcodeada | Cualquiera puede firmar tokens | Variable de entorno + rotación |
| Contraseñas en texto plano | Grave fallo de seguridad | Argon2id/bcrypt |
| El token no se verifica en rutas protegidas | Se puede llamar la API sin autenticarse | Dependencia `get_current_user` + RBAC |
| Se confía en `id_usuario` enviado por el cliente | Suplantación de usuarios | Tomar el usuario del token, nunca del body |
| Sin validación de entrada | Datos inconsistentes, errores 500 | Pydantic v2 + schemas |
| Sin paginación | Respuestas lentas y pesadas | `page`/`limit` + metadata |
| Sin Swagger/OpenAPI | Difícil demostrar la API | FastAPI + OpenAPI 3.1 |
| `routes.py` monolítico | Difícil mantener y testear | Capas router → service → repository |
| Frontend con `innerHTML` e interpolación | XSS | React + escape automático + sanitización |
| `API_URL` hardcodeada a localhost | No funciona en producción | Variable `VITE_API_URL` |
| Sin tests, CI, Docker ni lint | Poca confiabilidad | pytest, Vitest, GitHub Actions, Ruff/ESLint |
| Sin logs estructurados ni health checks | Difícil diagnosticar | Logging JSON + `/health` + `/ready` |
| CORS abierto (`*`) | Riesgo de seguridad | Lista blanca de orígenes |
| Datos duplicados (título dentro de la colección) | Inconsistencia | Referencias por `_id` + `$lookup` |
| Arreglo `coleccion` sin límite | Documento crece indefinidamente | Colección aparte con índice único |
| Sin rol admin real | Cualquiera puede subir contenido | RBAC `reader`/`admin` |
| Modo lectura simulado | No cumple el objetivo del producto | PDF real con GridFS o enlace externo |
| Solo 6-7 consultas | No cumple el requisito de 10 | 10 consultas documentadas |
| Fechas con `datetime.utcnow()` | Deprecado en Python 3.12+ | `datetime.now(timezone.utc)` |
| Sin manejo uniforme de errores | Respuestas distintas | Handler global + formato único |

---

## 2. Visión del nuevo proyecto

Rehacer **Lector+** como una plataforma de lectura profesional, API-first, segura y demostrable:

- Catálogo de contenidos con búsqueda avanzada, filtros, paginación y ordenamiento.
- Autenticación con roles (`reader`/`admin`), JWT de acceso + refresh token.
- Biblioteca personal, reseñas/calificaciones y progreso de lectura.
- **Subida y lectura de PDFs reales** almacenados en GridFS, con visor `react-pdf`.
- Panel de administración con métricas y CRUD de contenidos.
- **10 consultas MongoDB** claramente identificadas y documentadas.
- **Swagger UI** público para demostrar la API.
- **Despliegue gratuito**: MongoDB Atlas + Render + Vercel.
- Código testeado, con CI, Docker local y documentación.

### Principios de diseño

1. **API-first**: el backend es la fuente de verdad; el frontend consume `/api/v1`.
2. **Separación de responsabilidades**: routers, servicios, repositorios y schemas.
3. **Seguridad por defecto**: hash de contraseñas, RBAC, validación, CORS restringido, rate limiting.
4. **Consultas explícitas**: las 10 consultas usan el driver oficial y pipelines de agregación visibles, no magia de ODM.
5. **Reproducibilidad**: seed, Docker Compose, `.env.example`, README y CI.
6. **Costo cero**: todo debe caber en planes gratuitos.

---

## 3. Stack recomendado

### 3.1 Backend

| Componente | Elección | Motivo |
|---|---|---|
| Lenguaje | Python 3.12+ | Continuidad con Flask, ecosistema maduro |
| Framework | **FastAPI** | OpenAPI/Swagger automático, async, tipado, rápido |
| Validación | Pydantic v2 | Schemas, validación y serialización |
| Driver MongoDB | **PyMongo Async API** (`AsyncMongoClient`) | Motor está deprecado desde mayo 2025 y su EOL es mayo 2026 |
| Archivos PDF | **GridFS** (`AsyncMongoClient`) | Guarda los PDFs en MongoDB, sin servicios externos |
| Autenticación | PyJWT + `pwdlib[argon2]` | JWT y hash Argon2id |
| Servidor | Uvicorn | Estándar para FastAPI |
| Configuración | pydantic-settings | Variables de entorno tipadas |
| Rate limiting | SlowAPI | Protección de login/registro |
| Tests | pytest + pytest-asyncio + httpx | Tests de API y servicios |
| Calidad | Ruff + mypy | Lint, formato y tipado |

> **¿Por qué no un ODM como Beanie?** Para un trabajo académico de MongoDB conviene que las 10 consultas se vean explícitas en el código (pipelines, índices, `$lookup`, `$facet`, etc.). PyMongo Async + Pydantic da control total y demuestra dominio de MongoDB.

### 3.2 Frontend

| Componente | Elección |
|---|---|
| Framework | React 19 + TypeScript |
| Build | Vite |
| Estilos | Tailwind CSS + shadcn/ui |
| Routing | React Router |
| Estado del servidor | TanStack Query |
| Estado global | Zustand (auth) |
| Formularios | React Hook Form + Zod |
| Gráficos | Recharts |
| Notificaciones | Sonner |
| Iconos | Lucide React |
| Lector PDF | `react-pdf` (si se implementa lectura real) |
| Tests | Vitest + React Testing Library |

> Alternativa si prefieres Node/TypeScript en el backend: **NestJS + Mongoose/MongoDB driver + Swagger**. Es igualmente profesional, pero el desarrollo será más pesado y las consultas quedan más abstraídas por el ODM. Recomiendo FastAPI por velocidad, Swagger automático y continuidad con tu proyecto anterior.

### 3.3 Infraestructura gratuita

| Servicio | Plan | Uso |
|---|---|---|
| MongoDB Atlas | M0 (512 MB) | Base de datos |
| Render | Web Service free | Backend FastAPI |
| Vercel | Hobby | Frontend React |
| UptimeRobot | Free | Ping a `/health` para reducir cold starts |
| GitHub Actions | Free | CI |

---

## 4. Arquitectura propuesta

### 4.1 Backend por capas

```
HTTP Request
   │
   ▼
Router (FastAPI)          → valida entrada, auth, status codes
   │
   ▼
Service                   → reglas de negocio, transacciones, permisos
   │
   ▼
Repository                → consultas MongoDB (find, aggregate, indexes)
   │
   ▼
MongoDB Atlas
```

- **Routers**: solo HTTP. No acceden a Mongo directamente.
- **Schemas**: Pydantic para request/response.
- **Services**: reglas de negocio, coordinación, validaciones de dominio.
- **Repositories**: consultas y pipelines. Aquí viven las 10 consultas.
- **Core**: configuración, conexión, seguridad, logging, excepciones.
- **Scripts**: seed, creación de índices, verificación de salud.

### 4.2 Diseño de la API

- Prefijo versionado: `/api/v1`.
- Recursos en plural: `/contents`, `/users`, `/collections`, `/reviews`.
- Paginación estándar:
  ```json
  {
    "data": [],
    "meta": {
      "page": 1,
      "limit": 12,
      "total": 120,
      "total_pages": 10
    }
  }
  ```
- Errores uniformes:
  ```json
  {
    "error": {
      "code": "CONTENT_NOT_FOUND",
      "message": "El contenido no existe",
      "details": null,
      "request_id": "..."
    }
  }
  ```
- Códigos HTTP correctos: 200, 201, 204, 400, 401, 403, 404, 409, 422, 429, 500.
- Autenticación Bearer en Swagger.
- Health checks: `GET /health` y `GET /ready`.

### 4.3 Frontend por features

```
src/
├── api/            # cliente Axios + endpoints tipados
├── components/     # UI reutilizable (shadcn) + layout
├── features/
│   ├── auth/
│   ├── catalog/
│   ├── content/
│   ├── library/
│   ├── reader/
│   ├── admin/
│   └── queries/
├── hooks/
├── lib/
├── pages/
├── stores/
├── types/
└── styles/
```

- TanStack Query para cache, loading, errores y refetch.
- Zustand solo para sesión/tema; no duplicar estado del servidor.
- Formularios con React Hook Form + Zod.
- Estados de carga con skeletons, errores con mensajes claros y empty states.
- Diseño responsive, accesible y con modo oscuro opcional.

### 4.4 Estructura de repositorios

**Backend**

```
Backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   ├── logging.py
│   │   └── exceptions.py
│   ├── models/              # documentos/tipos de dominio
│   ├── schemas/             # Pydantic request/response
│   ├── repositories/        # consultas MongoDB
│   ├── services/            # lógica de negocio
│   ├── api/
│   │   ├── deps.py
│   │   └── v1/
│   │       ├── router.py
│   │       └── endpoints/
│   │           ├── auth.py
│   │           ├── users.py
│   │           ├── contents.py
│   │           ├── collections.py
│   │           ├── reviews.py
│   │           ├── queries.py
│   │           └── admin.py
│   └── scripts/
│       ├── seed.py
│       └── create_indexes.py
├── tests/
├── docs/
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── render.yaml
└── README.md
```

**Frontend**

```
Frontend/
├── src/
│   ├── api/
│   ├── components/
│   ├── features/
│   ├── hooks/
│   ├── lib/
│   ├── pages/
│   ├── stores/
│   ├── types/
│   └── styles/
├── public/
├── index.html
├── package.json
├── tailwind.config.ts
├── tsconfig.json
├── vite.config.ts
├── vercel.json
└── README.md
```

---

## 5. Modelo de datos MongoDB

### 5.1 Colecciones

#### `users`

```js
{
  _id: ObjectId,
  name: "María López",
  email: "maria@email.com",          // único, lowercase
  password_hash: "$argon2id$...",
  role: "reader" | "admin",
  status: "active" | "disabled",
  avatar_url: null,
  bio: null,
  created_at: ISODate,
  updated_at: ISODate,
  last_login_at: ISODate | null
}
```

Índices:
- `{ email: 1 }` único.
- `{ role: 1, status: 1 }`.

#### `contents`

```js
{
  _id: ObjectId,
  title: "Álgebra Lineal y sus Aplicaciones",
  author: "David C. Lay",
  type: "book" | "article" | "thesis" | "magazine" | "other",
  description: "...",
  cover_url: "https://...",
  file_id: ObjectId | null,          // GridFS si hay PDF
  external_url: null,                // alternativa sin PDF
  tags: ["ingenieria", "matematicas"],
  language: "es",
  published_at: ISODate,
  status: "draft" | "published" | "archived",
  popularity: 0,                     // contador denormalizado de guardados
  rating_avg: 0,
  rating_count: 0,
  created_by: ObjectId,
  created_at: ISODate,
  updated_at: ISODate
}
```

Índices:
- Text index: `{ title: "text", author: "text", description: "text", tags: "text" }` con pesos.
- `{ tags: 1 }` (multikey).
- `{ popularity: -1 }`.
- `{ type: 1, published_at: -1 }`.
- `{ author: 1 }`.
- `{ rating_avg: -1, rating_count: -1 }`.
- `{ status: 1, created_at: -1 }`.

#### `collections` (biblioteca personal)

```js
{
  _id: ObjectId,
  user_id: ObjectId,
  content_id: ObjectId,
  added_at: ISODate
}
```

Índices:
- `{ user_id: 1, content_id: 1 }` único (evita duplicados).
- `{ user_id: 1, added_at: -1 }`.
- `{ content_id: 1 }`.

#### `reviews`

```js
{
  _id: ObjectId,
  user_id: ObjectId,
  content_id: ObjectId,
  rating: 1..5,
  comment: "Muy buen libro",
  created_at: ISODate,
  updated_at: ISODate
}
```

Índices:
- `{ user_id: 1, content_id: 1 }` único (una reseña por usuario/contenido).
- `{ content_id: 1, rating: -1 }`.
- `{ created_at: -1 }`.

#### `reading_progress` (opcional)

```js
{
  _id: ObjectId,
  user_id: ObjectId,
  content_id: ObjectId,
  current_page: 42,
  total_pages: 320,
  percentage: 13.1,
  updated_at: ISODate
}
```

Índice único: `{ user_id: 1, content_id: 1 }`.

#### `refresh_tokens` (opcional pero recomendado)

```js
{
  _id: ObjectId,
  user_id: ObjectId,
  token_hash: "sha256...",
  expires_at: ISODate,
  revoked_at: null,
  created_at: ISODate,
  user_agent: "...",
  ip: "..."
}
```

Índice TTL: `{ expires_at: 1 }` con `expireAfterSeconds: 0`.

### 5.2 Decisiones de modelado

| Relación | Decisión | Por qué |
|---|---|---|
| `contents.tags` | Embebido como array de strings | Acotado, se lee junto con el contenido, permite índice multikey y `$unwind` |
| `collections` | Colección separada | Crece sin límite, necesita índice único y agregaciones |
| `reviews` | Colección separada | Crece sin límite, una por usuario/contenido, se agrega con `$avg` |
| `reading_progress` | Colección separada | Un documento por usuario/contenido, actualización frecuente |
| `popularity`, `rating_avg`, `rating_count` | Campos denormalizados en `contents` | Lecturas rápidas sin agregar en cada request; se actualizan con `$inc`/recalculo |
| PDFs | GridFS (si se requiere) | Todo queda en MongoDB y no depende de otro servicio |

> Para mantener consistentes los contadores se pueden usar transacciones de MongoDB (Atlas M0 soporta replica set) o actualizaciones atómicas con recálculo periódico. En el plan se prioriza `$inc` atómico y un script de reconciliación.

### 5.3 GridFS y lectura de PDFs

- Bucket: `pdfs` (colecciones `pdfs.files` y `pdfs.chunks`).
- Cada PDF se asocia a un contenido mediante `contents.file_id`.
- Metadatos en `pdfs.files.metadata`: `content_id`, `uploaded_by`, `original_name`, `content_type`, `size`.
- Índice adicional: `{ "metadata.content_id": 1 }` en `pdfs.files`.
- Límites: máximo 15 MB por PDF, validación de firma `%PDF-`, MIME y extensión.
- Endpoints:
  - `POST /api/v1/contents/{id}/file` (admin, `multipart/form-data`): sube o reemplaza el PDF.
  - `GET /api/v1/contents/{id}/file`: streaming del PDF (requiere JWT).
  - `DELETE /api/v1/contents/{id}/file` (admin): elimina el PDF y limpia `file_id`.
  - `GET /api/v1/contents/{id}/file/metadata`: nombre, tamaño y tipo.
- El frontend descarga el PDF como `Blob` con el header `Authorization`, crea un `objectURL` y lo pasa a `react-pdf`; así el token no se expone en la URL.
- `react-pdf` reporta la página actual; el frontend llama a `PUT /api/v1/users/me/progress/{content_id}` para guardar `current_page`, `total_pages` y `percentage`.
- **Advertencia Atlas M0**: los PDFs comparten los 512 MB con los datos. Para la demo se incluirán pocos PDFs pequeños de dominio público (1-5 MB). Si se necesitan muchos archivos, migrar a Cloudinary/S3 o a un plan pago.
- En M0 no hay backups; para la demo basta con poder re-ejecutar el seed.

---

## 6. Las 10 consultas

Todas estarán agrupadas en Swagger bajo el tag **"Consultas MongoDB"** y tendrán ejemplos de request/response. Además, existirá `GET /api/v1/queries` para listar el catálogo de consultas desde el frontend.

| # | Endpoint | Qué devuelve | Operadores MongoDB | Índice principal |
|---|---|---|---|---|
| 1 | `GET /contents/search?q=` | Búsqueda full-text con relevancia | `$text`, `$meta: "textScore"`, `$facet` | Text index |
| 2 | `GET /contents` | Catálogo filtrado y paginado | `$match`, `$in`, `$gte/$lte`, `$facet`, `$sort` | `tags`, `type`, `published_at` |
| 3 | `GET /contents/popular` | Top contenidos por popularidad | `$sort`, `$limit`, `$lookup` | `popularity: -1` |
| 4 | `GET /contents/top-rated` | Mejor valorados con mínimo de reseñas | `$group`, `$avg`, `$sum`, `$match`, `$lookup` | `content_id`, `rating` |
| 5 | `GET /contents/by-author` | Agrupación por autor | `$group`, `$sum`, `$avg`, `$push` | `author: 1` |
| 6 | `GET /stats/tags` | Estadísticas por etiqueta | `$unwind`, `$group`, `$avg`, `$sum` | `tags: 1` |
| 7 | `GET /stats/most-saved` | Contenidos más guardados | `$group`, `$sum`, `$sort`, `$lookup` | `content_id: 1` |
| 8 | `GET /users/me/collection` | Mi biblioteca con datos del contenido | `$match`, `$lookup`, `$unwind`, `$project`, `$facet` | `user_id`, `added_at` |
| 9 | `GET /users/me/recommendations` | Recomendaciones por etiquetas afines | `$lookup` con pipeline, `$setIntersection`, `$size`, `$addToSet`, `$reduce` | `tags`, `popularity` |
| 10 | `GET /admin/dashboard` | Métricas globales del sistema | `$facet`, `$group`, `$dateToString`, `$count` | Varios |

### 6.1 Detalle de las consultas más importantes

#### Consulta 9 — Recomendaciones personalizadas

1. Obtener los `content_id` guardados por el usuario.
2. Obtener la unión de sus etiquetas.
3. Buscar contenidos que compartan al menos una etiqueta y que no estén guardados.
4. Puntuar por cantidad de etiquetas coincidentes y popularidad.
5. Si el usuario no tiene historial, devolver los populares como fallback.

Pipeline resumido:

```js
collections.aggregate([
  { $match: { user_id: userId } },
  { $lookup: { from: "contents", localField: "content_id", foreignField: "_id", as: "c" } },
  { $unwind: "$c" },
  {
    $group: {
      _id: null,
      savedIds: { $addToSet: "$content_id" },
      tags: { $addToSet: "$c.tags" }
    }
  },
  {
    $project: {
      savedIds: 1,
      tags: {
        $reduce: {
          input: "$tags",
          initialValue: [],
          in: { $setUnion: ["$$value", "$$this"] }
        }
      }
    }
  },
  {
    $lookup: {
      from: "contents",
      let: { tags: "$tags", saved: "$savedIds" },
      pipeline: [
        {
          $match: {
            $expr: {
              $and: [
                { $not: { $in: ["$_id", "$$saved"] } },
                { $gt: [{ $size: { $setIntersection: ["$tags", "$$tags"] } }, 0] }
              ]
            }
          }
        },
        {
          $addFields: {
            match_score: { $size: { $setIntersection: ["$tags", "$$tags"] } }
          }
        },
        { $sort: { match_score: -1, popularity: -1 } },
        { $limit: 10 }
      ],
      as: "recommendations"
    }
  },
  { $unwind: "$recommendations" },
  { $replaceRoot: { newRoot: "$recommendations" } }
])
```

#### Consulta 10 — Dashboard administrativo

Un solo endpoint que combina varias agregaciones:

- Totales: usuarios, contenidos, guardados, reseñas.
- Promedio global de calificaciones.
- Usuarios nuevos por mes (últimos 6 meses) con `$dateToString`.
- Contenidos por tipo.
- Top 5 etiquetas.
- Top 5 contenidos por guardados.
- Actividad reciente.

Se puede implementar con `$facet` sobre `contents` y consultas paralelas sobre las demás colecciones, combinadas en el servicio.

### 6.2 Modo demostración

- `GET /api/v1/queries`: devuelve nombre, descripción, endpoint, operadores usados e índice de cada una de las 10 consultas.
- `?explain=true` (solo admin o entorno demo): devuelve `explain("executionStats")` para que el docente vea el plan de ejecución y el uso de índices.
- Página `/queries` en el frontend: ejecuta cada consulta y muestra la tabla/JSON resultante. Ideal para la demostración.

---

## 7. Swagger y documentación

- Swagger UI: `https://<backend>.onrender.com/docs`
- ReDoc: `https://<backend>.onrender.com/redoc`
- OpenAPI JSON: `https://<backend>.onrender.com/openapi.json`
- Título: **Lector+ API**
- Descripción con flujo de autenticación y enlaces a los repos.
- Tags:
  - `Auth`
  - `Users`
  - `Contents`
  - `Collections`
  - `Reviews`
  - `Consultas MongoDB`
  - `Admin`
- Esquema de seguridad `HTTPBearer` para probar endpoints protegidos desde Swagger.
- Ejemplos de request/response en español.
- README con:
  - Arquitectura.
  - Cómo levantar localmente.
  - Variables de entorno.
  - Seed.
  - Las 10 consultas explicadas.
  - Guía de despliegue.
  - URLs de demo.
- Postman collection opcional (exportada desde OpenAPI).

---

## 8. Seguridad

- Hash de contraseñas con **Argon2id** (`pwdlib[argon2]`).
- JWT de acceso corto (15 min) + refresh token (7 días) con rotación.
- Refresh token hasheado en MongoDB y cookie `httpOnly`, `Secure`, `SameSite=None` en producción.
- Access token en memoria del frontend; al recargar se renueva con `/auth/refresh`.
- RBAC: `reader` y `admin`; dependencia `require_role("admin")`.
- Rate limiting en `/auth/login` y `/auth/register` con SlowAPI.
- CORS con lista blanca de orígenes.
- Validación estricta con Pydantic; nunca pasar diccionarios crudos a Mongo.
- Prevención de inyección NoSQL: no usar `$where`, no interpolar `$regex` con input del usuario; usar `$text`.
- Validación de archivos: MIME, extensión y tamaño máximo (ej. 10 MB) si se suben PDFs.
- Security headers: `X-Content-Type-Options`, `X-Frame-Options`, HSTS en producción.
- Secretos solo en variables de entorno; `.env.example` sin valores reales.
- Logs sin datos sensibles (no loggear passwords ni tokens).
- Swagger público para la demo; endpoints de admin protegidos con JWT.

---

## 9. Testing y calidad

### Backend

- `pytest` + `pytest-asyncio` + `httpx.AsyncClient`.
- Base de datos de test separada (Mongo local en Docker o Atlas de pruebas).
- Fixtures: usuario reader, usuario admin, contenidos, reseñas, tokens.
- Tests de:
  - Registro/login/refresh.
  - Permisos y roles.
  - CRUD de contenidos.
  - Guardar/quitar de colección.
  - Reseñas y cálculo de promedio.
  - Las 10 consultas con datos semilla.
- Cobertura objetivo: 80% en servicios y routers.
- Ruff + mypy en CI.

### Frontend

- Vitest + React Testing Library para componentes críticos.
- Tests de hooks de auth y del cliente API.
- Playwright (opcional) para flujos E2E: login, búsqueda, guardar, admin.
- ESLint + Prettier + `tsc --noEmit` en CI.

### CI/CD

GitHub Actions en cada repo:

- Backend: instalar dependencias, Ruff, mypy, pytest con servicio MongoDB.
- Frontend: instalar, ESLint, typecheck, tests, build.
- Deploy automático: Render y Vercel se conectan a `main`.
- Pre-commit hooks opcionales.

---

## 10. Despliegue gratuito

### 10.1 MongoDB Atlas (M0)

1. Crear cluster **M0** en la región más cercana.
2. Crear usuario de base de datos con permisos `readWrite` sobre `lector_plus`.
3. Network Access: `0.0.0.0/0` (Render free usa IPs dinámicas) o IPs permitidas si se usa un plan con IP fija.
4. Copiar el connection string SRV.
5. Ejecutar el seed apuntando a Atlas:
   ```bash
   MONGO_URI="mongodb+srv://..." python -m app.scripts.seed
   ```

**Límites M0**: 512 MB, sin backups, recursos compartidos. Suficiente para catálogo, reseñas y unos pocos PDFs pequeños (1-5 MB). Si se suben muchos PDFs, el espacio se agota rápido; en ese caso usar Cloudinary/S3 o un plan pago.

### 10.2 Backend en Render (free)

- Crear **Web Service** desde el repo `Plataforma-Lector-Api/Backend`.
- Runtime: Python 3.12.
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- Auto-deploy: `main`.
- Variables de entorno:
  ```
  ENV=production
  MONGO_URI=mongodb+srv://...
  MONGO_DB=lector_plus
  JWT_SECRET=<secreto-largo>
  ACCESS_TOKEN_EXPIRE_MINUTES=15
  REFRESH_TOKEN_EXPIRE_DAYS=7
  CORS_ORIGINS=https://<frontend>.vercel.app,http://localhost:5173
  COOKIE_SECURE=true
  COOKIE_SAMESITE=none
  ```
- Render free se duerme tras ~15 min de inactividad; el primer request puede tardar 30-60 s. Mitigación: UptimeRobot cada 5-10 min y estados de carga en el frontend.

### 10.3 Frontend en Vercel (Hobby)

- Importar el repo `Plataforma-Lector-Api/Frontend`.
- Framework preset: Vite.
- Build: `npm run build`; output: `dist`.
- Variable: `VITE_API_URL=https://<backend>.onrender.com/api/v1`.
- `vercel.json` con rewrite a `/index.html` para React Router.
- Dominio gratuito `*.vercel.app`.

### 10.4 UptimeRobot

- Monitor HTTP a `https://<backend>.onrender.com/health` cada 5-10 minutos.
- Reduce cold starts y avisa si el backend se cae.

### 10.5 Alternativas de despliegue

| Servicio | Nota |
|---|---|
| Koyeb | Free tier con scale-to-zero; alternativa a Render |
| Fly.io | Requiere tarjeta; free allowances limitadas |
| Railway | Sin free tier permanente |
| Netlify | Alternativa a Vercel para el frontend |
| Cloudflare Pages | Alternativa a Vercel |

> Recomendación: **Atlas + Render + Vercel** por simplicidad, TLS gratis y despliegue automático desde GitHub.

### 10.6 Variables de entorno

**Backend** (`.env.example`):

```env
ENV=development
APP_NAME=Lector+ API
API_V1_PREFIX=/api/v1
MONGO_URI=mongodb://localhost:27017
MONGO_DB=lector_plus
JWT_SECRET=change-me
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
CORS_ORIGINS=http://localhost:5173
COOKIE_SECURE=false
COOKIE_SAMESITE=lax
RATE_LIMIT_ENABLED=true
```

**Frontend** (`.env.example`):

```env
VITE_API_URL=http://localhost:8000/api/v1
VITE_APP_NAME=Lector+
```

---

## 11. Roadmap de implementación

| Fase | Entregable | Estimación |
|---|---|---|
| 0. Definiciones | Stack confirmado, repos, Atlas, variables, Docker Compose | 0.5-1 día |
| 1. Backend base | FastAPI, config, DB, logging, errores, health, OpenAPI, auth + RBAC | 1-2 días |
| 2. Modelo y CRUD | Users, contents, collections, reviews, progress, GridFS, índices, seed | 2 días |
| 3. 10 consultas | Endpoints, pipelines, ejemplos Swagger, catálogo `/queries`, tests | 1-2 días |
| 4. Frontend base | Vite/React/TS/Tailwind/shadcn, router, API client, auth, layout | 2-3 días |
| 5. Frontend features | Home, catálogo, detalle, biblioteca, reseñas, lector PDF + progreso, admin, `/queries` | 3 días |
| 6. Calidad y deploy | Tests, CI, Docker, Atlas/Render/Vercel, seed, UptimeRobot, README | 1-2 días |

**Total estimado**: 9-14 días de trabajo efectivo, 2-3 semanas a ritmo académico.

---

## 12. Entregables finales

1. **Backend** (`Plataforma-Lector-Api/Backend`):
   - API FastAPI versionada.
   - 10 consultas MongoDB documentadas.
   - Swagger/ReDoc.
   - Subida y streaming de PDFs con GridFS.
   - Tests y CI.
   - Dockerfile + docker-compose.
   - Seed reproducible (incluye PDFs de ejemplo).
   - README técnico.
2. **Frontend** (`Plataforma-Lector-Api/Frontend`):
   - SPA React + TypeScript.
   - Diseño responsive y accesible.
   - Integración completa con la API.
   - Lector de PDFs con `react-pdf` y progreso de lectura.
   - Página de demostración de las 10 consultas.
   - README.
3. **Demo en vivo**:
   - Frontend en Vercel.
   - Backend en Render.
   - Swagger público.
4. **Documentación**:
   - Arquitectura.
   - Modelo de datos.
   - Las 10 consultas explicadas.
   - Guía de despliegue.
   - Guion de demostración para la presentación.

---

## 13. Decisiones pendientes (preguntas)

**Resueltas:**

- Backend: FastAPI + Python.
- Frontend: React + Vite + TypeScript.
- PDFs: GridFS + `react-pdf`.
- Alcance: completo (reseñas, admin, progreso).
- Consultas: las 10 propuestas.

**Pendientes:**

1. **¿Cuál es la fecha de entrega y la rúbrica?** Para priorizar alcance.
2. **¿Ya tienes cuentas de Atlas, Render y Vercel?** ¿Hay alguna restricción de red o de país?
3. **¿Mantener la marca "Lector+" y los colores actuales o rediseñar la identidad visual?**
4. **¿Tienes PDFs de ejemplo o generamos/descargamos algunos de dominio público?**
5. **¿Quieres que empiece ya con el scaffolding del backend y el frontend?**

---

> **Siguiente paso sugerido**: confirmar las decisiones de la sección 13 y arrancar con la Fase 0-1 (estructura del backend, configuración, conexión a MongoDB, auth y Swagger). Luego se construye el frontend contra la API ya estable.
