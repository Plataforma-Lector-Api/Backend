"""Carga datos de demostración completos en MongoDB.

Uso:
    python -m app.scripts.seed            # borra y recrea los datos demo
    python -m app.scripts.seed --keep     # conserva datos existentes y hace upsert

Genera usuarios, 24 contenidos, reseñas, biblioteca personal, progreso de lectura
y tres PDFs reales almacenados en GridFS.
"""

from __future__ import annotations

import argparse
import asyncio
import random
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any

from bson import ObjectId
from fpdf import FPDF
from gridfs import AsyncGridFSBucket
from pymongo import AsyncMongoClient

from app.core.config import settings
from app.core.security import hash_password
from app.scripts.indexes import ensure_indexes
from app.utils.mongo import aggregate

rng = random.Random(42)

NOW = datetime.now(UTC)


def months_ago(months: int, day: int = 12) -> datetime:
    year = NOW.year
    month = NOW.month - months
    while month <= 0:
        month += 12
        year -= 1
    return datetime(year, month, min(day, 28), 10, 30, tzinfo=UTC)


USERS: list[dict[str, Any]] = [
    {
        "email": "admin@lector.com",
        "name": "Valeria Admin",
        "password": "Admin123!",
        "role": "admin",
        "bio": "Administradora de la plataforma y curadora del catálogo.",
        "created_at": months_ago(10),
    },
    {
        "email": "lector@lector.com",
        "name": "Byron Lector",
        "password": "Lector123!",
        "role": "reader",
        "bio": "Lector voraz de narrativa latinoamericana y tecnología.",
        "created_at": months_ago(9),
    },
    {
        "email": "maria@lector.com",
        "name": "María Fernández",
        "password": "Lector123!",
        "role": "reader",
        "bio": "Estudiante de literatura comparada.",
        "created_at": months_ago(8),
    },
    {
        "email": "carlos@lector.com",
        "name": "Carlos Ramírez",
        "password": "Lector123!",
        "role": "reader",
        "bio": "Ingeniero de software aficionado a la ciencia ficción.",
        "created_at": months_ago(6),
    },
    {
        "email": "lucia@lector.com",
        "name": "Lucía Torres",
        "password": "Lector123!",
        "role": "reader",
        "bio": "Investigadora en inteligencia artificial y educación.",
        "created_at": months_ago(4),
    },
    {
        "email": "diego@lector.com",
        "name": "Diego Morales",
        "password": "Lector123!",
        "role": "reader",
        "bio": "Docente, poeta y lector de ensayos.",
        "created_at": months_ago(2),
    },
    {
        "email": "sofia@lector.com",
        "name": "Sofía Herrera",
        "password": "Lector123!",
        "role": "reader",
        "bio": "Periodista cultural y reseñista.",
        "created_at": months_ago(1),
    },
]

