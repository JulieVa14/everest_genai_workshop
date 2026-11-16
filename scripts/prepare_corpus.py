"""Build/export/import a public Intro + Ethics index, never conversation histories.

Run with backend/.venv Python. Build alone calls OpenAI (and incurs embedding cost).
Export/import use a logical Chroma snapshot, not raw SQLite/HNSW files. Stop writers.
Targets are always this checkout's .workshop-data/<surface>/<mode>.
"""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.reset_data import data_target, reject_links  # noqa: E402

FORMAT = "course-companion-corpus-v1"
CHUNKING = {"page_based": True, "stride_characters": 1000, "chunk_characters": 1200}
DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}
SOURCES = (
    ("introduction", "Introduction", "00-Intro.pdf"),
    ("ethics", "Generative AI Ethics", "05-GAI_ethics.pdf"),
)


def infrastructure():
    from backend.app.config import load_settings
    from backend.app.retrieval import DocumentStore, extract_chunks

    return load_settings, DocumentStore, extract_chunks


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode()


def empty_target(target: Path) -> None:
    reject_links(target)
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ValueError("Destination must be absent or empty; stop writers and reset explicitly")


def source_contract(root: Path) -> tuple[list[dict], dict[str, tuple[str, dict]], dict[str, bytes]]:
    _, store_type, extract_chunks = infrastructure()
    sources, expected, uploads = [], {}, {}
    for lecture_id, title, filename in SOURCES:
        path = root / "docs" / filename
        reject_links(path)
        data = path.read_bytes()
        chunks = extract_chunks(filename, data)
        source_id = store_type.source_id("generative-ai", lecture_id)
        upload = f"uploads/{source_id}.pdf"
        uploads[upload] = data
        sources.append({
            "lecture_id": lecture_id, "title": title, "filename": filename,
            "source_id": source_id, "sha256": digest(data), "upload": upload,
            "selected_pages": sorted({page for page, _, _ in chunks}),
            "selection": "all readable pages of the full original PDF",
        })
        for page, offset, text in chunks:
            chunk_id = digest(f"generative-ai:{lecture_id}:{page}:{offset}:{text}".encode())
            expected[chunk_id] = (text, {
                "course_id": "generative-ai", "lecture_id": lecture_id,
                "filename": filename, "page": page, "source_id": source_id,
            })
    return sources, expected, uploads


def validate_payload(root: Path, manifest: dict, files: dict[str, bytes], model: str):
    if manifest.get("format") != FORMAT:
        raise ValueError("Unsupported corpus format")
    version = importlib.metadata.version("chromadb")
    if manifest.get("chroma_version") != version:
        raise ValueError("Chroma version mismatch; install the locked backend dependencies")
    if model not in DIMENSIONS or manifest.get("embedding_model") != model:
        raise ValueError("Embedding model mismatch or unsupported model; never silently re-embed")
    if manifest.get("dimension") != DIMENSIONS[model] or manifest.get("chunking") != CHUNKING:
        raise ValueError("Embedding dimension or chunk settings mismatch")
    sources, expected, uploads = source_contract(root)
    if manifest.get("sources") != sources:
        raise ValueError("Original PDF hashes/pages/provenance differ from this checkout")
    required = {"catalog.json", "vectors.json", *uploads}
    if set(files) != required or set(manifest.get("files", {})) != required:
        raise ValueError("Bundle must contain ONLY catalog, vectors and approved PDF uploads")
    if any(manifest["files"][name] != digest(data) for name, data in files.items()):
        raise ValueError("Corpus file hash mismatch")
    if any(files[name] != data for name, data in uploads.items()):
        raise ValueError("Uploaded PDFs are not the approved originals")
    catalog = json.loads(files["catalog.json"])
    expected_catalog = [{
        "id": item["lecture_id"], "course_id": "generative-ai", "title": item["title"],
        "filename": item["filename"], "source_id": item["source_id"], "state": "ready",
        "error": None,
    } for item in sources]
    if catalog != expected_catalog:
        raise ValueError("Catalog contains unknown or modified lectures")
    records = json.loads(files["vectors.json"])
    if not isinstance(records, list) or len(records) != len(expected):
        raise ValueError("Corpus record count mismatch")
    seen = set()
    for record in records:
        if set(record) != {"id", "document", "metadata", "embedding"}:
            raise ValueError("Unexpected vector record fields")
        chunk_id = record["id"]
        if chunk_id in seen or expected.get(chunk_id) != (record["document"], record["metadata"]):
            raise ValueError("Chunk IDs/text/page metadata do not match the original corpus")
        seen.add(chunk_id)
        vector = record["embedding"]
        if (not isinstance(vector, list) or len(vector) != DIMENSIONS[model]
                or any(type(value) not in {int, float} or not math.isfinite(value)
                       for value in vector) or not any(vector)):
            raise ValueError("Invalid or incompatible embedding vector")
    if manifest.get("record_count") != len(records):
        raise ValueError("Manifest record count mismatch")
    return records


def read_bundle(bundle: Path) -> tuple[dict, dict[str, bytes]]:
    reject_links(bundle)
    manifest_path = bundle / "manifest.json"
    reject_links(manifest_path)
    manifest = json.loads(manifest_path.read_bytes())
    names = manifest.get("files", {})
    allowed_uploads = {
        f"uploads/{infrastructure()[1].source_id('generative-ai', lecture_id)}.pdf"
        for lecture_id, _, _ in SOURCES
    }
    expected_names = {"catalog.json", "vectors.json", *allowed_uploads}
    if not isinstance(names, dict) or set(names) != expected_names:
        raise ValueError("Unsafe or unexpected corpus filenames")
    actual = set()
    for path in bundle.rglob("*"):
        reject_links(path)
        if path.is_file():
            actual.add(path.relative_to(bundle).as_posix())
    if actual != {"manifest.json", *names}:
        raise ValueError("Unexpected bundle files (histories/keys are never imported)")
    return manifest, {name: (bundle / name).read_bytes() for name in names}


