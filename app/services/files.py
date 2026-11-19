from __future__ import annotations

import io
import zipfile
from typing import Any

from bson import ObjectId
from gridfs import AsyncGridFSBucket
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import settings
from app.core.exceptions import AppError
from app.repositories.contents import ContentRepository
from app.schemas.content import FileType
from app.utils.serializers import to_object_id

EPUB_MIMETYPE = b"application/epub+zip"
FILE_CONTENT_TYPES: dict[FileType, str] = {
    "pdf": "application/pdf",
    "epub": "application/epub+zip",
}
FILE_EXTENSIONS: dict[FileType, str] = {"pdf": ".pdf", "epub": ".epub"}
FILE_LABELS: dict[FileType, str] = {"pdf": "PDF", "epub": "EPUB"}
FILE_SIZE_LIMITS: dict[FileType, int] = {
    "pdf": settings.max_pdf_mb,
    "epub": settings.max_epub_mb,
}


def detect_file_type(filename: str) -> FileType:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "pdf"
    if lower.endswith(".epub"):
        return "epub"
    raise AppError(
        400,
        "INVALID_FILE_TYPE",
        "Solo se permiten archivos PDF o EPUB",
    )


def validate_pdf(data: bytes) -> None:
    if not data.startswith(b"%PDF-"):
        raise AppError(400, "INVALID_PDF", "El archivo no parece ser un PDF válido")


def validate_epub(data: bytes) -> None:
    if not data.startswith(b"PK\x03\x04"):
        raise AppError(400, "INVALID_EPUB", "El archivo no parece ser un EPUB válido")

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            if "mimetype" not in names:
                raise AppError(
                    400,
                    "INVALID_EPUB",
                    "El EPUB no contiene el archivo mimetype requerido",
                )
            if archive.read("mimetype").strip() != EPUB_MIMETYPE:
                raise AppError(
                    400,
                    "INVALID_EPUB",
                    "El archivo no declara el tipo application/epub+zip",
                )
            if "META-INF/container.xml" not in names:
                raise AppError(
                    400,
                    "INVALID_EPUB",
                    "El EPUB no contiene META-INF/container.xml",
                )
    except zipfile.BadZipFile as exc:
        raise AppError(
            400,
            "INVALID_EPUB",
            "El archivo no parece ser un EPUB válido",
        ) from exc


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
        content_type: str | None,  # noqa: ARG002
        data: bytes,
    ) -> ObjectId:
        content = await self.contents.find_by_id(content_id)
        if content is None:
            raise AppError(404, "CONTENT_NOT_FOUND", "El contenido no existe")

        file_type = detect_file_type(filename)
        if file_type == "pdf":
            validate_pdf(data)
        else:
            validate_epub(data)

        max_mb = FILE_SIZE_LIMITS[file_type]
        if len(data) > max_mb * 1024 * 1024:
            raise AppError(
                413,
                "FILE_TOO_LARGE",
                f"El {FILE_LABELS[file_type]} supera el límite de {max_mb} MB",
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
                "file_type": file_type,
                "content_type": FILE_CONTENT_TYPES[file_type],
                "size": len(data),
            },
        )
        await self.contents.update(
            content_id,
            {"file_id": file_id, "file_type": file_type},
        )
        return file_id

    async def get_download(self, content_id: str) -> tuple[Any, str, str]:
        content = await self.contents.find_by_id(content_id)
        if content is None or not content.get("file_id"):
            raise AppError(404, "FILE_NOT_FOUND", "Este contenido no tiene un archivo asociado")

        file_document = await self.db["pdfs.files"].find_one({"_id": content["file_id"]})
        stream = await self.bucket.open_download_stream(content["file_id"])
        file_type = self._resolve_file_type(content, file_document)
        default_name = f"documento{FILE_EXTENSIONS[file_type]}"
        filename = (
            file_document.get("filename", default_name)
            if file_document
            else default_name
        )
        content_type = self._resolve_content_type(file_document, file_type)
        return stream, filename, content_type

    async def get_metadata(self, content_id: str) -> dict[str, Any]:
        content = await self.contents.find_by_id(content_id)
        if content is None or not content.get("file_id"):
            raise AppError(404, "FILE_NOT_FOUND", "Este contenido no tiene un archivo asociado")

        file_document = await self.db["pdfs.files"].find_one({"_id": content["file_id"]})
        if file_document is None:
            raise AppError(404, "FILE_NOT_FOUND", "El archivo no existe en GridFS")

        file_type = self._resolve_file_type(content, file_document)
        return {
            "id": str(file_document["_id"]),
            "filename": file_document.get(
                "filename",
                f"documento{FILE_EXTENSIONS[file_type]}",
            ),
            "content_type": self._resolve_content_type(file_document, file_type),
            "file_type": file_type,
            "size": file_document.get("length", 0),
            "upload_date": file_document.get("uploadDate"),
        }

    async def delete(self, content_id: str) -> FileType:
        content = await self.contents.find_by_id(content_id)
        if content is None or not content.get("file_id"):
            raise AppError(404, "FILE_NOT_FOUND", "Este contenido no tiene un archivo asociado")

        file_type = self._resolve_file_type(content, None)
        await self.bucket.delete(content["file_id"])
        await self.contents.update(content_id, {"file_id": None, "file_type": None})
        return file_type

    @staticmethod
    def _resolve_file_type(
        content: dict[str, Any],
        file_document: dict[str, Any] | None,
    ) -> FileType:
        file_type = content.get("file_type")
        if file_type in FILE_CONTENT_TYPES:
            return file_type  # type: ignore[return-value]

        metadata = (file_document or {}).get("metadata") or {}
        metadata_type = metadata.get("file_type")
        if metadata_type in FILE_CONTENT_TYPES:
            return metadata_type  # type: ignore[return-value]

        filename = (file_document or {}).get("filename", "")
        if str(filename).lower().endswith(".epub"):
            return "epub"
        return "pdf"

    @staticmethod
    def _resolve_content_type(
        file_document: dict[str, Any] | None,
        file_type: FileType,
    ) -> str:
        document = file_document or {}
        metadata = document.get("metadata") or {}
        stored = document.get("content_type") or metadata.get("content_type")
        if stored:
            return stored
        return FILE_CONTENT_TYPES[file_type]
