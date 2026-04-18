from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .parser import EdgeRecord, ParseDiagnostic, ParseResult, Position, Span, SymbolRecord


@dataclass(frozen=True, slots=True)
class WorkspaceFileSnapshot:
    path: str
    language_id: str
    content_hash: str
    size: int
    mtime_ns: int
    module_name: str


class SQLiteGraphStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._reset_if_incompatible()
        self._initialize_schema()

    def _connect(self) -> None:
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def _table_columns(self, table: str) -> set[str]:
        rows = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(row["name"]) for row in rows}

    def _reset_if_incompatible(self) -> None:
        expected_columns = {
            "files": {
                "id",
                "path",
                "module_name",
                "language_id",
                "content_hash",
                "size",
                "mtime_ns",
                "indexed_at",
            },
            "symbols": {
                "id",
                "file_id",
                "kind",
                "name",
                "qualified_name",
                "start_line",
                "start_col",
                "end_line",
                "end_col",
                "metadata_json",
            },
            "edges": {
                "id",
                "source_file_id",
                "source_symbol_id",
                "target_file_id",
                "target_symbol_id",
                "edge_kind",
                "target_ref",
                "metadata_json",
            },
            "diagnostics": {
                "id",
                "file_id",
                "level",
                "message",
                "metadata_json",
            },
        }

        for table, required_columns in expected_columns.items():
            exists = self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            if exists is None:
                continue
            if not required_columns.issubset(self._table_columns(table)):
                self._conn.close()
                try:
                    self.db_path.unlink()
                except FileNotFoundError:
                    pass
                self._connect()
                return

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SQLiteGraphStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _initialize_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                module_name TEXT NOT NULL,
                language_id TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                size INTEGER NOT NULL,
                mtime_ns INTEGER NOT NULL,
                indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                qualified_name TEXT NOT NULL,
                start_line INTEGER,
                start_col INTEGER,
                end_line INTEGER,
                end_col INTEGER,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                source_symbol_id INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
                target_file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
                target_symbol_id INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
                edge_kind TEXT NOT NULL,
                target_ref TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
            CREATE INDEX IF NOT EXISTS idx_symbols_file_id ON symbols(file_id);
            CREATE INDEX IF NOT EXISTS idx_edges_source_file_id ON edges(source_file_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target_file_id ON edges(target_file_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target_ref ON edges(target_ref);
            """
        )
        self._conn.commit()

    def upsert_file_snapshot(self, snapshot: WorkspaceFileSnapshot) -> int:
        row = self._conn.execute("SELECT id FROM files WHERE path = ?", (snapshot.path,)).fetchone()
        if row is None:
            cursor = self._conn.execute(
                """
                INSERT INTO files(path, module_name, language_id, content_hash, size, mtime_ns)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (snapshot.path, snapshot.module_name, snapshot.language_id, snapshot.content_hash, snapshot.size, snapshot.mtime_ns),
            )
            self._conn.commit()
            return int(cursor.lastrowid)

        self._conn.execute(
            """
            UPDATE files
            SET module_name = ?, language_id = ?, content_hash = ?, size = ?, mtime_ns = ?, indexed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (snapshot.module_name, snapshot.language_id, snapshot.content_hash, snapshot.size, snapshot.mtime_ns, int(row["id"])),
        )
        self._conn.commit()
        return int(row["id"])

    def delete_file(self, path: str) -> None:
        self._conn.execute("DELETE FROM files WHERE path = ?", (path,))
        self._conn.commit()

    def clear(self) -> None:
        self._conn.executescript(
            """
            DELETE FROM diagnostics;
            DELETE FROM edges;
            DELETE FROM symbols;
            DELETE FROM files;
            DELETE FROM sqlite_sequence WHERE name IN ('diagnostics', 'edges', 'symbols', 'files');
            """
        )
        self._conn.commit()

    def get_file_snapshot(self, path: str) -> WorkspaceFileSnapshot | None:
        row = self._conn.execute(
            "SELECT path, module_name, language_id, content_hash, size, mtime_ns FROM files WHERE path = ?",
            (path,),
        ).fetchone()
        if row is None:
            return None
        return WorkspaceFileSnapshot(
            path=row["path"],
            module_name=row["module_name"],
            language_id=row["language_id"],
            content_hash=row["content_hash"],
            size=int(row["size"]),
            mtime_ns=int(row["mtime_ns"]),
        )

    def list_file_snapshots(self) -> list[WorkspaceFileSnapshot]:
        rows = self._conn.execute(
            "SELECT path, module_name, language_id, content_hash, size, mtime_ns FROM files ORDER BY path"
        ).fetchall()
        return [
            WorkspaceFileSnapshot(
                path=row["path"],
                module_name=row["module_name"],
                language_id=row["language_id"],
                content_hash=row["content_hash"],
                size=int(row["size"]),
                mtime_ns=int(row["mtime_ns"]),
            )
            for row in rows
        ]

    def fetch_file_rows(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, path, module_name, language_id, content_hash, size, mtime_ns FROM files ORDER BY path"
        ).fetchall()
        return [dict(row) for row in rows]

    def replace_file_graph(self, file_id: int, parse_result: ParseResult) -> None:
        self._conn.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))
        self._conn.execute("DELETE FROM edges WHERE source_file_id = ?", (file_id,))

        symbol_ids: dict[str, int] = {}
        for symbol in parse_result.symbols:
            symbol_id = self._insert_symbol(file_id, symbol)
            symbol_ids[symbol.qualified_name] = symbol_id
            symbol_ids[symbol.name] = symbol_id

        for edge in parse_result.edges:
            self._insert_edge(file_id, edge, symbol_ids)

        self._insert_diagnostics(file_id, parse_result.diagnostics)
        self._conn.commit()

    def _insert_symbol(self, file_id: int, symbol: SymbolRecord) -> int:
        span = symbol.span
        if span is None:
            start_line = start_col = end_line = end_col = None
        else:
            start_line = span.start.line
            start_col = span.start.column
            end_line = span.end.line
            end_col = span.end.column
        cursor = self._conn.execute(
            """
            INSERT INTO symbols(file_id, kind, name, qualified_name, start_line, start_col, end_line, end_col, metadata_json)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                symbol.kind,
                symbol.name,
                symbol.qualified_name,
                start_line,
                start_col,
                end_line,
                end_col,
                json.dumps(symbol.metadata, sort_keys=True),
            ),
        )
        return int(cursor.lastrowid)

    def _insert_edge(self, file_id: int, edge: EdgeRecord, symbol_ids: dict[str, int]) -> None:
        target_symbol_id = symbol_ids.get(edge.target_ref)
        self._conn.execute(
            """
            INSERT INTO edges(source_file_id, source_symbol_id, target_file_id, target_symbol_id, edge_kind, target_ref, metadata_json)
            VALUES(?, NULL, NULL, ?, ?, ?, ?)
            """,
            (file_id, target_symbol_id, edge.kind, edge.target_ref, json.dumps(edge.metadata, sort_keys=True)),
        )

    def _insert_diagnostics(self, file_id: int, diagnostics: Iterable[ParseDiagnostic]) -> None:
        self._conn.execute("DELETE FROM diagnostics WHERE file_id = ?", (file_id,)) if self._has_diagnostics_table() else None
        if not self._has_diagnostics_table():
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS diagnostics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
        self._conn.execute("DELETE FROM diagnostics WHERE file_id = ?", (file_id,))
        for diagnostic in diagnostics:
            self._conn.execute(
                """
                INSERT INTO diagnostics(file_id, level, message, metadata_json)
                VALUES(?, ?, ?, ?)
                """,
                (file_id, diagnostic.level, diagnostic.message, json.dumps(diagnostic.metadata, sort_keys=True)),
            )

    def _has_diagnostics_table(self) -> bool:
        row = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'diagnostics'"
        ).fetchone()
        return row is not None

    def resolve_import_edges(self) -> int:
        files = self._conn.execute("SELECT id, path, module_name FROM files").fetchall()
        module_map = {row["module_name"]: int(row["id"]) for row in files}
        path_map = {row["path"]: int(row["id"]) for row in files}
        basename_map = {Path(str(row["path"])).name.lower(): int(row["id"]) for row in files}

        edges = self._conn.execute(
            "SELECT id, target_ref FROM edges WHERE edge_kind = 'imports' AND target_ref IS NOT NULL"
        ).fetchall()

        resolved = 0
        for edge in edges:
            target_ref = edge["target_ref"]
            target_file_id = module_map.get(target_ref)
            if target_file_id is None:
                normalized = target_ref.replace("/", ".").strip(".")
                target_file_id = module_map.get(normalized)
            if target_file_id is None:
                candidate_path = target_ref.replace(".", "/")
                if not candidate_path.endswith(".py"):
                    candidate_path = f"{candidate_path}.py"
                for path, file_id in path_map.items():
                    if path.endswith(candidate_path) or path.endswith(candidate_path.replace("/", "\\")):
                        target_file_id = file_id
                        break
            if target_file_id is None:
                basename = Path(str(target_ref).replace("\\", "/")).name.lower()
                target_file_id = basename_map.get(basename)
            if target_file_id is None:
                continue
            self._conn.execute("UPDATE edges SET target_file_id = ? WHERE id = ?", (target_file_id, int(edge["id"])))
            resolved += 1
        self._conn.commit()
        return resolved

    def resolve_symbol_edges(self) -> int:
        symbols = self._conn.execute("SELECT id, file_id, name, qualified_name FROM symbols").fetchall()
        symbol_map: dict[str, tuple[int, int]] = {}
        for row in symbols:
            file_id = int(row["file_id"])
            symbol_id = int(row["id"])
            symbol_map.setdefault(str(row["name"]), (symbol_id, file_id))
            symbol_map.setdefault(str(row["qualified_name"]), (symbol_id, file_id))

        edges = self._conn.execute(
            "SELECT id, target_ref FROM edges WHERE edge_kind = 'references' AND target_ref IS NOT NULL"
        ).fetchall()

        resolved = 0
        for edge in edges:
            target_ref = str(edge["target_ref"])
            match = symbol_map.get(target_ref)
            if match is None:
                cleaned = target_ref.split("(", 1)[0].split(".", 1)[0].strip()
                match = symbol_map.get(cleaned)
            if match is None:
                continue
            target_symbol_id, target_file_id = match
            self._conn.execute(
                "UPDATE edges SET target_symbol_id = ?, target_file_id = ? WHERE id = ?",
                (target_symbol_id, target_file_id, int(edge["id"])),
            )
            resolved += 1
        self._conn.commit()
        return resolved

    def stats(self) -> dict[str, int]:
        return {
            "files": self._scalar_count("files"),
            "symbols": self._scalar_count("symbols"),
            "edges": self._scalar_count("edges"),
            "diagnostics": self._scalar_count("diagnostics"),
        }

    def _scalar_count(self, table: str) -> int:
        row = self._conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
        return int(row["count"]) if row is not None else 0

    def fetch_edges(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT id, source_file_id, source_symbol_id, target_file_id, target_symbol_id, edge_kind, target_ref, metadata_json
            FROM edges
            ORDER BY id
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def fetch_symbols(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT id, file_id, kind, name, qualified_name, start_line, start_col, end_line, end_col, metadata_json
            FROM symbols
            ORDER BY id
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def fetch_diagnostics(self) -> list[dict[str, Any]]:
        row = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'diagnostics'"
        ).fetchone()
        if row is None:
            return []
        rows = self._conn.execute(
            """
            SELECT id, file_id, level, message, metadata_json
            FROM diagnostics
            ORDER BY id
            """
        ).fetchall()
        return [dict(row) for row in rows]

