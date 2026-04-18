from pathlib import Path

from knowledge_graph.incremental import IncrementalIndexer
from knowledge_graph.languages import build_default_registry
from knowledge_graph.parser import EdgeRecord, GraphParser, ParseDiagnostic, ParseResult, ParserBackend, Span, Position, SymbolRecord
from knowledge_graph.storage import SQLiteGraphStore, WorkspaceFileSnapshot


class StaticBackend(ParserBackend):
    def __init__(self, symbol_map: dict[str, tuple[list[SymbolRecord], list[EdgeRecord], list[ParseDiagnostic]]]) -> None:
        self.symbol_map = symbol_map

    def parse(self, *, path: Path, source: bytes, language):
        key = source.decode("utf-8")
        symbols, edges, diagnostics = self.symbol_map.get(key, ([], [], []))
        return _FakeTree(symbols, edges, diagnostics)


class _FakeTree:
    def __init__(self, symbols, edges, diagnostics):
        self.symbols = tuple(symbols)
        self.edges = tuple(edges)
        self.diagnostics = tuple(diagnostics)


class StaticGraphParser(GraphParser):
    def __init__(self, backend: StaticBackend):
        self._backend = backend

    def parse(self, *, path: Path, source: bytes, language, content_hash: str) -> ParseResult:
        tree = self._backend.parse(path=path, source=source, language=language)
        return ParseResult(
            path=path,
            language_id=language.language_id,
            content_hash=content_hash,
            symbols=tree.symbols,
            edges=tree.edges,
            diagnostics=tree.diagnostics,
        )


def _symbol(name: str) -> SymbolRecord:
    span = Span(start=Position(1, 1), end=Position(1, len(name) + 1))
    return SymbolRecord(kind="function", name=name, qualified_name=name, span=span)


def test_storage_replaces_file_graph(sample_repo_path) -> None:
    db_path = Path(r"C:\Users\acer\.codex\memories\knowledge-graph-storage.sqlite")
    db_path.unlink(missing_ok=True)
    store = SQLiteGraphStore(db_path)

    snapshot = WorkspaceFileSnapshot(
        path="app.py",
        module_name="app",
        language_id="python",
        content_hash="abc",
        size=12,
        mtime_ns=1,
    )
    file_id = store.upsert_file_snapshot(snapshot)
    result = ParseResult(
        path=Path("app.py"),
        language_id="python",
        content_hash="abc",
        symbols=(_symbol("main"),),
        edges=(EdgeRecord(kind="references", target_ref="main"),),
    )
    store.replace_file_graph(file_id, result)

    assert store.stats()["files"] == 1
    assert store.stats()["symbols"] == 1
    assert store.stats()["edges"] == 1
    assert store.fetch_symbols()[0]["name"] == "main"
    store.close()


def test_incremental_index_updates_only_changed_files(sample_repo_path) -> None:
    root = sample_repo_path
    (root / "app.py").write_text("v1", encoding="utf-8")
    (root / "util.py").write_text("v1", encoding="utf-8")

    db_path = Path(r"C:\Users\acer\.codex\memories\knowledge-graph-incremental.sqlite")
    db_path.unlink(missing_ok=True)
    store = SQLiteGraphStore(db_path)

    backend = StaticBackend(
        {
            "v1": ([_symbol("main")], [EdgeRecord(kind="imports", target_ref="util")], []),
            "v2": ([_symbol("main")], [EdgeRecord(kind="imports", target_ref="util")], []),
        }
    )
    parser = StaticGraphParser(backend)
    indexer = IncrementalIndexer(registry=build_default_registry(), parser=parser, store=store)

    first = indexer.update(root)
    assert first.added_files >= 2
    assert first.modified_files == 0
    assert first.skipped_files >= 0
    assert store.stats()["files"] >= 2

    (root / "app.py").write_text("v2", encoding="utf-8")
    second = indexer.update(root)
    assert second.added_files == 0
    assert second.modified_files >= 1
    assert second.skipped_files >= 1
    assert store.stats()["files"] >= 2
    assert store.stats()["symbols"] == 2
    store.close()


