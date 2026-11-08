"""Smoke test end-to-end contra una API en ejecución.

Uso:
    .venv\\Scripts\\python.exe tests\\smoke_live.py
"""

from __future__ import annotations

import sys

import httpx

BASE = "http://127.0.0.1:8000"
API = f"{BASE}/api/v1"

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  OK  {name}")
    else:
        failed += 1
        print(f"FAIL  {name} {detail}")


def main() -> int:
    client = httpx.Client(timeout=30.0)

    print("\n[Salud y documentación]")
    response = client.get(f"{BASE}/health")
    check("GET /health", response.status_code == 200, response.text)
    response = client.get(f"{BASE}/ready")
    check("GET /ready", response.status_code == 200, response.text)
    response = client.get(f"{BASE}/docs")
    check("GET /docs (Swagger)", response.status_code == 200)
    response = client.get(f"{BASE}/openapi.json")
    check(
        "GET /openapi.json",
        response.status_code == 200 and "paths" in response.json(),
    )

    print("\n[Autenticación]")
    response = client.post(
        f"{API}/auth/login",
        json={"email": "admin@lector.com", "password": "Admin123!"},
    )
    check("Login admin", response.status_code == 200, response.text)
    admin_tokens = response.json()
    admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    response = client.post(
        f"{API}/auth/login",
        json={"email": "lector@lector.com", "password": "Lector123!"},
    )
    check("Login lector", response.status_code == 200, response.text)
    reader_tokens = response.json()
    reader_headers = {"Authorization": f"Bearer {reader_tokens['access_token']}"}

    response = client.get(f"{API}/auth/me", headers=reader_headers)
    check(
        "GET /auth/me",
        response.status_code == 200 and response.json()["email"] == "lector@lector.com",
        response.text,
    )

    response = client.post(
        f"{API}/auth/refresh",
        json={"refresh_token": reader_tokens["refresh_token"]},
    )
    check("POST /auth/refresh", response.status_code == 200, response.text)
    reader_tokens = response.json()
    reader_headers = {"Authorization": f"Bearer {reader_tokens['access_token']}"}

    response = client.get(f"{API}/auth/me")
    check("Ruta protegida sin token -> 401", response.status_code == 401)

    print("\n[Consulta 1: búsqueda full-text]")
    response = client.get(f"{API}/contents/search", params={"q": "MongoDB"})
    payload = response.json()
    check(
        "GET /contents/search?q=MongoDB",
        response.status_code == 200 and payload["meta"]["total"] >= 1,
        response.text,
    )
    check(
        "Resultados ordenados por textScore",
        bool(payload.get("data")) and "score" in payload["data"][0],
    )

    print("\n[Consulta 2: catálogo filtrado]")
    response = client.get(
        f"{API}/contents",
        params={"tags": "programacion", "type": "book", "sort": "-popularity"},
    )
    payload = response.json()
    check(
        "GET /contents con filtros",
        response.status_code == 200 and payload["meta"]["total"] >= 3,
        response.text,
    )
    check(
        "Paginación con meta",
        {"page", "limit", "total", "total_pages"} <= payload["meta"].keys(),
    )

    print("\n[Consulta 3: populares]")
    response = client.get(f"{API}/contents/popular", params={"limit": 5})
    payload = response.json()
    check(
        "GET /contents/popular",
        response.status_code == 200 and len(payload) == 5,
        response.text,
    )
    popularities = [item["popularity"] for item in payload]
    check("Orden descendente por popularidad", popularities == sorted(popularities, reverse=True))

    print("\n[Consulta 4: mejor valorados]")
    response = client.get(f"{API}/contents/top-rated", params={"min_reviews": 2, "limit": 5})
    payload = response.json()
    check(
        "GET /contents/top-rated",
        response.status_code == 200 and len(payload) >= 1,
        response.text,
    )
    check(
        "Rating calculado por $avg",
        all(item["rating_count"] >= 2 for item in payload),
    )

    print("\n[Consulta 5: por autor]")
    response = client.get(f"{API}/contents/by-author", params={"limit": 20})
    payload = response.json()
    check(
        "GET /contents/by-author",
        response.status_code == 200 and len(payload) >= 1,
        response.text,
    )
    garcia = next((item for item in payload if item["author"] == "Gabriel García Márquez"), None)
    check(
        "Agrupación por autor con títulos",
        garcia is not None and garcia["total"] >= 2 and len(garcia["titles"]) >= 2,
    )

    print("\n[Consulta 6: estadísticas por etiqueta]")
    response = client.get(f"{API}/stats/tags", params={"limit": 10})
    payload = response.json()
    check(
        "GET /stats/tags",
        response.status_code == 200 and len(payload) == 10,
        response.text,
    )
    check(
        "Agregación con $unwind",
        all({"tag", "total", "avg_rating", "total_popularity"} <= item.keys() for item in payload),
    )

    print("\n[Consulta 7: más guardados]")
    response = client.get(f"{API}/stats/most-saved", params={"limit": 5})
    payload = response.json()
    check(
        "GET /stats/most-saved",
        response.status_code == 200 and len(payload) == 5,
        response.text,
    )
    check(
        "$lookup con contenido poblado",
        all(item["content"] and item["content"]["title"] for item in payload),
    )

    print("\n[Consulta 8: mi biblioteca]")
    response = client.get(f"{API}/collections/me", headers=reader_headers)
    payload = response.json()
    check(
        "GET /collections/me",
        response.status_code == 200 and payload["meta"]["total"] >= 8,
        response.text,
    )
    check(
        "Items con added_at y content",
        bool(payload["data"]) and {"added_at", "content"} <= payload["data"][0].keys(),
    )

    print("\n[Consulta 9: recomendaciones]")
    response = client.get(
        f"{API}/collections/me/recommendations",
        headers=reader_headers,
        params={"limit": 6},
    )
    payload = response.json()
    saved_titles = {
        item["content"]["title"]
        for item in client.get(f"{API}/collections/me", headers=reader_headers).json()["data"]
    }
    check(
        "GET /collections/me/recommendations",
        response.status_code == 200 and len(payload) >= 1,
        response.text,
    )
    check(
        "Recomendaciones fuera de la biblioteca",
        all(item["title"] not in saved_titles for item in payload),
    )

    print("\n[Consulta 10: dashboard admin]")
    response = client.get(f"{API}/admin/dashboard", headers=admin_headers)
    payload = response.json()
    check(
        "GET /admin/dashboard",
        response.status_code == 200,
        response.text,
    )
    check(
        "Métricas completas",
        {"totals", "average_rating", "users_per_month", "contents_per_type"} <= payload.keys(),
    )
    response = client.get(f"{API}/admin/dashboard", headers=reader_headers)
    check("Dashboard bloqueado a lectores -> 403", response.status_code == 403)

    print("\n[Catálogo de consultas]")
    response = client.get(f"{API}/queries")
    payload = response.json()
    check(
        "GET /queries devuelve 10 consultas",
        response.status_code == 200 and len(payload) == 10,
        response.text,
    )
    check(
        "Catálogo completo",
        all(item["number"] and item["endpoint"] and item["operators"] for item in payload),
    )

    print("\n[CRUD de contenidos y archivos GridFS]")
    response = client.get(f"{API}/contents", params={"limit": 50})
    contents = response.json()["data"]
    quijote = next(item for item in contents if item["title"] == "Don Quijote de la Mancha")
    check("Contenido tiene has_file", quijote["has_file"] is True, str(quijote))

    response = client.get(
        f"{API}/contents/{quijote['id']}/file/metadata",
        headers=reader_headers,
    )
    check(
        "Metadatos de PDF en GridFS",
        response.status_code == 200 and response.json()["size"] > 0,
        response.text,
    )

    response = client.get(f"{API}/contents/{quijote['id']}/file", headers=reader_headers)
    check(
        "Descarga de PDF desde GridFS",
        response.status_code == 200
        and response.headers["content-type"].startswith("application/pdf")
        and response.content.startswith(b"%PDF-"),
        response.text[:200],
    )

    response = client.get(f"{API}/contents/{quijote['id']}/file")
    check("PDF protegido sin token -> 401", response.status_code == 401)

    new_content = {
        "title": "Contenido de prueba smoke",
        "author": "Equipo Lector+",
        "type": "article",
        "description": "Creado por el smoke test y eliminado al final.",
        "tags": ["pruebas", "smoke"],
        "status": "published",
    }
    response = client.post(f"{API}/contents", json=new_content, headers=admin_headers)
    check("POST /contents (admin)", response.status_code == 201, response.text)
    created_id = response.json()["id"]

    response = client.patch(
        f"{API}/contents/{created_id}",
        json={"title": "Contenido de prueba actualizado"},
        headers=admin_headers,
    )
    check(
        "PATCH /contents/{id}",
        response.status_code == 200
        and response.json()["title"] == "Contenido de prueba actualizado",
        response.text,
    )

    response = client.delete(f"{API}/contents/{created_id}", headers=admin_headers)
    check("DELETE /contents/{id}", response.status_code == 200, response.text)

    print("\n[Reseñas y progreso]")
    response = client.post(
        f"{API}/contents/{quijote['id']}/reviews",
        json={"rating": 5, "comment": "Reseña del smoke test."},
        headers=reader_headers,
    )
    check("POST reseña", response.status_code == 200, response.text)

    response = client.get(f"{API}/contents/{quijote['id']}/reviews")
    check(
        "GET reseñas con nombre de usuario",
        response.status_code == 200 and any(item["user_name"] for item in response.json()["data"]),
        response.text,
    )

    response = client.put(
        f"{API}/users/me/progress/{quijote['id']}",
        json={"current_page": 200, "total_pages": 863},
        headers=reader_headers,
    )
    check(
        "PUT progreso de lectura",
        response.status_code == 200 and response.json()["percentage"] > 0,
        response.text,
    )

    response = client.get(f"{API}/users/me/progress", headers=reader_headers)
    check(
        "GET progreso con contenido poblado",
        response.status_code == 200 and len(response.json()) >= 1,
        response.text,
    )

    print("\n[Usuarios y admin]")
    response = client.get(f"{API}/admin/users", headers=admin_headers)
    check(
        "GET /admin/users",
        response.status_code == 200 and response.json()["meta"]["total"] >= 7,
        response.text,
    )

    response = client.patch(
        f"{API}/users/me",
        json={"bio": "Bio actualizada por smoke test."},
        headers=reader_headers,
    )
    check("PATCH /users/me", response.status_code == 200, response.text)

    response = client.post(
        f"{API}/auth/logout",
        json={"refresh_token": reader_tokens["refresh_token"]},
    )
    check("POST /auth/logout", response.status_code == 200, response.text)

    client.close()
    print(f"\nResultado: {passed} OK, {failed} fallos")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
