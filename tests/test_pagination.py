from __future__ import annotations

from app.utils.pagination import page_meta


def test_page_meta_rounds_up() -> None:
    assert page_meta(page=1, limit=12, total=25) == {
        "page": 1,
        "limit": 12,
        "total": 25,
        "total_pages": 3,
    }


def test_page_meta_exact_division() -> None:
    assert page_meta(page=2, limit=10, total=20)["total_pages"] == 2


def test_page_meta_empty_result() -> None:
    assert page_meta(page=1, limit=10, total=0)["total_pages"] == 0
