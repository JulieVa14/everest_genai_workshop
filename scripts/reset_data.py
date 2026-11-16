"""Delete only explicitly selected generated workshop data; stop writers first."""

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def reject_links(path: Path) -> None:
    for item in (path, *path.parents):
        if item.is_symlink() or item.is_junction():
            raise ValueError("Linked paths are not allowed")


def data_target(root: Path, surface: str, mode: str) -> Path:
    if surface not in {"app", "notebook"} or mode not in {"student", "solution"}:
        raise ValueError("Choose app/notebook and student/solution")
    reject_links(root)
    target = root.absolute() / ".workshop-data" / surface / mode
    reject_links(target)
    if target.resolve().parent != (root / ".workshop-data" / surface).resolve():
        raise ValueError("Data path escapes the workshop")
    if target.exists() and not target.is_dir():
        raise ValueError("Data target must be a directory")
    return target


def reset(root: Path, surface: str, mode: str, confirm: bool = False) -> Path:
    target = data_target(root, surface, mode)
    if not confirm:
        raise ValueError("Stop all writers, then pass --confirm to delete generated data")
    if target.exists():
        for child in target.rglob("*"):
            reject_links(child)
        shutil.rmtree(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surface", required=True, choices=["app", "notebook"])
    parser.add_argument("--mode", required=True, choices=["student", "solution"])
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    try:
        target = reset(ROOT, args.surface, args.mode, args.confirm)
    except ValueError as error:
        parser.exit(2, f"Reset refused: {error}\n")
    print(f"Generated data cleared (or already absent): {target}")


if __name__ == "__main__":
    main()
