"""Build and update the local code graph."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json

from .models import BuildSummary
from .parser import parse_file
from .storage import GraphStore


IGNORED_DIRS = {".git", ".venv", "__pycache__", ".code-review-graph", "node_modules", "dist", "build"}


def iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in {".py", ".js", ".jsx", ".ts", ".tsx", ".go"}:
            files.append(path)
    return files


def build_graph(root: Path, db_path: Path) -> BuildSummary:
    store = GraphStore(db_path)
    changed = 0
    nodes = 0
    edges = 0
    files = iter_source_files(root)
    with store.connect():
        pass
    for path in files:
        parsed = parse_file(root, path)
        rel = path.relative_to(root).as_posix()
        store.clear_file(rel)
        store.upsert_file(rel, parsed.sha256, parsed.language, datetime.now(timezone.utc).isoformat())
        store.insert_symbols((rel, name, kind, start, end) for name, kind, start, end in parsed.symbols)
        store.insert_edges(parsed.edges)
        changed += 1
        nodes += len(parsed.symbols)
        edges += len(parsed.edges)
    return BuildSummary(
        root=str(root),
        database=str(db_path),
        files_scanned=len(files),
        files_changed=changed,
        nodes_indexed=nodes,
        edges_indexed=edges,
        mode="full",
    )


def update_graph(root: Path, db_path: Path) -> BuildSummary:
    store = GraphStore(db_path)
    existing = store.known_files()
    files = iter_source_files(root)
    current_paths = {path.relative_to(root).as_posix() for path in files}
    changed = 0
    nodes = 0
    edges = 0

    for stale_path in sorted(set(existing) - current_paths):
        store.clear_file(stale_path)
        changed += 1

    for path in files:
        parsed = parse_file(root, path)
        rel = path.relative_to(root).as_posix()
        if existing.get(rel) == parsed.sha256:
            continue
        store.clear_file(rel)
        store.upsert_file(rel, parsed.sha256, parsed.language, datetime.now(timezone.utc).isoformat())
        store.insert_symbols((rel, name, kind, start, end) for name, kind, start, end in parsed.symbols)
        store.insert_edges(parsed.edges)
        changed += 1
        nodes += len(parsed.symbols)
        edges += len(parsed.edges)
    return BuildSummary(
        root=str(root),
        database=str(db_path),
        files_scanned=len(files),
        files_changed=changed,
        nodes_indexed=nodes,
        edges_indexed=edges,
        mode="incremental",
    )