CONTENTS: list[dict[str, Any]] = [
    {
        "seed_key": "cien-anos",
        "title": "Cien años de soledad",
        "author": "Gabriel García Márquez",
        "type": "book",
        "description": (
            "La saga de la familia Buendía en el mítico pueblo de Macondo, obra cumbre "
            "del realismo mágico y de la literatura latinoamericana."
        ),
        "tags": ["novela", "realismo-magico", "clasico", "latinoamerica"],
        "published_year": 1967,
        "popularity": 96,
    },
    {
        "seed_key": "don-quijote",
        "title": "Don Quijote de la Mancha",
        "author": "Miguel de Cervantes",
        "type": "book",
        "description": (
            "Las aventuras del ingenioso hidalgo y su fiel escudero Sancho Panza, "
            "una de las obras fundacionales de la novela moderna."
        ),
        "tags": ["novela", "clasico", "aventura", "siglo-de-oro"],
        "published_year": 1605,
        "popularity": 91,
    },
    {
        "seed_key": "casa-espiritus",
        "title": "La casa de los espíritus",
        "author": "Isabel Allende",
        "type": "book",
        "description": (
            "Cuatro generaciones de la familia Trueba retratan los cambios políticos "
            "y sociales de Chile durante el siglo XX."
        ),
        "tags": ["novela", "realismo-magico", "familia", "latinoamerica"],
        "published_year": 1982,
        "popularity": 84,
    },
    {
        "seed_key": "rayuela",
        "title": "Rayuela",
        "author": "Julio Cortázar",
        "type": "book",
        "description": (
            "Novela experimental que invita al lector a elegir entre dos órdenes de "
            "lectura para seguir la historia de Horacio Oliveira y La Maga."
        ),
        "tags": ["novela", "experimental", "clasico", "paris"],
        "published_year": 1963,
        "popularity": 78,
    },
    {
        "seed_key": "amor-colera",
        "title": "El amor en los tiempos del cólera",
        "author": "Gabriel García Márquez",
        "type": "book",
        "description": (
            "Una historia de amor que atraviesa más de medio siglo y explora la "
            "espera, la memoria y la vejez."
        ),
        "tags": ["novela", "romance", "latinoamerica", "clasico"],
        "published_year": 1985,
        "popularity": 80,
    },
    {
        "seed_key": "pedro-paramo",
        "title": "Pedro Páramo",
        "author": "Juan Rulfo",
        "type": "book",
        "description": (
            "Juan Preciado llega a Comala buscando a su padre y encuentra un pueblo "
            "habitado por voces y recuerdos."
        ),
        "tags": ["novela", "clasico", "mexico", "realismo-magico"],
        "published_year": 1955,
        "popularity": 75,
    },
    {
        "seed_key": "ficciones",
        "title": "Ficciones",
        "author": "Jorge Luis Borges",
        "type": "book",
        "description": (
            "Relatos que juegan con infinitos, laberintos, bibliotecas y espejos; "
            "una de las cumbres del cuento fantástico."
        ),
        "tags": ["cuento", "fantastico", "clasico", "argentina"],
        "published_year": 1944,
        "popularity": 82,
    },
    {
        "seed_key": "ciudad-perros",
        "title": "La ciudad y los perros",
        "author": "Mario Vargas Llosa",
        "type": "book",
        "description": (
            "La vida en un colegio militar de Lima revela la violencia, el honor y "
            "las jerarquías de una sociedad."
        ),
        "tags": ["novela", "drama", "latinoamerica", "clasico"],
        "published_year": 1963,
        "popularity": 71,
    },
    {
        "seed_key": "veinte-poemas",
        "title": "Veinte poemas de amor y una canción desesperada",
        "author": "Pablo Neruda",
        "type": "book",
        "description": (
            "Poemario que convirtió el amor adolescente en materia universal y "
            "consagró la voz lírica de Neruda."
        ),
        "tags": ["poesia", "romance", "clasico", "chile"],
        "published_year": 1924,
        "popularity": 74,
    },
    {
        "seed_key": "martin-fierro",
        "title": "Martín Fierro",
        "author": "José Hernández",
        "type": "book",
        "description": (
            "Poema gauchesco que narra las penurias del gaucho argentino y se "
            "convirtió en emblema de la identidad nacional."
        ),
        "tags": ["poesia", "clasico", "argentina", "gauchesco"],
        "published_year": 1872,
        "popularity": 52,
    },
    {
        "seed_key": "breve-historia",
        "title": "Breve historia del tiempo",
        "author": "Stephen Hawking",
        "type": "book",
        "description": (
            "Una introducción accesible al origen del universo, los agujeros negros "
            "y la naturaleza del tiempo."
        ),
        "tags": ["ciencia", "fisica", "divulgacion", "universo"],
        "published_year": 1988,
        "popularity": 69,
    },
    {
        "seed_key": "sapiens",
        "title": "Sapiens: De animales a dioses",
        "author": "Yuval Noah Harari",
        "type": "book",
        "description": (
            "Un recorrido por la historia de la humanidad, desde las primeras "
            "revoluciones cognitivas hasta la era de la información."
        ),
        "tags": ["historia", "ciencia", "ensayo", "divulgacion"],
        "published_year": 2011,
        "popularity": 88,
    },
    {
        "seed_key": "pensar-rapido",
        "title": "Pensar rápido, pensar despacio",
        "author": "Daniel Kahneman",
        "type": "book",
        "description": (
            "El premio Nobel de Economía explica los dos sistemas de pensamiento que "
            "guían nuestras decisiones y sesgos."
        ),
        "tags": ["psicologia", "ensayo", "decisiones", "divulgacion"],
        "published_year": 2011,
        "popularity": 77,
    },
    {
        "seed_key": "clean-code",
        "title": "Clean Code",
        "author": "Robert C. Martin",
        "type": "book",
        "description": (
            "Principios, patrones y prácticas para escribir código legible, "
            "mantenible y profesional."
        ),
        "tags": ["programacion", "tecnologia", "buenas-practicas", "software"],
        "published_year": 2008,
        "popularity": 86,
    },
    {
        "seed_key": "arte-guerra",
        "title": "El arte de la guerra",
        "author": "Sun Tzu",
        "type": "book",
        "description": (
            "Tratado clásico sobre estrategia, liderazgo y conflicto, vigente en "
            "negocios, deportes y vida cotidiana."
        ),
        "tags": ["estrategia", "clasico", "liderazgo", "filosofia"],
        "published_year": 1999,
        "popularity": 73,
    },
    {
        "seed_key": "algoritmos",
        "title": "Introducción a los algoritmos",
        "author": "Thomas H. Cormen",
        "type": "book",
        "description": (
            "Manual de referencia sobre análisis de algoritmos, estructuras de datos "
            "y complejidad computacional."
        ),
        "tags": ["programacion", "matematicas", "algoritmos", "software"],
        "published_year": 2009,
        "popularity": 68,
    },
    {
        "seed_key": "ia-moderna",
        "title": "Inteligencia artificial moderna",
        "author": "Stuart Russell",
        "type": "book",
        "description": (
            "Panorama de los métodos, modelos y desafíos éticos de la inteligencia "
            "artificial contemporánea."
        ),
        "tags": ["ia", "tecnologia", "etica", "software"],
        "published_year": 2020,
        "popularity": 83,
    },
    {
        "seed_key": "python-estructuras",
        "title": "Estructuras de datos en Python",
        "author": "Andrés López",
        "type": "book",
        "description": (
            "Guía práctica para implementar listas, pilas, colas, árboles y grafos "
            "con Python moderno."
        ),
        "tags": ["programacion", "python", "estructuras-de-datos", "software"],
        "published_year": 2021,
        "popularity": 64,
    },
    {
        "seed_key": "mongodb-accion",
        "title": "MongoDB en acción",
        "author": "Kyle Banker",
        "type": "book",
        "description": (
            "Diseño de esquemas, consultas, agregaciones e indexación para "
            "aplicaciones con MongoDB."
        ),
        "tags": ["bases-de-datos", "mongodb", "programacion", "software"],
        "published_year": 2011,
        "popularity": 66,
    },
    {
        "seed_key": "ia-educacion",
        "title": "El impacto de la IA en la educación",
        "author": "Lucía Torres",
        "type": "article",
        "description": (
            "Análisis de oportunidades y riesgos de integrar asistentes de "
            "inteligencia artificial en el aula universitaria."
        ),
        "tags": ["ia", "educacion", "investigacion", "tecnologia"],
        "published_year": 2024,
        "popularity": 58,
    },
    {
        "seed_key": "lectura-digital",
        "title": "Hábitos de lectura digital en América Latina",
        "author": "Sofía Herrera",
        "type": "article",
        "description": (
            "Datos recientes sobre dispositivos, formatos y tiempos de lectura en "
            "siete países de la región."
        ),
        "tags": ["lectura", "cultura", "investigacion", "digital"],
        "published_year": 2023,
        "popularity": 49,
    },
    {
        "seed_key": "tesis-mongodb",
        "title": "Análisis de datos con MongoDB para bibliotecas digitales",
        "author": "Carlos Ramírez",
        "type": "thesis",
        "description": (
            "Tesis de maestría sobre modelado documental, agregaciones y "
            "recomendaciones en catálogos bibliográficos."
        ),
        "tags": ["bases-de-datos", "mongodb", "investigacion", "bibliotecas"],
        "published_year": 2022,
        "popularity": 41,
    },
    {
        "seed_key": "letras-42",
        "title": "Letras Hispanoamericanas #42",
        "author": "Revista Lector",
        "type": "magazine",
        "description": (
            "Dossier sobre nuevas voces de la narrativa latinoamericana, entrevistas "
            "y reseñas de las novedades del semestre."
        ),
        "tags": ["literatura", "cultura", "revista", "latinoamerica"],
        "published_year": 2024,
        "popularity": 37,
    },
    {
        "seed_key": "lectura-politica",
        "title": "La lectura como acto político",
        "author": "Diego Morales",
        "type": "other",
        "description": (
            "Ensayo sobre bibliotecas públicas, acceso al conocimiento y el derecho "
            "a leer como práctica ciudadana."
        ),
        "tags": ["ensayo", "cultura", "lectura", "politica"],
        "published_year": 2020,
        "popularity": 45,
    },
    {
        "seed_key": "borrador-ia",
        "title": "Ética de los modelos generativos",
        "author": "Lucía Torres",
        "type": "article",
        "description": (
            "Borrador en revisión sobre sesgos, transparencia y responsabilidad en "
            "sistemas generativos."
        ),
        "tags": ["ia", "etica", "investigacion"],
        "published_year": 2025,
        "popularity": 0,
        "status": "draft",
    },
    {
        "seed_key": "archivado-mito",
        "title": "Mitología y territorio en la narrativa andina",
        "author": "María Fernández",
        "type": "thesis",
        "description": (
            "Investigación archivada sobre símbolos, paisajes y oralidad en la "
            "literatura de los Andes."
        ),
        "tags": ["investigacion", "literatura", "andes"],
        "published_year": 2019,
        "popularity": 12,
        "status": "archived",
    },
]

