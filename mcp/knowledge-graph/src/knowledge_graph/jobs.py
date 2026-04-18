from __future__ import annotations

from datetime import datetime
import threading
import uuid
from pathlib import Path
from typing import Any

from .backend import create_service
from .runtime import job_status_path, workspace_db_path, workspace_manifest_path, write_json


class BuildJobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._active_by_root: dict[str, str] = {}
        self._cancelled: set[str] = set()

    def start(self, root_path: Path, incremental: bool = True) -> dict[str, Any]:
        root_path = Path(root_path).resolve()
        root_key = str(root_path)
        with self._lock:
            active_job_id = self._active_by_root.get(root_key)
            if active_job_id:
                current = self._jobs.get(active_job_id)
                if current and current.get("state") in {"queued", "running"}:
                    return dict(current)

            job_id = uuid.uuid4().hex[:12]
            status = {
                "job_id": job_id,
                "root_path": root_key,
                "db_path": str(workspace_db_path(root_path)),
                "state": "queued",
                "message": "Build queued",
                "incremental": incremental,
                "current": 0,
                "total": 0,
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "finished_at": None,
            }
            self._jobs[job_id] = status
            self._active_by_root[root_key] = job_id
            self._write_status(status)

        thread = threading.Thread(target=self._worker, args=(job_id,), daemon=True)
        thread.start()
        return dict(status)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            current = self._jobs.get(job_id)
        if current is not None:
            return dict(current)
        path = job_status_path(job_id)
        if not path.exists():
            return None
        import json

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def cancel(self, *, job_id: str | None = None, root_path: Path | None = None) -> dict[str, Any] | None:
        resolved_job_id = job_id
        if resolved_job_id is None and root_path is not None:
            resolved_job_id = self._active_by_root.get(str(Path(root_path).resolve()))
        if resolved_job_id is None:
            return None
        with self._lock:
            current = self._jobs.get(resolved_job_id)
            if current is None:
                return None
            self._cancelled.add(resolved_job_id)
            current = dict(current)
            current["cancel_requested"] = True
            if current.get("state") == "queued":
                current["state"] = "cancelled"
                current["message"] = "Build cancelled before start"
                current["finished_at"] = datetime.now().isoformat(timespec="seconds")
            self._jobs[resolved_job_id] = current
        self._write_status(current)
        return dict(current)

    def _worker(self, job_id: str) -> None:
        status = self._jobs[job_id]
        root_path = Path(status["root_path"])
        service = create_service(root_path, workspace_db_path(root_path))
        if job_id in self._cancelled:
            self._update(
                job_id,
                state="cancelled",
                message="Build cancelled before start",
                finished_at=datetime.now().isoformat(timespec="seconds"),
            )
            return
        self._update(job_id, state="running", message="Indexing started")

        def progress_callback(payload: dict[str, Any]) -> None:
            if job_id in self._cancelled:
                raise RuntimeError("Build cancelled by user")
            self._update(
                job_id,
                state=str(payload.get("stage", "running")),
                message=str(payload.get("message", "")),
                current=int(payload.get("current", 0) or 0),
                total=int(payload.get("total", 0) or 0),
                path=payload.get("path"),
                language_id=payload.get("language_id"),
            )

        try:
            summary = service.update(progress_callback=progress_callback) if status["incremental"] else service.build(progress_callback=progress_callback)
            final_stats = service.stats()
            manifest = {
                "root_path": str(root_path),
                "db_path": str(workspace_db_path(root_path)),
                "stats": final_stats,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            write_json(workspace_manifest_path(root_path), manifest)
            total = summary.files_changed if status["incremental"] else summary.files_scanned
            self._update(
                job_id,
                state="done",
                message="Build completed",
                current=total,
                total=total,
                stats=final_stats,
                finished_at=datetime.now().isoformat(timespec="seconds"),
            )
        except Exception as exc:
            state = "cancelled" if job_id in self._cancelled else "error"
            message = "Build cancelled by user" if state == "cancelled" else f"Build failed: {exc}"
            self._update(
                job_id,
                state=state,
                message=message,
                error=str(exc),
                finished_at=datetime.now().isoformat(timespec="seconds"),
            )
        finally:
            with self._lock:
                if self._active_by_root.get(str(root_path)) == job_id:
                    self._active_by_root.pop(str(root_path), None)
                self._cancelled.discard(job_id)

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            current = dict(self._jobs[job_id])
            current.update(changes)
            self._jobs[job_id] = current
        self._write_status(current)

    @staticmethod
    def _write_status(status: dict[str, Any]) -> None:
        write_json(job_status_path(str(status["job_id"])), status)


_DEFAULT_MANAGER = BuildJobManager()


def default_build_manager() -> BuildJobManager:
    return _DEFAULT_MANAGER
