from __future__ import annotations

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    password_hash = hash_password("Secreto123!")  # noqa: S105
    assert password_hash != "Secreto123!"
    assert verify_password("Secreto123!", password_hash)
    assert not verify_password("otra-clave", password_hash)


def test_access_token_payload() -> None:
    token = create_access_token("507f1f77bcf86cd799439011", "reader")
    payload = decode_token(token)
    assert payload["sub"] == "507f1f77bcf86cd799439011"
    assert payload["role"] == "reader"
    assert payload["type"] == "access"
    assert payload["jti"]


def test_refresh_token_payload() -> None:
    token = create_refresh_token("507f1f77bcf86cd799439011", "admin")
    payload = decode_token(token)
    assert payload["type"] == "refresh"
    assert payload["role"] == "admin"


def test_tokens_are_unique() -> None:
    first = create_access_token("507f1f77bcf86cd799439011", "reader")
    second = create_access_token("507f1f77bcf86cd799439011", "reader")
    assert first != second


def test_hash_token_is_deterministic() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")


def test_decode_invalid_token() -> None:
    import jwt

    with pytest.raises(jwt.PyJWTError):
        decode_token("no-es-un-token")
