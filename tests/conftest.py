from __future__ import annotations

import os

# Debe ejecutarse antes de importar la app: usa una base de datos aislada.
os.environ["MONGO_DB"] = "lector_plus_test"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["JWT_SECRET"] = "test-secret-only-for-pytest-0123456789abcdef"  # noqa: S105
