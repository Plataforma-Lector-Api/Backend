from __future__ import annotations

from typing import Any

from bson import ObjectId
from gridfs import AsyncGridFSBucket
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import settings
from app.core.exceptions import AppError
from app.repositories.contents import ContentRepository
from app.utils.serializers import to_object_id


class FileService:
    def __init__(self, db: AsyncDatabase) -> None:
        self.db = db
        self.bucket = AsyncGridFSBucket(db, bucket_name="pdfs")
        self.contents = ContentRepository(db)

    async def upload(
        self,
        *,
        user_id: str,
        content_id: str,
        filename: str,
        content_type: str | None,
        data: bytes,
    ) -> ObjectId:
        content = await self.contents.find_by_id(content_id)
        if content is None:
            raise AppError(404, "CONTENT_NOT_FOUND", "El contenido no existe")
        if not filename.lower().endswith(".pdf"):
            raise AppError(400, "INVALID_FILE_TYPE", "Solo se permiten archivos PDF")
        if not data.startswith(b"%PDF-"):
            raise AppError(400, "INVALID_PDF", "El archivo no parece ser un PDF válido")

        max_bytes = settings.max_pdf_mb * 1024 * 1024
        if len(data) > max_bytes:
            raise AppError(
                413,
                "FILE_TOO_LARGE",
                f"El PDF supera el límite de {settings.max_pdf_mb} MB",
            )

        if content.get("file_id"):
            try:
                await self.bucket.delete(content["file_id"])
            except Exception:
                pass

        file_id = await self.bucket.upload_from_stream(
            filename,
            data,
            metadata={
                "content_id": to_object_id(content_id),
                "uploaded_by": to_object_id(user_id),
                "content_type": content_type or "application/pdf",
                "size": len(data),
            },
        )
        await self.contents.update(content_id, {"file_id": file_id})
        return file_id

    async def get_download(self, content_id: str) -> tuple[Any, str, str]:
        content = await self.contents.find_by_id(content_id)
        if content is None or not content.get("file_id"):
            raise AppError(404, "FILE_NOT_FOUND", "Este contenido no tiene un PDF asociado")

        file_document = await self.db["pdfs.files"].find_one({"_id": content["file_id"]})
        stream = await self.bucket.open_download_stream(content["file_id"])
        filename = (
            file_document.get("filename", "documento.pdf") if file_document else "documento.pdf"
        )
        content_type = (
            file_document.get("content_type", "application/pdf")
            if file_document
            else "application/pdf"
        )
        return stream, filename, content_type

    async def get_metadata(self, content_id: str) -> dict[str, Any]:
        content = await self.contents.find_by_id(content_id)
        if content is None or not content.get("file_id"):
            raise AppError(404, "FILE_NOT_FOUND", "Este contenido no tiene un PDF asociado")

        file_document = await self.db["pdfs.files"].find_one({"_id": content["file_id"]})
        if file_document is None:
            raise AppError(404, "FILE_NOT_FOUND", "El archivo no existe en GridFS")

        return {
            "id": str(file_document["_id"]),
            "filename": file_document.get("filename", "documento.pdf"),
            "content_type": file_document.get("content_type", "application/pdf"),
            "size": file_document.get("length", 0),
            "upload_date": file_document.get("uploadDate"),
        }

    async def delete(self, content_id: str) -> None:
        content = await self.contents.find_by_id(content_id)
        if content is None or not content.get("file_id"):
            raise AppError(404, "FILE_NOT_FOUND", "Este contenido no tiene un PDF asociado")

        await self.bucket.delete(content["file_id"])
        await self.contents.update(content_id, {"file_id": None})
