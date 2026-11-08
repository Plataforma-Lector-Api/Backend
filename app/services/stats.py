from __future__ import annotations

import asyncio
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from app.repositories.collections import CollectionRepository
from app.repositories.contents import ContentRepository
from app.repositories.reviews import ReviewRepository
from app.repositories.users import UserRepository
from app.utils.serializers import serialize_value


class StatsService:
    def __init__(self, db: AsyncDatabase) -> None:
        self.users = UserRepository(db)
        self.contents = ContentRepository(db)
        self.collections = CollectionRepository(db)
        self.reviews = ReviewRepository(db)

    async def dashboard(self) -> dict[str, Any]:
        (
            users_count,
            contents_count,
            collections_count,
            reviews_count,
            average_rating,
            users_per_month,
            contents_per_type,
            top_tags,
            top_contents,
            recent_reviews,
        ) = await asyncio.gather(
            self.users.count(),
            self.contents.count(),
            self.collections.count(),
            self.reviews.count(),
            self.reviews.average_rating(),
            self.users.count_by_month(),
            self.contents.contents_per_type(),
            self.contents.tag_stats(5),
            self.collections.most_saved(5),
            self.reviews.recent(5),
        )

        return serialize_value(
            {
                "totals": {
                    "users": users_count,
                    "contents": contents_count,
                    "collections": collections_count,
                    "reviews": reviews_count,
                },
                "average_rating": average_rating,
                "users_per_month": users_per_month,
                "contents_per_type": contents_per_type,
                "top_tags": top_tags,
                "top_contents": top_contents,
                "recent_reviews": recent_reviews,
            }
        )
