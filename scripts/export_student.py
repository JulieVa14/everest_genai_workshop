"""Export allowlisted student materials to a NEW directory or NEW zip archive."""

import argparse
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDFS = (
    "00-Intro.pdf", "01-LLMs.pdf", "02-LLMS_Applications_and_Tools.pdf",
    "03-Image_Generation.pdf", "04-Audio_Generation.pdf", "05-GAI_ethics.pdf",
)
FIXED = (
    "README.md", "requirements.txt", "backend/__init__.py", "backend/pyproject.toml", "backend/uv.lock",
    "backend/.python-version", "backend/.env.example",
    "frontend/index.html", "frontend/package.json", "frontend/package-lock.json",
    "frontend/tsconfig.json", "frontend/tsconfig.node.json", "frontend/vite.config.ts",
    "notebooks/course_companion.ipynb", "exercises/workshop.md",
    "scripts/launch.ps1", "scripts/reset_data.py", "scripts/export_student.py",
    "scripts/prepare_corpus.py",
)
APP_MODULES = (
    "__init__", "config", "errors", "exercise_steps", "exercise_wiring", "main",
    "notebook_support", "retrieval", "schemas", "tutor", "student_code/__init__",
    "student_code/exercise_1", "student_code/exercise_2", "student_code/exercise_3",
    "student_code/exercise_4",
)


def reject_links(path: Path) -> None:
    for item in (path, *path.parents):
        if item.is_symlink() or item.is_junction():
            raise ValueError("Linked paths are not allowed")


def clean_notebook(data: bytes) -> bytes:
    notebook = json.loads(data)
    if notebook.get("nbformat") != 4 or not isinstance(notebook.get("cells"), list):
        raise ValueError("Expected a version 4 student notebook")
    cells = []
    for cell in notebook["cells"]:
        kind = cell["cell_type"]
        if kind not in {"code", "markdown", "raw"}:
            raise ValueError("Unsupported notebook cell")
        source = cell["source"]
        text = "".join(source) if isinstance(source, list) else source
        if not isinstance(text, str):
            raise ValueError("Invalid notebook source")
        if re.search(r"\b(?:from|import)\s+instructor\b|course_companion_solution|sk-[\w-]{12,}",
                     text):
            raise ValueError("Student notebook contains instructor imports or a credential")
        if re.search(r"(?i)OPENAI_API_KEY\s*[=\]]\s*['\"][^'\"]+['\"]", text):
            raise ValueError("Student notebook contains a literal API credential")
        cleaned = {"cell_type": kind, "metadata": {}, "source": source}
        if "id" in cell:
            cleaned["id"] = cell["id"]
        if kind == "code":
            cleaned.update(outputs=[], execution_count=None)
        cells.append(cleaned)
    result = {
        "nbformat": 4, "nbformat_minor": notebook.get("nbformat_minor", 5),
        "metadata": {"kernelspec": {
            "display_name": "Python 3.12", "language": "python", "name": "python3",
        }}, "cells": cells,
    }
    return (json.dumps(result, indent=2, ensure_ascii=True) + "\n").encode()


def student_files(root: Path) -> dict[str, bytes]:
    reject_links(root)
    paths = [root / name for name in FIXED]
    paths.extend(root / "backend/app" / f"{name}.py" for name in APP_MODULES)
    for folder, suffixes in (("frontend/src", {".ts", ".tsx", ".css"}),
                             ("frontend/public", {".svg", ".txt", ".json", ".css"})):
        base = root / folder
        reject_links(base)
        if base.exists():
            for path in base.rglob("*"):
                relative = path.relative_to(base)
                if any(part.startswith(".") or part in {
                    "tests", "__tests__", "node_modules", "dist", "build", "coverage",
                } for part in relative.parts):
                    continue
                if (path.suffix in suffixes and not re.search(r"\.(test|spec)\.", path.name)
                        and path.name != "testSetup.ts"):
                    paths.append(path)
    for name in PDFS:
        path = root / "docs" / name
        if not path.is_file():
            raise ValueError(f"Required original PDF missing: docs/{name}")
        paths.append(path)
    result = {}
    for path in paths:
        reject_links(path)
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        data = path.read_bytes()
        result[name] = clean_notebook(data) if path.suffix == ".ipynb" else data
    return result


def export(root: Path, output: Path, archive: bool = False) -> int:
    reject_links(output)
    output = output.absolute()
    if output.exists():
        raise ValueError("Output already exists; choose a fresh destination")
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Export outside the source checkout")
    if archive and output.suffix.lower() != ".zip":
        raise ValueError("Archive output must have a .zip extension")
    files = student_files(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    if archive:
        with output.open("xb") as stream:
            try:
                with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as package:
                    for name, data in sorted(files.items()):
                        package.writestr(name, data)
            except BaseException:
                stream.close()
                output.unlink()
                raise
    else:
        output.mkdir()
        try:
            for name, data in sorted(files.items()):
                path = output / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(data)
        except BaseException:
            shutil.rmtree(output)
            raise
    return len(files)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    outputs = parser.add_mutually_exclusive_group(required=True)
    outputs.add_argument("--destination", type=Path)
    outputs.add_argument("--archive", type=Path)
    args = parser.parse_args()
    try:
        count = export(ROOT, args.archive or args.destination, args.archive is not None)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Export refused: {error}\n")
    print(f"Exported {count} allowlisted files to {args.archive or args.destination}")


if __name__ == "__main__":
    main()
