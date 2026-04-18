from __future__ import annotations

from pathlib import Path

from ..storage import SQLiteGraphStore


class GraphStore(SQLiteGraphStore):
    def status(self) -> dict[str, dict[str, int]]:
        return {"counts": self.stats()}


def open_graph_store(db_path: Path) -> GraphStore:
    return GraphStore(db_path)


