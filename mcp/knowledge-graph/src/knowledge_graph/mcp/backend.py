"""Backend implementation for the MCP server."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from knowledge_graph.backend import create_service
from knowledge_graph.jobs import default_build_manager
from knowledge_graph.runtime import workspace_db_path
from knowledge_graph.web import build_web_links, default_web_server

from .contracts import GraphBackend, GraphOperationResult, ToolRequestContext


class KnowledgeGraphBackend(GraphBackend):
    def __init__(self, *, root_path: Path, db_path: Path) -> None:
        self.root_path = Path(root_path).resolve()
        self.db_path = Path(db_path).resolve()

    def _service(self):
        return create_service(self.root_path, self.db_path)

    def _service_for_context(self, context: ToolRequestContext):
        root_path = Path(context.root_path).resolve()
        if root_path == self.root_path:
            db_path = self.db_path
        else:
            db_path = workspace_db_path(root_path)
        return create_service(root_path, db_path)

    def _ok(self, summary: str, data: dict[str, Any]) -> GraphOperationResult:
        return GraphOperationResult(ok=True, summary=summary, data=data)

    def build_or_update_graph(self, context: ToolRequestContext, incremental: bool = True) -> GraphOperationResult:
        manager = default_build_manager()
        status = manager.start(context.root_path, incremental=incremental)
        status.update(build_web_links(context.root_path, job_id=str(status["job_id"])))
        return self._ok("Graph build scheduled", status)

    def get_build_status(self, job_id: str) -> GraphOperationResult:
        status = default_build_manager().get(job_id)
        if status is None:
            return GraphOperationResult(ok=False, summary="Build job not found", data={"job_id": job_id})
        status.update(build_web_links(Path(status["root_path"]), job_id=job_id))
        return self._ok("Build status fetched", status)

    def cancel_build(self, job_id: str | None = None, root_path: Path | None = None) -> GraphOperationResult:
        status = default_build_manager().cancel(job_id=job_id, root_path=root_path)
        if status is None:
            return GraphOperationResult(ok=False, summary="Build job not found", data={"job_id": job_id, "root_path": str(root_path) if root_path else None})
        status.update(build_web_links(Path(status["root_path"]), job_id=str(status["job_id"])))
        return self._ok("Build cancellation requested", status)

    def stop_web_server(self) -> GraphOperationResult:
        stopped = default_web_server().stop()
        return self._ok("Web server stopped" if stopped else "Web server was not running", {"stopped": stopped})

    def autocomplete_entities(self, context: ToolRequestContext, prefix: str, limit: int = 20) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok("Autocomplete results collected", service.autocomplete_entities(prefix=prefix, limit=limit))

    def get_neighbors(self, context: ToolRequestContext, targets: list[str], depth: int = 1) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok("Neighbors collected", service.get_neighbors(targets=targets, depth=depth))

    def get_impact_radius(self, context: ToolRequestContext, targets: list[str], depth: int = 2) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok("Impact radius calculated", service.impact_radius(targets=targets, depth=depth))

    def get_review_context(
        self,
        context: ToolRequestContext,
        targets: list[str],
        max_files: int = 10,
        max_tokens: int = 8000,
    ) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok(
            "Review context generated",
            service.review_context(targets=targets, max_files=max_files, max_tokens=max_tokens),
        )

    def query_graph(self, context: ToolRequestContext, query: str, limit: int = 20) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok("Graph query executed", service.query(query=query, limit=limit))

    def semantic_search_nodes(self, context: ToolRequestContext, query: str, limit: int = 20) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok("Semantic search executed", service.semantic_search(query=query, limit=limit))

    def list_graph_stats(self, context: ToolRequestContext) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok("Graph stats collected", service.stats())

    def find_files_by_pattern(self, context: ToolRequestContext, pattern: str, limit: int = 50) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok("Files matched", service.find_files_by_pattern(pattern=pattern, limit=limit))

    def detect_changes(self, context: ToolRequestContext, base_ref: str, head_ref: str) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok("Changes detected", service.detect_changes(base_ref=base_ref, head_ref=head_ref))

    def find_paths(self, context: ToolRequestContext, source: str, sink: str, max_depth: int = 4) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok("Paths found", service.find_paths(source=source, sink=sink, max_depth=max_depth))

    def trace_dataflow(self, context: ToolRequestContext, source: str, sink: str, max_depth: int = 4) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok("Dataflow traced", service.trace_dataflow(source=source, sink=sink, max_depth=max_depth))

    def ask_graph(self, context: ToolRequestContext, question: str, limit: int = 8, depth: int = 2) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok("Graph answer generated", service.ask_graph(question=question, limit=limit, depth=depth))

    def audit_workspace(self, context: ToolRequestContext) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok("Workspace audited", service.audit_workspace())

    def list_communities(self, context: ToolRequestContext, min_size: int = 2) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok("Communities listed", service.list_communities(min_size=min_size))

    def get_architecture_overview(self, context: ToolRequestContext) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok("Architecture overview generated", service.get_architecture_overview())

    def refactor_workspace(
        self,
        context: ToolRequestContext,
        large_symbol_threshold: int = 80,
    ) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok(
            "Refactor suggestions generated",
            service.refactor_workspace(large_symbol_threshold=large_symbol_threshold),
        )

    def generate_wiki(
        self,
        context: ToolRequestContext,
        write_to_disk: bool = False,
    ) -> GraphOperationResult:
        service = self._service_for_context(context)
        return self._ok("Wiki generated", service.generate_wiki(write_to_disk=write_to_disk))
CodeReviewGraphBackend = KnowledgeGraphBackend

