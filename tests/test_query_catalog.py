from __future__ import annotations

from app.services.query_catalog import QUERY_CATALOG


def test_catalog_has_exactly_ten_queries() -> None:
    assert len(QUERY_CATALOG) == 10


def test_catalog_numbers_are_sequential() -> None:
    assert [item["number"] for item in QUERY_CATALOG] == list(range(1, 11))


def test_catalog_entries_are_complete() -> None:
    for item in QUERY_CATALOG:
        assert item["name"]
        assert item["description"]
        assert item["endpoint"].startswith("/api/v1/")
        assert item["method"] in {"GET", "POST", "PATCH", "DELETE"}
        assert len(item["operators"]) >= 2
        assert item["index"]


def test_catalog_endpoints_are_unique() -> None:
    endpoints = [item["endpoint"] for item in QUERY_CATALOG]
    assert len(endpoints) == len(set(endpoints))


def test_catalog_covers_key_mongodb_operators() -> None:
    operators = " ".join(" ".join(item["operators"]) for item in QUERY_CATALOG)
    for expected in ("$text", "$facet", "$group", "$lookup", "$unwind", "$setIntersection"):
        assert expected in operators
