from __future__ import annotations

from typing import Any

from pymongo.asynchronous.collection import AsyncCollection


async def aggregate(
    collection: AsyncCollection,
    pipeline: list[dict[str, Any]],
    *,
    length: int | None = None,
) -> list[dict[str, Any]]:
    """Ejecuta un pipeline async y devuelve la lista de resultados.

    En PyMongo async, ``collection.aggregate()`` es una corrutina que devuelve
    un ``AsyncCommandCursor``; hay que esperar ambos pasos.
    """

    cursor = await collection.aggregate(pipeline)
    return await cursor.to_list(length=length)