REVIEWS: dict[str, list[tuple[str, int, str]]] = {
    "lector@lector.com": [
        ("cien-anos", 5, "Una obra total. Macondo se queda con uno para siempre."),
        ("don-quijote", 5, "Sigue siendo divertida, triste y profundamente humana."),
        ("clean-code", 4, "Muy útil, aunque algunos consejos dependen del contexto."),
        ("mongodb-accion", 5, "La mejor introducción práctica a MongoDB que he leído."),
        ("ficciones", 5, "Borges reescribe el infinito en pocas páginas."),
        ("ia-moderna", 4, "Completo y riguroso; ideal como referencia."),
        ("pedro-paramo", 4, "Denso y fascinante. Hay que leerlo dos veces."),
        ("sapiens", 4, "Amplio y provocador, aunque simplifica algunos debates."),
    ],
    "maria@lector.com": [
        ("cien-anos", 5, "La mejor novela que he leído este año."),
        ("casa-espiritus", 4, "Personajes memorables y una atmósfera única."),
        ("rayuela", 5, "Jugar con el orden de lectura cambia la experiencia."),
        ("veinte-poemas", 5, "Poesía que se siente cercana incluso un siglo después."),
        ("pedro-paramo", 5, "Comala es un personaje más, y de los mejores."),
        ("letras-42", 4, "Buen dossier, con voces nuevas muy interesantes."),
        ("ficciones", 4, "Cada relato exige una segunda lectura."),
    ],
    "carlos@lector.com": [
        ("clean-code", 5, "Debería ser lectura obligatoria en cualquier equipo."),
        ("algoritmos", 4, "Exhaustivo. No es ligero, pero vale cada página."),
        ("python-estructuras", 4, "Ejemplos claros y bien estructurados."),
        ("mongodb-accion", 4, "Muy buen puente entre teoría y práctica."),
        ("ia-moderna", 5, "El capítulo de ética es especialmente valioso."),
        ("tesis-mongodb", 4, "Un caso de estudio muy aplicable."),
        ("clean-code", 4, "Relectura recomendada para refactorizar con criterio."),
    ],
    "lucia@lector.com": [
        ("ia-moderna", 5, "Una referencia imprescindible para investigar en IA."),
        ("ia-educacion", 4, "Aterriza el debate con datos y casos concretos."),
        ("sapiens", 4, "Me ayudó a ordenar ideas sobre historia y tecnología."),
        ("pensar-rapido", 5, "Explica sesgos que uno reconoce en sí mismo."),
        ("breve-historia", 4, "Divulgación exigente pero accesible."),
        ("tesis-mongodb", 4, "Buena metodología y conclusiones claras."),
    ],
    "diego@lector.com": [
        ("veinte-poemas", 4, "Neruda en estado puro."),
        ("martin-fierro", 4, "Un clásico que gana cuando se lee en voz alta."),
        ("lectura-politica", 5, "Un ensayo necesario sobre el derecho a leer."),
        ("pedro-paramo", 4, "Rulfo construye silencios que pesan."),
        ("don-quijote", 4, "Cada generación encuentra algo distinto en él."),
        ("arte-guerra", 3, "Interesante, aunque a veces demasiado aforístico."),
    ],
    "sofia@lector.com": [
        ("lectura-digital", 5, "Datos actuales y una mirada crítica muy útil."),
        ("letras-42", 5, "Excelente selección de nuevas voces."),
        ("casa-espiritus", 4, "Una saga familiar que atrapa desde la primera página."),
        ("ia-educacion", 3, "Buen punto de partida, aunque pide más evidencia empírica."),
        ("cien-anos", 5, "Releerlo es descubrir otro libro dentro."),
        ("lectura-politica", 4, "Invita a pensar el acceso a los libros como política pública."),
    ],
    "admin@lector.com": [
        ("sapiens", 5, "Un mapa general útil para conversaciones interdisciplinarias."),
        ("clean-code", 4, "Buen estándar para revisar código en equipo."),
        ("mongodb-accion", 4, "Sólido para diseñar el modelo de datos."),
        ("ia-moderna", 4, "Actualizado y bien organizado."),
    ],
}

