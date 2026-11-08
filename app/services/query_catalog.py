from __future__ import annotations

QUERY_CATALOG: list[dict] = [
    {
        "number": 1,
        "name": "Búsqueda full-text de contenidos",
        "description": (
            "Busca por título, autor, descripción y etiquetas usando el índice de texto "
            "y ordena por relevancia (textScore)."
        ),
        "method": "GET",
        "endpoint": "/api/v1/contents/search?q=mongodb",
        "operators": ["$text", "$meta: textScore", "$sort", "$facet"],
        "index": "Índice text sobre title, author, description y tags",
    },
    {
        "number": 2,
        "name": "Catálogo filtrado y paginado",
        "description": (
            "Filtra por etiquetas, tipo, idioma y rango de años; devuelve datos y metadata "
            "de paginación en una sola consulta con $facet."
        ),
        "method": "GET",
        "endpoint": "/api/v1/contents?tags=matematicas&type=book&sort=-popularity",
        "operators": [
            "$match",
            "$in",
            "$gte",
            "$lte",
            "$facet",
            "$sort",
            "$skip",
            "$limit",
        ],
        "index": "tags, type + published_at, popularity",
    },
    {
        "number": 3,
        "name": "Contenidos populares",
        "description": "Devuelve los contenidos con más guardados, ordenados por popularidad.",
        "method": "GET",
        "endpoint": "/api/v1/contents/popular?limit=10",
        "operators": ["$sort", "$limit"],
        "index": "popularity: -1",
    },
    {
        "number": 4,
        "name": "Contenidos mejor valorados",
        "description": (
            "Agrupa las reseñas por contenido, calcula el promedio y exige un mínimo de "
            "reseñas antes de unir con el contenido."
        ),
        "method": "GET",
        "endpoint": "/api/v1/contents/top-rated?min_reviews=1&limit=10",
        "operators": ["$group", "$avg", "$sum", "$match", "$sort", "$lookup", "$unwind"],
        "index": "reviews: content_id + rating",
    },
    {
        "number": 5,
        "name": "Contenidos agrupados por autor",
        "description": (
            "Agrupa por autor, cuenta títulos, calcula popularidad promedio y muestra títulos."
        ),
        "method": "GET",
        "endpoint": "/api/v1/contents/by-author?limit=20",
        "operators": ["$group", "$sum", "$avg", "$push", "$sort", "$project"],
        "index": "author: 1",
    },
    {
        "number": 6,
        "name": "Estadísticas por etiqueta",
        "description": (
            "Descompone el arreglo de etiquetas con $unwind y calcula cantidad, rating "
            "promedio y popularidad total por etiqueta."
        ),
        "method": "GET",
        "endpoint": "/api/v1/stats/tags?limit=20",
        "operators": ["$unwind", "$group", "$avg", "$sum", "$sort"],
        "index": "tags: 1 (multikey)",
    },
    {
        "number": 7,
        "name": "Contenidos más guardados",
        "description": (
            "Agrupa la colección de guardados por contenido, cuenta cuántas veces se guardó "
            "y une con el documento del contenido."
        ),
        "method": "GET",
        "endpoint": "/api/v1/stats/most-saved?limit=10",
        "operators": ["$group", "$sum", "$sort", "$limit", "$lookup", "$unwind"],
        "index": "collections: content_id",
    },
    {
        "number": 8,
        "name": "Mi biblioteca personal",
        "description": (
            "Filtra los guardados del usuario autenticado y une cada uno con su contenido "
            "usando $lookup, con paginación por $facet."
        ),
        "method": "GET",
        "endpoint": "/api/v1/collections/me?page=1&limit=12",
        "operators": ["$match", "$sort", "$facet", "$lookup", "$unwind", "$project"],
        "index": "collections: user_id + added_at",
    },
    {
        "number": 9,
        "name": "Recomendaciones personalizadas",
        "description": (
            "Toma las etiquetas de los contenidos guardados, calcula la intersección con "
            "otros contenidos y los ordena por coincidencia y popularidad."
        ),
        "method": "GET",
        "endpoint": "/api/v1/collections/me/recommendations?limit=10",
        "operators": [
            "$lookup con pipeline",
            "$setIntersection",
            "$size",
            "$addToSet",
            "$reduce",
            "$expr",
        ],
        "index": "tags + popularity",
    },
    {
        "number": 10,
        "name": "Dashboard administrativo",
        "description": (
            "Combina conteos, promedio global de rating, usuarios por mes, contenidos por "
            "tipo, top etiquetas, top contenidos y actividad reciente."
        ),
        "method": "GET",
        "endpoint": "/api/v1/admin/dashboard",
        "operators": ["$facet", "$group", "$dateToString", "$count", "$lookup"],
        "index": "Varios índices de apoyo",
    },
]
