from __future__ import annotations

import math


def page_meta(*, page: int, limit: int, total: int) -> dict[str, int]:
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": math.ceil(total / limit) if limit > 0 else 0,
    }
