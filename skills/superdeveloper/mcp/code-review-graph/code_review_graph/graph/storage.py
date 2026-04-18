"""SQLite storage for graph data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import sqlite3
from typing import Iterable


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    language TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    UNIQUE(file_path, name, kind, start_line, end_line)
);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    target_path TEXT NOT NULL,
    edge_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass(slots=True)
class GraphStore:
    db_path: Path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        return conn

    def status(self) -> dict[str, object]:
        with self.connect() as conn:
            counts = {}
            for table in ("files", "symbols", "edges"):
                counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            return {"database": str(self.db_path), "counts": counts}

    def status_json(self) -> str:
        return json.dumps(self.status(), indent=2, sort_keys=True)

    def known_files(self) -> dict[str, str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT path, sha256 FROM files").fetchall()
            return {row["path"]: row["sha256"] for row in rows}

    def clear_file(self, file_path: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))
            conn.execute(
                "DELETE FROM edges WHERE source_path = ? OR target_path = ?",
                (file_path, file_path),
            )
            conn.execute("DELETE FROM files WHERE path = ?", (file_path,))
            conn.commit()

    def upsert_file(self, path: str, sha256: str, language: str, updated_at: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO files(path, sha256, language, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    sha256=excluded.sha256,
                    language=excluded.language,
                    updated_at=excluded.updated_at
                """,
                (path, sha256, language, updated_at),
            )
            conn.commit()

    def insert_symbols(self, rows: Iterable[tuple[str, str, str, int, int]]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO symbols(file_path, name, kind, start_line, end_line)
                VALUES(?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()

    def insert_edges(self, rows: Iterable[tuple[str, str, str]]) -> None:
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO edges(source_path, target_path, edge_type)
                VALUES(?, ?, ?)
                """,
                rows,
            )
            conn.commit()

