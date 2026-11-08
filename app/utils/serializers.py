from __future__ import annotations

from datetime import date, datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from app.core.exceptions import AppError


def to_object_id(value: str | ObjectId) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise AppError(400, "INVALID_ID", "El identificador enviado no es válido") from exc


def serialize_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {
            ("id" if key == "_id" else key): serialize_value(item) for key, item in value.items()
        }
    return value


def serialize_doc(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    return serialize_value(document)


def serialize_docs(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [serialize_value(document) for document in documents]
