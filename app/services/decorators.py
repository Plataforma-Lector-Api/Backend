from __future__ import annotations

from typing import Any

from app.repositories.collections import CollectionRepository
from app.utils.serializers import serialize_doc


async def decorate_content(
    document: dict[str, Any] | None,
    collections: CollectionRepository,
    user_id: str | None,
) -> dict[str, Any] | None:
    if document is None:
        return None
    item = serialize_doc(document)
    item["has_file"] = item.get("file_id") is not None
    item["is_saved"] = (
        await collections.exists(user_id, item["id"]) if user_id is not None else False
    )
    return item


async def decorate_many(
    documents: list[dict[str, Any]],
    collections: CollectionRepository,
    user_id: str | None,
) -> list[dict[str, Any]]:
    saved_ids = await collections.saved_ids(user_id) if user_id is not None else set()
    result: list[dict[str, Any]] = []
    for document in documents:
        item = serialize_doc(document)
        item["has_file"] = item.get("file_id") is not None
        item["is_saved"] = item["id"] in saved_ids
        result.append(item)
    return result