async def build(root: Path, surface: str, mode: str) -> Path:
    load_settings, store_type, _ = infrastructure()
    settings = load_settings()
    if not settings.api_key:
        raise ValueError("Build requires an individual OPENAI_API_KEY in backend/.env")
    if settings.embedding_model not in DIMENSIONS:
        raise ValueError("Unsupported embedding model; explicit model dimension is required")
    target = data_target(root, surface, mode)
    empty_target(target)
    source_contract(root)
    from backend.app.tutor import openai_client

    client = openai_client(settings)
    try:
        store = store_type(replace(settings, mode=mode, data_dir=target), client)
        for lecture_id, title, filename in SOURCES:
            await store.index_document("generative-ai", lecture_id, filename,
                                       (root / "docs" / filename).read_bytes(), title)
    finally:
        await client.close()
    print("Built full Intro + Ethics PDFs using live OpenAI embeddings; no sessions created.")
    return target


def export(root: Path, surface: str, mode: str, output: Path) -> None:
    load_settings, store_type, _ = infrastructure()
    target = data_target(root, surface, mode)
    reject_links(target / "catalog.json")
    reject_links(target / "chroma")
    for path in (target / "chroma").rglob("*"):
        reject_links(path)
    if not (target / "catalog.json").is_file() or not (target / "chroma").is_dir():
        raise ValueError("No indexed corpus found; run build first")
    reject_links(output)
    if output.exists():
        raise ValueError("Bundle output already exists; choose a fresh directory")
    if output.resolve().is_relative_to((root / ".workshop-data").resolve()):
        raise ValueError("Export bundle outside generated data")
    settings = load_settings()
    store = store_type(replace(settings, mode=mode, data_dir=target))
    snapshot = store.collection.get(include=["documents", "metadatas", "embeddings"])
    records = [{
        "id": chunk_id, "document": document, "metadata": metadata,
        "embedding": [float(value) for value in embedding],
    } for chunk_id, document, metadata, embedding in zip(
        snapshot["ids"], snapshot["documents"], snapshot["metadatas"],
        snapshot["embeddings"], strict=True,
    )]
    sources, _, uploads = source_contract(root)
    files = {"catalog.json": (target / "catalog.json").read_bytes(),
             "vectors.json": encoded(records)}
    for name in uploads:
        path = target / name
        reject_links(path)
        files[name] = path.read_bytes()
    manifest = {
        "format": FORMAT, "chroma_version": importlib.metadata.version("chromadb"),
        "embedding_model": settings.embedding_model,
        "dimension": DIMENSIONS.get(settings.embedding_model), "chunking": CHUNKING,
        "sources": sources, "record_count": len(records),
        "files": {name: digest(data) for name, data in files.items()},
    }
    validate_payload(root, manifest, files, settings.embedding_model)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    try:
        for name, data in {**files, "manifest.json": encoded(manifest)}.items():
            path = output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(data)
    except BaseException:
        shutil.rmtree(output)
        raise
    print(f"Exported {len(records)} exact vectors and approved PDFs to {output}")


def close_store(store) -> None:
    if store is not None and store._chroma is not None:
        store._chroma._system.stop()
        from chromadb.api.client import SharedSystemClient

        SharedSystemClient.clear_system_cache()


def import_corpus(root: Path, surface: str, mode: str, bundle: Path) -> Path:
    load_settings, store_type, _ = infrastructure()
    target = data_target(root, surface, mode)
    empty_target(target)
    settings = load_settings()
    manifest, files = read_bundle(bundle)
    records = validate_payload(root, manifest, files, settings.embedding_model)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".corpus-import-", dir=target.parent))
    store = None
    try:
        store = store_type(replace(settings, mode=mode, data_dir=temporary))
        for offset in range(0, len(records), 64):
            batch = records[offset:offset + 64]
            store.collection.upsert(
                ids=[item["id"] for item in batch],
                documents=[item["document"] for item in batch],
                metadatas=[item["metadata"] for item in batch],
                embeddings=[item["embedding"] for item in batch],
            )
        for name, data in files.items():
            if name == "vectors.json":
                continue
            path = temporary / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        close_store(store)
        store = None
        empty_target(target)
        if target.exists():
            target.rmdir()
        temporary.rename(target)
    except BaseException:
        close_store(store)
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    print(f"Imported {len(records)} exact vectors to {target}; no re-embedding or histories.")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "export", "import"):
        command = commands.add_parser(name)
        command.add_argument("--surface", required=True, choices=["app", "notebook"])
        command.add_argument("--mode", required=True, choices=["student", "solution"])
        if name == "export":
            command.add_argument("--output", required=True, type=Path)
        elif name == "import":
            command.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "build":
            asyncio.run(build(ROOT, args.surface, args.mode))
        elif args.command == "export":
            export(ROOT, args.surface, args.mode, args.output.absolute())
        else:
            import_corpus(ROOT, args.surface, args.mode, args.bundle.absolute())
    except Exception:
        parser.exit(2, "Corpus operation refused/failed. Check credentials (build only), locked "
                    "versions/model, original PDFs, manifest integrity and an empty destination. "
                    "No provider exception details are printed. Stop writers before retrying.\n")


if __name__ == "__main__":
    main()
