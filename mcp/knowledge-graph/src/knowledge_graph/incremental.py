from __future__ import annotations

import hashlib
import os
import re
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

    def scan(self, root: Path, progress_callback=None) -> WorkspaceScanResult:
        root = Path(root).resolve()
        discovered_files = self._discover_files(root)
        snapshots: list[WorkspaceFileSnapshot] = []
        total = len(discovered_files)

        for index, file_path in enumerate(discovered_files, start=1):
            content = file_path.read_bytes()
            language = self.registry.detect(file_path)
            inferred_language_id = self._infer_language_id(file_path, content)
            if language is None and inferred_language_id is None:
                if progress_callback is not None:
                    progress_callback(
                        {
                            "stage": "scan",
                            "current": index,
                            "total": total,
                            "path": str(file_path),
                            "message": f"Skipped unsupported file {file_path.name}",
                        }
                    )
                continue
            if language is None or (
                inferred_language_id is not None and inferred_language_id != language.language_id
            ):
                if inferred_language_id is not None:
                    language = self.registry.get(inferred_language_id)
            stat = file_path.stat()
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
            if progress_callback is not None:
                progress_callback(
                    {
                        "stage": "scan",
                        "current": index,
                        "total": total,
                        "path": str(file_path),
                        "language_id": language.language_id,
                        "message": f"Scanned {index}/{total}: {file_path.name}",
                    }
                )
        return WorkspaceScanResult(root=root, files=tuple(sorted(snapshots, key=lambda item: item.path)))

    def update(self, root: Path, progress_callback=None) -> IncrementalUpdateResult:
        scan_result = self.scan(root, progress_callback=progress_callback)
        existing = {snapshot.path: snapshot for snapshot in self.store.list_file_snapshots()}
        current = {snapshot.path: snapshot for snapshot in scan_result.files}
        diagnostics: list[ParseDiagnostic] = []

        deleted_paths = sorted(set(existing) - set(current))
        for relative_path in deleted_paths:
            self.store.delete_file(relative_path)

        added_files = 0
        modified_files = 0
        skipped_files = 0

        total = len(scan_result.files)
        for index, snapshot in enumerate(scan_result.files, start=1):
            if progress_callback is not None:
                progress_callback(
                    {
                        "stage": "index",
                        "current": index,
                        "total": total,
                        "path": snapshot.path,
                        "message": f"Indexing {index}/{total}: {snapshot.path}",
                    }
                )
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
        if progress_callback is not None:
            progress_callback(
                {
                    "stage": "complete",
                    "current": total,
                    "total": total,
                    "message": "Index build complete",
                }
            )
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

    def _infer_language_id(self, path: Path, content: bytes) -> str | None:
        suffix = path.suffix.lower()
        text = content.decode("utf-8", errors="ignore")
        if not text.strip():
            return None
        if "\x00" in text:
            return None

        first_lines = "\n".join(text.splitlines()[:20]).lower()
        lowered = text.lower()

        if suffix in {".sv", ".svh", ".v", ".vh"}:
            return "systemverilog"
        if suffix in {".rb", ".rake", ".gemspec"} or re.search(r"^\s*(?:class|module|def)\s+[A-Za-z_]", text, re.MULTILINE):
            return "ruby"
        if suffix in {".c", ".h"}:
            if re.search(r"\btemplate\s*<|::|namespace\s+\w+|class\s+\w+\s*(?:final\s*)?(?:[:{]|\b)", text):
                return "cpp"
            return "c"
        if suffix in {".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"}:
            return "cpp"
        if suffix in {".html", ".htm"} or "<!doctype html" in lowered or "<html" in lowered:
            return "html"
        if suffix == ".css" or re.search(r"^\s*@(?:import|media|supports|container|keyframes)\b", text, re.MULTILINE | re.IGNORECASE):
            return "css"
        if suffix == ".sql" or re.search(r"^\s*create\s+(?:table|view|function|procedure|trigger|index|schema)\b", text, re.MULTILINE | re.IGNORECASE):
            return "sql"
        if suffix in {".go"} or re.search(r"^\s*package\s+\w+\s*$", text, re.MULTILINE):
            return "go"
        if suffix in {".java"} or re.search(r"^\s*import\s+java\.", text, re.MULTILINE):
            return "java"
        if suffix in {".rs"} or re.search(r"^\s*(?:pub\s+)?(?:fn|struct|enum|trait|impl)\b", text, re.MULTILINE):
            return "rust"
        if suffix in {".js", ".mjs", ".cjs", ".jsx"}:
            return "javascript"
        if suffix in {".ts", ".tsx"}:
            return "typescript" if suffix == ".ts" else "tsx"
        if suffix in {".py", ".pyi"} or re.search(r"^\s*(?:from\s+\S+\s+import|import\s+\S+|def\s+\w+|class\s+\w+)", text, re.MULTILINE):
            return "python"
        if re.search(r"<\s*(?:script|style|template|section|article|nav|main|header|footer|aside|form)\b", text, re.IGNORECASE):
            return "html"
        if re.search(r"\b(?:module|interface|package|covergroup|sequence|property|checker)\s+\w+", text, re.IGNORECASE):
            return "systemverilog"
        if re.search(r"^\s*require(?:_relative)?\s+['\"]", text, re.MULTILINE):
            return "ruby"
        if re.search(
            r"\b(?:class|struct|enum|interface|module|package|function|fn|def|import|from|include|require|using|namespace|CREATE\s+(?:TABLE|VIEW|FUNCTION|PROCEDURE|TRIGGER|INDEX)|#include)\b",
            text,
            re.IGNORECASE,
        ):
            return "generic"
        return None

