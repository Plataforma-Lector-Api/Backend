from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient

from app.core.database import database
from app.core.security import hash_password
from app.main import app
from app.scripts.indexes import ensure_indexes

TEST_DB = "lector_plus_test"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    await database.connect()
    assert database.db is not None
    db = database.db
    await ensure_indexes(db)

    for name in ("users", "contents", "collections", "reviews", "reading_progress"):
        await db[name].delete_many({})

    now = datetime.now(UTC)
    admin_id = ObjectId()
    reader_id = ObjectId()
    await db.users.insert_many(
        [
            {
                "_id": admin_id,
                "name": "Admin Test",
                "email": "admin@test.com",
                "password_hash": hash_password("Admin123!"),
                "role": "admin",
                "status": "active",
                "created_at": now,
                "updated_at": now,
                "last_login_at": None,
            },
            {
                "_id": reader_id,
                "name": "Reader Test",
                "email": "reader@test.com",
                "password_hash": hash_password("Reader123!"),
                "role": "reader",
                "status": "active",
                "created_at": now,
                "updated_at": now,
                "last_login_at": None,
            },
        ]
    )

    first_id = ObjectId()
    second_id = ObjectId()
    await db.contents.insert_many(
        [
            {
                "_id": first_id,
                "title": "MongoDB aplicado",
                "author": "Ana Autora",
                "type": "book",
                "description": "Consultas y agregaciones con MongoDB.",
                "tags": ["mongodb", "bases-de-datos"],
                "language": "es",
                "published_at": datetime(2023, 1, 1, tzinfo=UTC),
                "status": "published",
                "popularity": 10,
                "rating_avg": 0.0,
                "rating_count": 0,
                "file_id": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "_id": second_id,
                "title": "FastAPI en práctica",
                "author": "Luis Autor",
                "type": "article",
                "description": "APIs modernas con Python.",
                "tags": ["python", "fastapi"],
                "language": "es",
                "published_at": datetime(2024, 1, 1, tzinfo=UTC),
                "status": "published",
                "popularity": 5,
                "rating_avg": 0.0,
                "rating_count": 0,
                "file_id": None,
                "created_at": now,
                "updated_at": now,
            },
        ]
    )
    await db.collections.insert_one(
        {
            "user_id": reader_id,
            "content_id": first_id,
            "added_at": now,
        }
    )
    await db.reviews.insert_one(
        {
            "user_id": reader_id,
            "content_id": first_id,
            "rating": 5,
            "comment": "Excelente.",
            "created_at": now,
            "updated_at": now,
        }
    )
    await db.contents.update_one(
        {"_id": first_id},
        {"$set": {"rating_avg": 5.0, "rating_count": 1}},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http

    await database.client.drop_database(TEST_DB)
    await database.disconnect()


async def login(client: AsyncClient, email: str, password: str) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_health_and_openapi(client: AsyncClient) -> None:
    assert (await client.get("/health")).json()["status"] == "ok"
    assert (await client.get("/ready")).status_code == 200
    openapi = (await client.get("/openapi.json")).json()
    assert "paths" in openapi
    assert "/api/v1/contents" in openapi["paths"]


async def test_login_and_profile(client: AsyncClient) -> None:
    tokens = await login(client, "reader@test.com", "Reader123!")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    profile = await client.get("/api/v1/auth/me", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["email"] == "reader@test.com"
    assert "password_hash" not in profile.json()


async def test_catalog_search_and_top_rated(client: AsyncClient) -> None:
    catalog = await client.get("/api/v1/contents")
    assert catalog.status_code == 200
    assert catalog.json()["meta"]["total"] == 2

    search = await client.get("/api/v1/contents/search", params={"q": "MongoDB"})
    assert search.status_code == 200
    assert search.json()["meta"]["total"] >= 1

    top_rated = await client.get("/api/v1/contents/top-rated")
    assert top_rated.status_code == 200
    assert top_rated.json()[0]["title"] == "MongoDB aplicado"


async def test_library_and_recommendations(client: AsyncClient) -> None:
    tokens = await login(client, "reader@test.com", "Reader123!")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    library = await client.get("/api/v1/collections/me", headers=headers)
    assert library.status_code == 200
    assert library.json()["meta"]["total"] == 1
    assert library.json()["data"][0]["content"]["title"] == "MongoDB aplicado"

    recommendations = await client.get(
        "/api/v1/collections/me/recommendations",
        headers=headers,
    )
    assert recommendations.status_code == 200
    assert all(item["title"] != "MongoDB aplicado" for item in recommendations.json())


async def test_admin_dashboard_and_permissions(client: AsyncClient) -> None:
    admin = await login(client, "admin@test.com", "Admin123!")
    reader = await login(client, "reader@test.com", "Reader123!")
    admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}
    reader_headers = {"Authorization": f"Bearer {reader['access_token']}"}

    dashboard = await client.get("/api/v1/admin/dashboard", headers=admin_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["totals"]["users"] == 2
    assert dashboard.json()["totals"]["contents"] == 2

    forbidden = await client.get("/api/v1/admin/dashboard", headers=reader_headers)
    assert forbidden.status_code == 403


async def test_query_catalog_endpoint(client: AsyncClient) -> None:
    response = await client.get("/api/v1/queries")
    assert response.status_code == 200
    assert len(response.json()) == 10


async def test_validation_error_format(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "no-es-correo", "password": "x"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
