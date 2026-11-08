from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserPublic(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: Literal["reader", "admin"] | str = "reader"
    status: Literal["active", "disabled"] | str = "active"
    avatar_url: str | None = None
    bio: str | None = None
    created_at: datetime | None = None
    last_login_at: datetime | None = None


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)
    bio: str | None = Field(default=None, max_length=500)


class AdminUserUpdate(BaseModel):
    role: Literal["reader", "admin"] | None = None
    status: Literal["active", "disabled"] | None = None
