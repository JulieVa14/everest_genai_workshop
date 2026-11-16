import asyncio
import hashlib
import io
import json
import re
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import AsyncOpenAI
from pypdf import PdfReader

from .config import ROOT, Settings
from .errors import WorkshopError, provider_error
from .schemas import Course, ErrorCode, Evidence, Lecture

COURSES = [
    Course(id="generative-ai", name="Generative AI"),
    Course(id="study-notes", name="Study Notes"),
]
DEFAULT_LECTURES = [
    ("introduction", "Introduction", "00-Intro.pdf"),
    ("llms", "Large Language Models", "01-LLMs.pdf"),
    ("applications-tools", "Applications and Tools", "02-LLMS_Applications_and_Tools.pdf"),
    ("image-generation", "Image Generation", "03-Image_Generation.pdf"),
    ("audio-generation", "Audio Generation", "04-Audio_Generation.pdf"),
    ("ethics", "Generative AI Ethics", "05-GAI_ethics.pdf"),
]


def validate_id(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", value):
        raise WorkshopError(ErrorCode.INVALID_INPUT, "Invalid course or lecture identifier.")
    return value


def validate_course(course_id: str) -> str:
    validate_id(course_id)
    if course_id not in {course.id for course in COURSES}:
        raise WorkshopError(ErrorCode.NOT_FOUND, "Course not found.", 404)
    return course_id


def scope_filter(course_id: str, lecture_id: str | None = None) -> dict:
    validate_course(course_id)
    if lecture_id is None:
        return {"course_id": course_id}
    return {"$and": [{"course_id": course_id}, {"lecture_id": validate_id(lecture_id)}]}


def extract_chunks(filename: str, data: bytes, max_bytes: int = 10 * 1024 * 1024):
    if len(data) > max_bytes:
        raise WorkshopError(ErrorCode.FILE_TOO_LARGE, "Files must be at most 10 MB.", 413)
    if not data:
        raise WorkshopError(ErrorCode.INVALID_INPUT, "The uploaded file is empty.")
    if not filename or re.search(r"[\\/\x00-\x1f\x7f]", filename) or len(filename) > 160:
        raise WorkshopError(ErrorCode.INVALID_INPUT, "Use a plain filename without paths.")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".txt"}:
        raise WorkshopError(ErrorCode.UNSUPPORTED_FILE, "Upload a PDF or UTF-8 .txt file.", 415)
    try:
        if suffix == ".pdf":
            if not data.startswith(b"%PDF-"):
                raise ValueError("Not PDF")
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ValueError("Encrypted PDF")
            if len(reader.pages) > 512:
                raise ValueError("Too many pages")
            pages = [
                (index + 1, page.extract_text() or "") for index, page in enumerate(reader.pages)
            ]
        else:
            text = data.decode("utf-8-sig")
            if "\x00" in text:
                raise ValueError("Binary text")
            pages = [(1, text)]
    except Exception:
        raise WorkshopError(
            ErrorCode.INVALID_INPUT,
            "Unable to extract this file. Use an unencrypted, text-based PDF or UTF-8 text; "
            "scanned PDFs need extraction outside this workshop.",
        ) from None
    chunks = []
    for page, text in pages:
        text = " ".join(text.split())
        for offset in range(0, len(text), 1000):
            piece = text[offset : offset + 1200]
            if piece.strip():
                chunks.append((page, offset, piece))
    if not chunks:
        raise WorkshopError(
            ErrorCode.INVALID_INPUT,
            "No readable text found. Use a text-based PDF or UTF-8 text; OCR is not supplied.",
        )
    if len(chunks) > 2000:
        raise WorkshopError(
            ErrorCode.INVALID_INPUT, "Use a smaller document (at most 2000 chunks)."
        )
    return chunks


