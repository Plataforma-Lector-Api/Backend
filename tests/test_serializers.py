from __future__ import annotations

from datetime import UTC, datetime

import pytest
from bson import ObjectId

from app.core.exceptions import AppError
from app.utils.serializers import serialize_doc, serialize_docs, serialize_value, to_object_id


def test_to_object_id_accepts_string_and_object_id() -> None:
    object_id = ObjectId()
    assert to_object_id(str(object_id)) == object_id
    assert to_object_id(object_id) == object_id


def test_to_object_id_rejects_invalid_value() -> None:
    with pytest.raises(AppError) as error:
        to_object_id("no-es-un-object-id")
    assert error.value.status_code == 400
    assert error.value.code == "INVALID_ID"


def test_serialize_value_handles_object_id_and_datetime() -> None:
    moment = datetime(2024, 5, 17, 12, 30, tzinfo=UTC)
    object_id = ObjectId()
    assert serialize_value(object_id) == str(object_id)
    assert serialize_value(moment) == moment.isoformat()


def test_serialize_doc_renames_id_and_nested_values() -> None:
    document = {
        "_id": ObjectId(),
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "tags": ["uno", "dos"],
        "nested": {"_id": ObjectId(), "value": 1},
    }
    result = serialize_doc(document)
    assert result is not None
    assert "id" in result and "_id" not in result
    assert isinstance(result["id"], str)
    assert result["nested"]["id"] == str(document["nested"]["_id"])


def test_serialize_docs_and_none() -> None:
    assert serialize_doc(None) is None
    assert serialize_docs([]) == []
    assert len(serialize_docs([{"_id": ObjectId()}, {"_id": ObjectId()}])) == 2
