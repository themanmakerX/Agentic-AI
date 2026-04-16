from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..incremental import IncrementalIndexer
from ..languages import LanguageDefinition, build_default_registry
from ..parser import EdgeRecord, GraphParser, ParseDiagnostic, ParseResult, ParserBackend, SymbolRecord
from ..storage import SQLiteGraphStore


@dataclass(frozen=True, slots=True)
class BuildSummary:
    files_scanned: int
    nodes_indexed: int
    edges_indexed: int
    diagnostics: tuple[ParseDiagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class UpdateSummary:
    files_changed: int
    files_added: int
    files_modified: int
    files_deleted: int
    files_skipped: int
    diagnostics: tuple[ParseDiagnostic, ...] = ()


class HeuristicBackend(ParserBackend):
    """Fallback backend for environments without Tree-sitter grammars installed."""

    def parse(self, *, path: Path, source: bytes, language: LanguageDefinition):
        return _HeuristicSyntaxTree(source=source, path=path, language_id=language.language_id)


class _HeuristicSyntaxTree:
    def __init__(self, *, source: bytes, path: Path, language_id: str) -> None:
        self.source = source
        self.path = path
        self.language_id = language_id


class _HeuristicExtractor:
    def extract(self, *, path: Path, language: LanguageDefinition, root, source: bytes):
        text = source.decode("utf-8", errors="ignore")
        symbols: list[SymbolRecord] = []
        edges: list[EdgeRecord] = []

        if language.language_id == "python":
            symbols.extend(_extract_python_symbols(text))
            edges.extend(_extract_python_imports(text))
        else:
            symbols.extend(_extract_generic_symbols(text))
            edges.extend(_extract_generic_imports(text))

        return tuple(symbols), tuple(edges), ()


def build_graph(root: Path, db_path: Path) -> BuildSummary:
    store = SQLiteGraphStore(db_path)
    parser = GraphParser(backend=HeuristicBackend(), extractor=_HeuristicExtractor())
    indexer = IncrementalIndexer(registry=build_default_registry(), parser=parser, store=store)
    result = indexer.update(root)
    stats = store.stats()
    store.close()
    return BuildSummary(
        files_scanned=result.scanned_files,
        nodes_indexed=stats["symbols"],
        edges_indexed=stats["edges"],
        diagnostics=result.diagnostics,
    )


def update_graph(root: Path, db_path: Path) -> UpdateSummary:
    store = SQLiteGraphStore(db_path)
    parser = GraphParser(backend=HeuristicBackend(), extractor=_HeuristicExtractor())
    indexer = IncrementalIndexer(registry=build_default_registry(), parser=parser, store=store)
    result = indexer.update(root)
    store.close()
    return UpdateSummary(
        files_changed=result.added_files + result.modified_files + result.deleted_files,
        files_added=result.added_files,
        files_modified=result.modified_files,
        files_deleted=result.deleted_files,
        files_skipped=result.skipped_files,
        diagnostics=result.diagnostics,
    )


def _extract_python_symbols(text: str) -> list[SymbolRecord]:
    symbols: list[SymbolRecord] = []
    lines = text.splitlines()
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("class ") or stripped.startswith("def "):
            head = stripped.split("(", 1)[0]
            kind = "class" if head.startswith("class ") else "function"
            name = head.split()[1].rstrip(":")
            symbols.append(
                SymbolRecord(
                    kind=kind,
                    name=name,
                    qualified_name=name,
                    span=None,
                    metadata={"line": line_no},
                )
            )
    return symbols


def _extract_python_imports(text: str) -> list[EdgeRecord]:
    edges: list[EdgeRecord] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("import "):
            modules = [module.strip() for module in stripped[len("import ") :].split(",")]
            for module in modules:
                if module:
                    edges.append(EdgeRecord(kind="imports", target_ref=module, metadata={"syntax": "import"}))
        elif stripped.startswith("from ") and " import " in stripped:
            module = stripped.split(" import ", 1)[0].removeprefix("from ").strip()
            if module:
                edges.append(EdgeRecord(kind="imports", target_ref=module, metadata={"syntax": "from_import"}))
    return edges


def _extract_generic_symbols(text: str) -> list[SymbolRecord]:
    symbols: list[SymbolRecord] = []
    for token in text.split():
        if token.startswith("def "):
            name = token.split()[1].split("(")[0]
            symbols.append(SymbolRecord(kind="function", name=name, qualified_name=name))
    return symbols


def _extract_generic_imports(text: str) -> list[EdgeRecord]:
    edges: list[EdgeRecord] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("import "):
            for part in stripped[len("import ") :].split(","):
                module = part.strip().split(" as ", 1)[0]
                if module:
                    edges.append(EdgeRecord(kind="imports", target_ref=module))
    return edges