class DocumentStore:
    def __init__(self, settings: Settings, client: AsyncOpenAI | None = None):
        self.settings = settings
        self.client = client
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.catalog_path = settings.data_dir / "catalog.json"
        self._collection = None
        self._chroma = None
        self.write_lock = asyncio.Lock()
        self.lectures: dict[str, Lecture] = {}
        self.paths: dict[str, Path] = {}
        for lecture_id, title, filename in DEFAULT_LECTURES:
            source_id = self.source_id("generative-ai", lecture_id)
            lecture = Lecture(
                id=lecture_id,
                course_id="generative-ai",
                title=title,
                filename=filename,
                source_id=source_id,
            )
            self.lectures[self.key("generative-ai", lecture_id)] = lecture
            self.paths[source_id] = ROOT / "docs" / filename
        if self.catalog_path.exists():
            for record in json.loads(self.catalog_path.read_text(encoding="utf-8")):
                lecture = Lecture.model_validate(record)
                self.lectures[self.key(lecture.course_id, lecture.id)] = lecture
                self.paths[lecture.source_id] = (
                    settings.data_dir
                    / "uploads"
                    / f"{lecture.source_id}{Path(lecture.filename).suffix.lower()}"
                )

    @staticmethod
    def key(course_id: str, lecture_id: str) -> str:
        return f"{course_id}:{lecture_id}"

    @staticmethod
    def source_id(course_id: str, lecture_id: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"course-companion/{course_id}/{lecture_id}"))

    def validate_scope(self, course_id: str, lecture_id: str | None = None):
        validate_course(course_id)
        if lecture_id is not None:
            validate_id(lecture_id)
            if self.key(course_id, lecture_id) not in self.lectures:
                raise WorkshopError(ErrorCode.NOT_FOUND, "Lecture not found in this course.", 404)

    def list_lectures(self, course_id: str) -> list[Lecture]:
        self.validate_scope(course_id)
        return [item for item in self.lectures.values() if item.course_id == course_id]

    @property
    def collection(self):
        if self._collection is None:
            self._chroma = chromadb.PersistentClient(
                path=str(self.settings.data_dir / "chroma"),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            collection = self._chroma.get_or_create_collection(
                "course_documents",
                embedding_function=None,
                metadata={"embedding_model": self.settings.embedding_model},
            )
            if collection.metadata.get("embedding_model") != self.settings.embedding_model:
                raise WorkshopError(
                    ErrorCode.INVALID_INPUT,
                    "Embedding model differs from this index. Use the original model or a fresh "
                    "generated data directory and re-index documents.",
                )
            self._collection = collection
        return self._collection

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if self.client is None:
            raise provider_error()
        vectors = []
        try:
            async with asyncio.timeout(self.settings.timeout_seconds):
                for offset in range(0, len(texts), 64):
                    response = await self.client.embeddings.create(
                        model=self.settings.embedding_model,
                        input=texts[offset : offset + 64],
                    )
                    batch = sorted(response.data, key=lambda item: item.index)
                    if len(batch) != len(texts[offset : offset + 64]):
                        raise ValueError("Embedding count mismatch")
                    vectors.extend(item.embedding for item in batch)
        except Exception:
            raise provider_error() from None
        return vectors

    async def index_document(
        self,
        course_id: str,
        lecture_id: str | None,
        filename: str,
        data: bytes,
        title: str | None = None,
    ) -> Lecture:
        validate_course(course_id)
        lecture_id = validate_id(lecture_id) if lecture_id else str(uuid4())
        if title is not None and (not title.strip() or len(title) > 160):
            raise WorkshopError(ErrorCode.INVALID_INPUT, "Title must contain 1-160 characters.")
        chunks = await asyncio.to_thread(
            extract_chunks,
            filename,
            data,
            self.settings.max_upload_bytes,
        )
        async with self.write_lock:
            existing = self.lectures.get(self.key(course_id, lecture_id))
            existing_path = self.paths.get(self.source_id(course_id, lecture_id))
            if (
                existing is not None
                and existing.state == "ready"
                and existing.filename == filename
                and existing.title == (title or filename)
                and existing_path is not None
                and existing_path.is_file()
                and existing_path.read_bytes() == data
            ):
                return existing
            vectors = await self.embed([chunk[2] for chunk in chunks])
            source_id = self.source_id(course_id, lecture_id)
            ids = [
                hashlib.sha256(
                    f"{course_id}:{lecture_id}:{page}:{offset}:{text}".encode()
                ).hexdigest()
                for page, offset, text in chunks
            ]
            metadata = [
                {
                    "course_id": course_id,
                    "lecture_id": lecture_id,
                    "filename": filename,
                    "page": page,
                    "source_id": source_id,
                }
                for page, _, _ in chunks
            ]
            where = scope_filter(course_id, lecture_id)
            collection = self.collection
            old_ids = collection.get(where=where, include=[])["ids"]
            for offset in range(0, len(ids), 64):
                collection.upsert(
                    ids=ids[offset : offset + 64],
                    documents=[chunk[2] for chunk in chunks[offset : offset + 64]],
                    embeddings=vectors[offset : offset + 64],
                    metadatas=metadata[offset : offset + 64],
                )
            stale = sorted(set(old_ids) - set(ids))
            if stale:
                collection.delete(ids=stale)
            upload_dir = self.settings.data_dir / "uploads"
            upload_dir.mkdir(exist_ok=True)
            path = upload_dir / f"{source_id}{Path(filename).suffix.lower()}"
            path.write_bytes(data)
            old_path = self.paths.get(source_id)
            if old_path and old_path.parent == upload_dir and old_path != path:
                old_path.unlink(missing_ok=True)
            lecture = Lecture(
                id=lecture_id,
                course_id=course_id,
                title=title or filename,
                filename=filename,
                source_id=source_id,
                state="ready",
            )
            self.lectures[self.key(course_id, lecture_id)] = lecture
            self.paths[source_id] = path
            uploaded = [
                item.model_dump()
                for item in self.lectures.values()
                if self.paths[item.source_id].parent == upload_dir
            ]
            temporary = self.catalog_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(uploaded), encoding="utf-8")
            temporary.replace(self.catalog_path)
            return lecture

    def query_vectors(
        self,
        vector: list[float],
        course_id: str,
        lecture_id: str | None = None,
    ) -> list[Evidence]:
        self.validate_scope(course_id, lecture_id)
        collection = self.collection
        count = collection.count()
        if not count:
            return []
        result = collection.query(
            query_embeddings=[vector],
            where=scope_filter(course_id, lecture_id),
            n_results=min(self.settings.retrieval_count, count),
            include=["documents", "metadatas"],
        )
        return [
            Evidence(
                chunk_id=chunk_id,
                text=text,
                lecture_id=metadata["lecture_id"],
                filename=metadata["filename"],
                page=metadata["page"],
                source_id=metadata["source_id"],
            )
            for chunk_id, text, metadata in zip(
                result["ids"][0],
                result["documents"][0],
                result["metadatas"][0],
                strict=True,
            )
        ]

    def validate_evidence(
        self,
        evidence: list[Evidence],
        course_id: str,
        lecture_id: str | None,
    ):
        self.validate_scope(course_id, lecture_id)
        if not evidence:
            return
        if len(evidence) > self.settings.retrieval_count:
            raise provider_error()
        result = self.collection.get(
            ids=list(dict.fromkeys(item.chunk_id for item in evidence)),
            where=scope_filter(course_id, lecture_id),
            include=["documents", "metadatas"],
        )
        stored = {
            chunk_id: Evidence(
                chunk_id=chunk_id,
                text=text,
                lecture_id=metadata["lecture_id"],
                filename=metadata["filename"],
                page=metadata["page"],
                source_id=metadata["source_id"],
            )
            for chunk_id, text, metadata in zip(
                result["ids"],
                result["documents"],
                result["metadatas"],
                strict=True,
            )
        }
        if any(stored.get(item.chunk_id) != item for item in evidence):
            raise provider_error()

    def source(self, source_id: str) -> Path:
        path = self.paths.get(source_id)
        if path is None or not path.is_file():
            raise WorkshopError(ErrorCode.NOT_FOUND, "Source not found.", 404)
        return path
