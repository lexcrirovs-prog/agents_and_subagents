#!/usr/bin/env python3
"""Build an archive-ready subscriber-kit folder from the public repo."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT_DIR / "dist" / "subscriber-kit"

INCLUDE_PATHS = (
    "README.md",
    ".gitignore",
    "docs",
    "agent-templates",
    "client-files",
    "ductor",
    "project-vault-generic",
    "runtime-template",
    "scripts",
    "shared-generic",
    "skills-generic",
)

EXCLUDE_DIR_NAMES = frozenset(
    {
        ".git",
        ".github",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "dist",
        "node_modules",
    }
)

EXCLUDE_RELATIVE_DIRS = frozenset(
    {
        "docs/internal",
        "ductor/docs",
        "ductor/tests",
        "runtime-template/logs",
        "scripts/__pycache__",
    }
)

EXCLUDE_FILE_SUFFIXES = (".pyc", ".pyo")
EXCLUDE_FILE_NAMES = frozenset({".DS_Store"})


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Destination directory for the built subscriber kit.",
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Also create a .zip archive next to the built subscriber kit folder.",
    )
    parser.add_argument(
        "--zip-path",
        help="Optional explicit path for the .zip archive. Defaults to <output>.zip",
    )
    return parser.parse_args()


def _should_skip_dir(root: Path, path: Path, *, prefix: str = "") -> bool:
    rel = path.relative_to(root).as_posix()
    project_rel = f"{prefix}/{rel}" if prefix else rel
    if path.name in EXCLUDE_DIR_NAMES:
        return True
    return _is_under_excluded_relative_dir(project_rel)


def _is_under_excluded_relative_dir(rel: str) -> bool:
    return any(rel == blocked or rel.startswith(f"{blocked}/") for blocked in EXCLUDE_RELATIVE_DIRS)


def _should_skip_file(path: Path) -> bool:
    if path.name in EXCLUDE_FILE_NAMES:
        return True
    return path.suffix in EXCLUDE_FILE_SUFFIXES


def _copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _copy_tree(src_root: Path, dest_root: Path, *, prefix: str = "") -> None:
    for path in src_root.rglob("*"):
        if path.is_dir():
            if _should_skip_dir(src_root, path, prefix=prefix):
                continue
            continue
        if _should_skip_file(path):
            continue
        rel = path.relative_to(src_root).as_posix()
        project_rel = f"{prefix}/{rel}" if prefix else rel
        if _is_under_excluded_relative_dir(project_rel):
            continue
        if any(part in EXCLUDE_DIR_NAMES for part in path.parts):
            continue
        _copy_file(path, dest_root / Path(rel))


def _write_manifest(dest: Path) -> None:
    manifest = {
        "built_at_utc": datetime.now(UTC).isoformat(),
        "source_repo": "agents_and_subagents",
        "paths": list(INCLUDE_PATHS),
        "excluded_dirs": sorted(EXCLUDE_DIR_NAMES),
        "excluded_relative_dirs": sorted(EXCLUDE_RELATIVE_DIRS),
    }
    (dest / "BUILD_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _build_zip(output: Path, zip_path: Path | None) -> Path:
    target = zip_path if zip_path is not None else output.with_suffix(".zip")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    archive_base = target.with_suffix("")
    if archive_base.with_suffix(".zip") != target:
        archive_base = target.parent / target.stem
    built = shutil.make_archive(str(archive_base), "zip", root_dir=output.parent, base_dir=output.name)
    built_path = Path(built)
    if built_path != target:
        if target.exists():
            target.unlink()
        built_path.replace(target)
    return target


def main() -> int:
    args = _parse_args()
    output = Path(args.output).expanduser().resolve()
    zip_path = Path(args.zip_path).expanduser().resolve() if args.zip_path else None

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    for relative in INCLUDE_PATHS:
        src = ROOT_DIR / relative
        dest = output / relative
        if not src.exists():
            continue
        if src.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            _copy_tree(src, dest, prefix=relative)
        else:
            _copy_file(src, dest)

    _write_manifest(output)
    print(output)
    if args.zip:
        archive = _build_zip(output, zip_path)
        print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