COLLECTIONS: dict[str, list[str]] = {
    "lector@lector.com": [
        "cien-anos",
        "don-quijote",
        "clean-code",
        "mongodb-accion",
        "ficciones",
        "ia-moderna",
        "pedro-paramo",
        "sapiens",
    ],
    "maria@lector.com": [
        "cien-anos",
        "casa-espiritus",
        "rayuela",
        "veinte-poemas",
        "pedro-paramo",
        "ficciones",
    ],
    "carlos@lector.com": [
        "clean-code",
        "algoritmos",
        "python-estructuras",
        "mongodb-accion",
        "ia-moderna",
        "tesis-mongodb",
    ],
    "lucia@lector.com": [
        "ia-moderna",
        "ia-educacion",
        "sapiens",
        "pensar-rapido",
        "breve-historia",
        "tesis-mongodb",
    ],
    "diego@lector.com": [
        "veinte-poemas",
        "martin-fierro",
        "lectura-politica",
        "pedro-paramo",
        "don-quijote",
    ],
    "sofia@lector.com": [
        "lectura-digital",
        "letras-42",
        "casa-espiritus",
        "ia-educacion",
        "cien-anos",
        "lectura-politica",
    ],
}

PROGRESS: dict[str, list[tuple[str, int, int]]] = {
    "lector@lector.com": [
        ("cien-anos", 2, 5),
        ("don-quijote", 3, 5),
        ("clean-code", 1, 5),
        ("mongodb-accion", 45, 312),
        ("ficciones", 90, 174),
    ],
    "maria@lector.com": [
        ("cien-anos", 320, 471),
        ("rayuela", 410, 600),
        ("pedro-paramo", 132, 132),
    ],
    "carlos@lector.com": [
        ("clean-code", 464, 464),
        ("algoritmos", 180, 1312),
        ("python-estructuras", 95, 280),
    ],
    "lucia@lector.com": [
        ("ia-moderna", 400, 1136),
        ("pensar-rapido", 250, 499),
    ],
    "diego@lector.com": [
        ("veinte-poemas", 80, 96),
        ("lectura-politica", 40, 120),
    ],
    "sofia@lector.com": [
        ("lectura-digital", 22, 48),
        ("letras-42", 60, 80),
    ],
}

