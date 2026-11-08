from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import settings


class Database:
    """Contenedor del cliente y la base de datos async de MongoDB."""

    client: AsyncMongoClient | None = None
    db: AsyncDatabase | None = None

    async def connect(self) -> None:
        self.client = AsyncMongoClient(
            settings.mongo_uri,
            serverSelectionTimeoutMS=8000,
            tz_aware=True,
        )
        await self.client.admin.command("ping")
        self.db = self.client[settings.mongo_db]

    async def disconnect(self) -> None:
        if self.client is not None:
            await self.client.close()
        self.client = None
        self.db = None


database = Database()


def get_db() -> AsyncDatabase:
    if database.db is None:
        raise RuntimeError("La base de datos no está inicializada")
    return database.db
