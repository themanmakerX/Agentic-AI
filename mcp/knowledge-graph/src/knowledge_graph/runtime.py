from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def public_graph_root() -> Path:
    root = Path(".graph_db").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def root_slug(root_path: Path) -> str:
    resolved = Path(root_path).resolve()
    digest = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:10]
    name = resolved.name or "workspace"
    return f"{name}-{digest}"


def workspace_dir(root_path: Path) -> Path:
    target = public_graph_root() / "workspaces" / root_slug(root_path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def workspace_db_path(root_path: Path) -> Path:
    return workspace_dir(root_path) / "graph.sqlite3"


def workspace_manifest_path(root_path: Path) -> Path:
    return workspace_dir(root_path) / "manifest.json"


def jobs_dir() -> Path:
    target = public_graph_root() / "jobs"
    target.mkdir(parents=True, exist_ok=True)
    return target


def job_status_path(job_id: str) -> Path:
    return jobs_dir() / f"{job_id}.json"


def web_runtime_dir() -> Path:
    target = public_graph_root() / "web"
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, ensure_ascii=False)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent), suffix=".tmp") as handle:
        handle.write(data)
        temp_name = handle.name
    try:
        os.replace(temp_name, path)
    except PermissionError:
        path.write_text(data, encoding="utf-8")
        Path(temp_name).unlink(missing_ok=True)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