PDFS: dict[str, tuple[str, str, list[str]]] = {
    "don-quijote": (
        "don-quijote-fragmento.pdf",
        "Don Quijote de la Mancha (fragmento)",
        [
            "En un lugar de la Mancha, de cuyo nombre no quiero acordarme, no ha mucho "
            "tiempo que vivía un hidalgo de los de lanza en astillero, adarga antigua, "
            "rocín flaco y galgo corredor.",
            "Una olla de algo más vaca que carnero, salpicón las más noches, duelos y "
            "quebrantos los sábados, lentejas los viernes, algún palomino de añadidura "
            "los domingos, consumían las tres partes de su hacienda.",
            "El resto della concluían sayo de velarte, calzas de velludo para las fiestas, "
            "con sus pantuflos de lo mismo, y los días de entresemana se honraba con su "
            "vellorí de lo más fino.",
            "Con estas razones perdía el pobre caballero el juicio, y desvelábase por "
            "entenderlas y desentrañarles el sentido, que no se lo sacara ni las "
            "entendiera el mismo Aristóteles si resucitara para sólo ello.",
        ],
    ),
    "cien-anos": (
        "cien-anos-fragmento.pdf",
        "Cien años de soledad (fragmento)",
        [
            "Muchos años después, frente al pelotón de fusilamiento, el coronel Aureliano "
            "Buendía había de recordar aquella tarde remota en que su padre lo llevó a "
            "conocer el hielo.",
            "Macondo era entonces una aldea de veinte casas de barro y cañabrava "
            "construidas a la orilla de un río de aguas diáfanas que se precipitaban por "
            "un lecho de piedras pulidas, blancas y enormes como huevos prehistóricos.",
            "El mundo era tan reciente, que muchas cosas carecían de nombre, y para "
            "mencionarlas había que señalarlas con el dedo.",
            "Todos los años, por el mes de marzo, una familia de gitanos desarrapados "
            "plantaba su carpa cerca de la aldea, y con un grande alboroto de pitos y "
            "timbalillos daba a conocer los nuevos inventos.",
        ],
    ),
    "clean-code": (
        "clean-code-resumen.pdf",
        "Clean Code: principios esenciales",
        [
            "El código limpio es aquel que otro desarrollador puede entender y mantener "
            "sin necesidad de explicaciones adicionales. La claridad es una inversión, "
            "no un lujo.",
            "Los nombres deben revelar intención: una variable llamada diasDesdeUltimoLogin "
            "comunica mucho más que d. Las funciones deben hacer una sola cosa y hacerla bien.",
            "Los comentarios explican el porqué, no el qué. Si el código necesita un "
            "comentario para explicar qué hace, probablemente pueda reescribirse con mayor "
            "claridad.",
            "Las pruebas automatizadas son la red de seguridad de la refactorización. Sin "
            "ellas, cada cambio es una apuesta; con ellas, la mejora continua se vuelve viable.",
        ],
    ),
}


