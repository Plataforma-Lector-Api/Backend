from __future__ import annotations

from pymongo.asynchronous.database import AsyncDatabase


async def ensure_indexes(db: AsyncDatabase) -> None:
    """Crea los índices que soportan las 10 consultas. Es idempotente."""

    await db.users.create_index("email", unique=True, name="users_email_unique")
    await db.users.create_index([("role", 1), ("status", 1)], name="users_role_status")

    await db.contents.create_index(
        [
            ("title", "text"),
            ("author", "text"),
            ("description", "text"),
            ("tags", "text"),
        ],
        weights={"title": 10, "author": 5, "tags": 3, "description": 1},
        name="contents_text_index",
    )
    await db.contents.create_index("tags", name="contents_tags")
    await db.contents.create_index([("popularity", -1)], name="contents_popularity")
    await db.contents.create_index(
        [("type", 1), ("published_at", -1)],
        name="contents_type_published",
    )
    await db.contents.create_index("author", name="contents_author")
    await db.contents.create_index(
        [("rating_avg", -1), ("rating_count", -1)],
        name="contents_rating",
    )
    await db.contents.create_index(
        [("status", 1), ("created_at", -1)],
        name="contents_status_created",
    )

    await db.collections.create_index(
        [("user_id", 1), ("content_id", 1)],
        unique=True,
        name="collections_user_content_unique",
    )
    await db.collections.create_index(
        [("user_id", 1), ("added_at", -1)],
        name="collections_user_added",
    )
    await db.collections.create_index("content_id", name="collections_content")

    await db.reviews.create_index(
        [("user_id", 1), ("content_id", 1)],
        unique=True,
        name="reviews_user_content_unique",
    )
    await db.reviews.create_index(
        [("content_id", 1), ("rating", -1)],
        name="reviews_content_rating",
    )
    await db.reviews.create_index([("created_at", -1)], name="reviews_created")

    await db.reading_progress.create_index(
        [("user_id", 1), ("content_id", 1)],
        unique=True,
        name="progress_user_content_unique",
    )
    await db.reading_progress.create_index(
        [("user_id", 1), ("updated_at", -1)],
        name="progress_user_updated",
    )

    await db.refresh_tokens.create_index(
        "token_hash",
        unique=True,
        name="refresh_token_hash_unique",
    )
    await db.refresh_tokens.create_index(
        "expires_at",
        expireAfterSeconds=0,
        name="refresh_token_ttl",
    )
    await db.refresh_tokens.create_index("user_id", name="refresh_token_user")

    await db["pdfs.files"].create_index(
        "metadata.content_id",
        name="pdfs_content_id",
    )
