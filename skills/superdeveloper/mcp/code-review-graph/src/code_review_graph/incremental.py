from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from .languages import LanguageRegistry
from .parser import GraphParser, ParseDiagnostic, ParseResult
from .storage import SQLiteGraphStore, WorkspaceFileSnapshot


@dataclass(frozen=True, slots=True)
class FileChange:
    path: Path
    status: str
    language_id: str | None


@dataclass(frozen=True, slots=True)
class WorkspaceScanResult:
    root: Path
    files: tuple[WorkspaceFileSnapshot, ...]


@dataclass(frozen=True, slots=True)
class IncrementalUpdateResult:
    scanned_files: int
    added_files: int
    modified_files: int
    deleted_files: int
    skipped_files: int
    resolved_import_edges: int
    diagnostics: tuple[ParseDiagnostic, ...] = ()


class IncrementalIndexer:
    def __init__(
        self,
        *,
        registry: LanguageRegistry,
        parser: GraphParser,
        store: SQLiteGraphStore,
        include_hidden: bool = False,
    ) -> None:
        self.registry = registry
        self.parser = parser
        self.store = store
        self.include_hidden = include_hidden

    def scan(self, root: Path) -> WorkspaceScanResult:
        root = Path(root).resolve()
        snapshots: list[WorkspaceFileSnapshot] = []
        for file_path in self._discover_files(root):
            language = self.registry.detect(file_path)
            if language is None:
                continue
            stat = file_path.stat()
            content = file_path.read_bytes()
            content_hash = self._hash_bytes(content)
            snapshots.append(
                WorkspaceFileSnapshot(
                    path=str(file_path.relative_to(root)),
                    module_name=self._module_name(root, file_path, language.language_id),
                    language_id=language.language_id,
                    content_hash=content_hash,
                    size=stat.st_size,
                    mtime_ns=stat.st_mtime_ns,
                )
            )
        return WorkspaceScanResult(root=root, files=tuple(sorted(snapshots, key=lambda item: item.path)))

    def update(self, root: Path) -> IncrementalUpdateResult:
        scan_result = self.scan(root)
        existing = {snapshot.path: snapshot for snapshot in self.store.list_file_snapshots()}
        current = {snapshot.path: snapshot for snapshot in scan_result.files}
        diagnostics: list[ParseDiagnostic] = []

        deleted_paths = sorted(set(existing) - set(current))
        for relative_path in deleted_paths:
            self.store.delete_file(relative_path)

        added_files = 0
        modified_files = 0
        skipped_files = 0

        for snapshot in scan_result.files:
            previous = existing.get(snapshot.path)
            if previous is not None and previous.content_hash == snapshot.content_hash:
                skipped_files += 1
                continue

            file_id = self.store.upsert_file_snapshot(snapshot)
            absolute_path = scan_result.root / snapshot.path
            language = self.registry.get(snapshot.language_id)
            content = absolute_path.read_bytes()
            parse_result = self.parser.parse(
                path=absolute_path,
                source=content,
                language=language,
                content_hash=snapshot.content_hash,
            )
            self.store.replace_file_graph(file_id, parse_result)
            diagnostics.extend(parse_result.diagnostics)

            if previous is None:
                added_files += 1
            else:
                modified_files += 1

        resolved_import_edges = self.store.resolve_import_edges()
        resolved_reference_edges = self.store.resolve_symbol_edges()
        return IncrementalUpdateResult(
            scanned_files=len(scan_result.files),
            added_files=added_files,
            modified_files=modified_files,
            deleted_files=len(deleted_paths),
            skipped_files=skipped_files,
            resolved_import_edges=resolved_import_edges + resolved_reference_edges,
            diagnostics=tuple(diagnostics),
        )

    def _discover_files(self, root: Path) -> list[Path]:
        result: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(root):
            current_dir = Path(dirpath)
            if not self.include_hidden:
                dirnames[:] = [name for name in dirnames if not name.startswith(".")]
            for filename in filenames:
                if not self.include_hidden and filename.startswith("."):
                    continue
                result.append(current_dir / filename)
        return result

    def _module_name(self, root: Path, path: Path, language_id: str) -> str:
        relative = path.relative_to(root)
        parts = list(relative.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        module = ".".join(part for part in parts if part)
        if not module:
            return relative.stem
        return module

    def _hash_bytes(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()
