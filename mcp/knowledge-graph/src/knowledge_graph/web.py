from __future__ import annotations

from pathlib import Path
import socket
import threading
import time
from typing import Any
from urllib.parse import quote_plus

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .backend import create_service
from .jobs import default_build_manager
from .payloads import build_file_details, build_graph_view, load_graph_payload
from .runtime import workspace_db_path, workspace_manifest_path


APP_ROOT = Path(__file__).resolve().parents[2] / "app"


class WebServerManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._server = None
        self._host = "127.0.0.1"
        self._port: int | None = None

    def ensure_started(self, host: str = "127.0.0.1", port: int = 5000) -> tuple[str, int]:
        with self._lock:
            if self._thread is not None and self._thread.is_alive() and self._port is not None:
                return self._host, self._port
            actual_port = _pick_port(host, preferred_port=port)
            self._host = host
            self._port = actual_port
            self._thread = threading.Thread(target=self._run_server, args=(host, actual_port), daemon=True)
            self._thread.start()
        _wait_for_port(host, actual_port)
        return host, actual_port

    def stop(self) -> bool:
        with self._lock:
            server = self._server
            thread = self._thread
            if server is None or thread is None or not thread.is_alive():
                return False
            server.should_exit = True
        thread.join(timeout=5.0)
        with self._lock:
            self._server = None
            self._thread = None
            self._port = None
        return True

    def _run_server(self, host: str, port: int) -> None:
        import uvicorn
        config = uvicorn.Config(create_app(), host=host, port=port, log_level="warning")
        server = uvicorn.Server(config)
        with self._lock:
            self._server = server
        server.run()
        with self._lock:
            self._server = None


def _pick_port(host: str, preferred_port: int) -> int:
    if not _can_connect(host, preferred_port):
        return preferred_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])


def _can_connect(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        return probe.connect_ex((host, port)) == 0


def _wait_for_port(host: str, port: int, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _can_connect(host, port):
            return
        time.sleep(0.1)
    raise RuntimeError(f"Web server failed to start on {host}:{port}")


def build_web_links(root_path: Path, *, job_id: str | None = None, host: str = "127.0.0.1", port: int = 5000) -> dict[str, str]:
    actual_host, actual_port = default_web_server().ensure_started(host=host, port=port)
    resolved_root = str(Path(root_path).resolve())
    encoded_root = quote_plus(resolved_root)
    root_query = f"root_path={encoded_root}"
    if job_id:
        root_query += f"&job_id={job_id}"
    base_url = f"http://{actual_host}:{actual_port}"
    return {
        "web_base_url": base_url,
        "web_url": f"{base_url}/?{root_query}",
        "api_url": f"{base_url}/api/repo_info?root_path={encoded_root}",
        "build_status_url": f"{base_url}/api/builds/{job_id}" if job_id else "",
    }


_DEFAULT_WEB_SERVER = WebServerManager()


def default_web_server() -> WebServerManager:
    return _DEFAULT_WEB_SERVER


def _resolve_root(root_path: str | None) -> Path:
    return Path(root_path or Path.cwd()).resolve()


def _load_payload(root_path: Path) -> dict[str, Any]:
    db_path = workspace_db_path(root_path)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Graph database not found. Build the graph first.")
    return load_graph_payload(root_path, db_path)


def create_app() -> FastAPI:
    app = FastAPI(title="knowledge-graph")

    if APP_ROOT.exists():
        app.mount("/assets", StaticFiles(directory=APP_ROOT), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(APP_ROOT / "index.html")

    @app.post("/api/build")
    def build_graph(payload: dict[str, Any]) -> dict[str, Any]:
        root_path = _resolve_root(payload.get("root_path"))
        incremental = bool(payload.get("incremental", True))
        return default_build_manager().start(root_path, incremental=incremental)

    @app.get("/api/builds/{job_id}")
    def build_status(job_id: str) -> dict[str, Any]:
        status = default_build_manager().get(job_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Build job not found")
        return status

    @app.get("/api/repo_info")
    def repo_info(root_path: str | None = Query(default=None)) -> dict[str, Any]:
        root = _resolve_root(root_path)
        payload = _load_payload(root)
        manifest_path = workspace_manifest_path(root)
        return {
            "root_path": payload["root_path"],
            "counts": payload["counts"],
            "stats": payload["stats"],
            "top_hubs": payload["top_hubs"][:10],
            "manifest_path": str(manifest_path),
            "db_path": payload["db_path"],
            "generated_at": payload["generated_at"],
        }

    @app.get("/api/graph_entities")
    def graph_entities(
        root_path: str | None = Query(default=None),
        target: str | None = Query(default=None),
        depth: int = Query(default=1, ge=0, le=4),
        limit: int = Query(default=300, ge=10, le=2000),
    ) -> dict[str, Any]:
        root = _resolve_root(root_path)
        payload = _load_payload(root)
        return {
            "root_path": payload["root_path"],
            "counts": payload["counts"],
            "graph": build_graph_view(payload, target=target, depth=depth, limit=limit),
        }

    @app.get("/api/file_details")
    def file_details(root_path: str | None = Query(default=None), file_path: str = Query(...)) -> dict[str, Any]:
        root = _resolve_root(root_path)
        payload = _load_payload(root)
        details = build_file_details(payload, file_path=file_path)
        if details is None:
            raise HTTPException(status_code=404, detail="File not found in graph")
        return details

    @app.post("/api/get_neighbors")
    def get_neighbors(payload: dict[str, Any]) -> dict[str, Any]:
        root = _resolve_root(payload.get("root_path"))
        service = create_service(root, workspace_db_path(root))
        return service.get_neighbors(targets=list(payload.get("targets", [])), depth=int(payload.get("depth", 1)))

    @app.post("/api/auto_complete")
    def auto_complete(payload: dict[str, Any]) -> dict[str, Any]:
        root = _resolve_root(payload.get("root_path"))
        service = create_service(root, workspace_db_path(root))
        return service.autocomplete_entities(prefix=str(payload.get("prefix", "")), limit=int(payload.get("limit", 20)))

    @app.post("/api/find_paths")
    def find_paths(payload: dict[str, Any]) -> dict[str, Any]:
        root = _resolve_root(payload.get("root_path"))
        service = create_service(root, workspace_db_path(root))
        return service.find_paths(
            source=str(payload.get("source", "")),
            sink=str(payload.get("sink", "")),
            max_depth=int(payload.get("max_depth", 4)),
        )

    @app.post("/api/chat")
    def ask_graph(payload: dict[str, Any]) -> dict[str, Any]:
        root = _resolve_root(payload.get("root_path"))
        service = create_service(root, workspace_db_path(root))
        return service.ask_graph(
            question=str(payload.get("question", "")),
            limit=int(payload.get("limit", 8)),
            depth=int(payload.get("depth", 2)),
        )

    return app


def run(host: str = "127.0.0.1", port: int = 5000) -> int:
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port)
    return 0