def build_pdf(title: str, author: str, paragraphs: list[str]) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.multi_cell(0, 10, title)
    pdf.set_font("Helvetica", "I", 12)
    pdf.cell(0, 10, author, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("Helvetica", size=11)
    for paragraph in paragraphs:
        pdf.add_page()
        pdf.multi_cell(0, 6, paragraph)
    pdf.set_y(-24)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 8, "Lector+ | Plataforma de lectura digital", align="C")
    return bytes(pdf.output())


async def seed(keep: bool = False) -> None:
    client = AsyncMongoClient(settings.mongo_uri, tz_aware=True)
    db = client[settings.mongo_db]
    await client.admin.command("ping")
    print(f"Conectado a MongoDB: {settings.mongo_db}")

    if not keep:
        for name in (
            "users",
            "contents",
            "collections",
            "reviews",
            "reading_progress",
            "refresh_tokens",
            "pdfs.files",
            "pdfs.chunks",
        ):
            await db[name].delete_many({})
        print("Datos anteriores eliminados")

    await ensure_indexes(db)

    user_ids: dict[str, ObjectId] = {}
    for item in USERS:
        user_id = ObjectId()
        document = {
            "_id": user_id,
            "name": item["name"],
            "email": item["email"],
            "password_hash": hash_password(item["password"]),
            "role": item["role"],
            "status": "active",
            "avatar_url": None,
            "bio": item["bio"],
            "created_at": item["created_at"],
            "updated_at": item["created_at"],
            "last_login_at": None,
        }
        await db.users.replace_one({"email": item["email"]}, document, upsert=True)
        existing = await db.users.find_one({"email": item["email"]})
        user_ids[item["email"]] = existing["_id"]
    print(f"Usuarios cargados: {len(user_ids)}")

    content_ids: dict[str, ObjectId] = {}
    for item in CONTENTS:
        status = item.get("status", "published")
        published_at = datetime(item["published_year"], 6, 15, tzinfo=UTC)
        document = {
            "_id": ObjectId(),
            "seed_key": item["seed_key"],
            "title": item["title"],
            "author": item["author"],
            "type": item["type"],
            "description": item["description"],
            "cover_url": None,
            "external_url": None,
            "tags": item["tags"],
            "language": "es",
            "published_at": published_at,
            "status": status,
            "popularity": item["popularity"],
            "rating_avg": 0.0,
            "rating_count": 0,
            "file_id": None,
            "created_by": user_ids["admin@lector.com"],
            "created_at": NOW - timedelta(days=rng.randint(10, 300)),
            "updated_at": NOW - timedelta(days=rng.randint(0, 9)),
        }
        await db.contents.replace_one({"seed_key": item["seed_key"]}, document, upsert=True)
        existing = await db.contents.find_one({"seed_key": item["seed_key"]})
        content_ids[item["seed_key"]] = existing["_id"]
    print(f"Contenidos cargados: {len(content_ids)}")

    reviews_count = 0
    seen_pairs: set[tuple[str, str]] = set()
    for email, entries in REVIEWS.items():
        for seed_key, rating, comment in entries:
            pair = (email, seed_key)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            created_at = NOW - timedelta(days=rng.randint(1, 240))
            await db.reviews.update_one(
                {
                    "user_id": user_ids[email],
                    "content_id": content_ids[seed_key],
                },
                {
                    "$set": {
                        "rating": rating,
                        "comment": comment,
                        "updated_at": created_at,
                    },
                    "$setOnInsert": {"created_at": created_at},
                },
                upsert=True,
            )
            reviews_count += 1
    print(f"Reseñas cargadas: {reviews_count}")

    collections_count = 0
    for email, seed_keys in COLLECTIONS.items():
        for seed_key in seed_keys:
            added_at = NOW - timedelta(days=rng.randint(1, 120))
            await db.collections.update_one(
                {
                    "user_id": user_ids[email],
                    "content_id": content_ids[seed_key],
                },
                {"$setOnInsert": {"added_at": added_at}},
                upsert=True,
            )
            collections_count += 1
    print(f"Guardados en bibliotecas: {collections_count}")

    progress_count = 0
    for email, entries in PROGRESS.items():
        for seed_key, current_page, total_pages in entries:
            percentage = round(min(100.0, current_page / total_pages * 100), 1)
            updated_at = NOW - timedelta(days=rng.randint(0, 20))
            await db.reading_progress.update_one(
                {
                    "user_id": user_ids[email],
                    "content_id": content_ids[seed_key],
                },
                {
                    "$set": {
                        "current_page": current_page,
                        "total_pages": total_pages,
                        "percentage": percentage,
                        "updated_at": updated_at,
                    },
                    "$setOnInsert": {"created_at": updated_at},
                },
                upsert=True,
            )
            progress_count += 1
    print(f"Progresos de lectura: {progress_count}")

    rating_pipeline = [
        {
            "$group": {
                "_id": "$content_id",
                "avg_rating": {"$avg": "$rating"},
                "review_count": {"$sum": 1},
            }
        }
    ]
    ratings = await aggregate(db.reviews, rating_pipeline)
    for item in ratings:
        await db.contents.update_one(
            {"_id": item["_id"]},
            {
                "$set": {
                    "rating_avg": round(float(item["avg_rating"]), 2),
                    "rating_count": int(item["review_count"]),
                }
            },
        )

    save_counts = await aggregate(
        db.collections,
        [{"$group": {"_id": "$content_id", "saves": {"$sum": 1}}}],
    )
    saves_by_content = {item["_id"]: item["saves"] for item in save_counts}
    for seed_key, content_id in content_ids.items():
        base = next(item["popularity"] for item in CONTENTS if item["seed_key"] == seed_key)
        popularity = base + saves_by_content.get(content_id, 0) * 3
        await db.contents.update_one(
            {"_id": content_id},
            {"$set": {"popularity": popularity}},
        )

    bucket = AsyncGridFSBucket(db, bucket_name="pdfs")
    pdf_count = 0
    for seed_key, (filename, title, paragraphs) in PDFS.items():
        content = await db.contents.find_one({"seed_key": seed_key})
        if content is None:
            continue
        if content.get("file_id"):
            try:
                await bucket.delete(content["file_id"])
            except Exception:
                pass
        data = build_pdf(title, content["author"], paragraphs)
        file_id = await bucket.upload_from_stream(
            filename,
            BytesIO(data),
            metadata={
                "content_id": content["_id"],
                "uploaded_by": user_ids["admin@lector.com"],
                "content_type": "application/pdf",
                "size": len(data),
            },
        )
        await db.contents.update_one({"_id": content["_id"]}, {"$set": {"file_id": file_id}})
        pdf_count += 1
        print(f"  PDF subido a GridFS: {filename} ({len(data) / 1024:.1f} KB)")
    print(f"PDFs cargados: {pdf_count}")

    totals = {
        "usuarios": await db.users.count_documents({}),
        "contenidos": await db.contents.count_documents({}),
        "reseñas": await db.reviews.count_documents({}),
        "guardados": await db.collections.count_documents({}),
        "progresos": await db.reading_progress.count_documents({}),
        "archivos_gridfs": await db["pdfs.files"].count_documents({}),
    }
    print("\nResumen final:")
    for key, value in totals.items():
        print(f"  {key}: {value}")
    print(
        "\nCredenciales demo:\n"
        "  Admin:  admin@lector.com / Admin123!\n"
        "  Lector: lector@lector.com / Lector123!"
    )

    await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga datos demo en MongoDB")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Conserva los datos existentes y solo hace upsert",
    )
    args = parser.parse_args()
    asyncio.run(seed(keep=args.keep))


if __name__ == "__main__":
    main()
