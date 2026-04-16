from __future__ import annotations

from pathlib import Path
from typing import Any

from ..backend import create_service


def get_graph_stats(db_path: Path) -> dict[str, Any]:
    service = create_service(Path.cwd(), db_path)
    return service.stats()

