"""Backend implementation for the MCP server."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from code_review_graph.backend import create_service

from .contracts import GraphBackend, GraphOperationResult, ToolRequestContext


class CodeReviewGraphBackend(GraphBackend):
    def __init__(self, *, root_path: Path, db_path: Path) -> None:
        self.root_path = Path(root_path).resolve()
        self.db_path = Path(db_path).resolve()

    def _service(self):
        return create_service(self.root_path, self.db_path)

    def _ok(self, summary: str, data: dict[str, Any]) -> GraphOperationResult:
        return GraphOperationResult(ok=True, summary=summary, data=data)

    def build_or_update_graph(self, context: ToolRequestContext, incremental: bool = True) -> GraphOperationResult:
        service = self._service()
        summary = service.update() if incremental else service.build()
        return self._ok("Graph built" if not incremental else "Graph updated", asdict(summary))

    def get_impact_radius(self, context: ToolRequestContext, targets: list[str], depth: int = 2) -> GraphOperationResult:
        service = self._service()
        return self._ok("Impact radius calculated", service.impact_radius(targets=targets, depth=depth))

    def get_review_context(
        self,
        context: ToolRequestContext,
        targets: list[str],
        max_files: int = 10,
        max_tokens: int = 8000,
    ) -> GraphOperationResult:
        service = self._service()
        return self._ok(
            "Review context generated",
            service.review_context(targets=targets, max_files=max_files, max_tokens=max_tokens),
        )

    def query_graph(self, context: ToolRequestContext, query: str, limit: int = 20) -> GraphOperationResult:
        service = self._service()
        return self._ok("Graph query executed", service.query(query=query, limit=limit))

    def semantic_search_nodes(self, context: ToolRequestContext, query: str, limit: int = 20) -> GraphOperationResult:
        service = self._service()
        return self._ok("Semantic search executed", service.semantic_search(query=query, limit=limit))

    def list_graph_stats(self, context: ToolRequestContext) -> GraphOperationResult:
        service = self._service()
        return self._ok("Graph stats collected", service.stats())

    def find_files_by_pattern(self, context: ToolRequestContext, pattern: str, limit: int = 50) -> GraphOperationResult:
        service = self._service()
        return self._ok("Files matched", service.find_files_by_pattern(pattern=pattern, limit=limit))

    def detect_changes(self, context: ToolRequestContext, base_ref: str, head_ref: str) -> GraphOperationResult:
        service = self._service()
        return self._ok("Changes detected", service.detect_changes(base_ref=base_ref, head_ref=head_ref))

    def trace_dataflow(self, context: ToolRequestContext, source: str, sink: str, max_depth: int = 4) -> GraphOperationResult:
        service = self._service()
        return self._ok("Dataflow traced", service.trace_dataflow(source=source, sink=sink, max_depth=max_depth))

    def audit_workspace(self, context: ToolRequestContext) -> GraphOperationResult:
        service = self._service()
        return self._ok("Workspace audited", service.audit_workspace())

    def list_communities(self, context: ToolRequestContext, min_size: int = 2) -> GraphOperationResult:
        service = self._service()
        return self._ok("Communities listed", service.list_communities(min_size=min_size))

    def get_architecture_overview(self, context: ToolRequestContext) -> GraphOperationResult:
        service = self._service()
        return self._ok("Architecture overview generated", service.get_architecture_overview())

    def refactor_workspace(
        self,
        context: ToolRequestContext,
        large_symbol_threshold: int = 80,
    ) -> GraphOperationResult:
        service = self._service()
        return self._ok(
            "Refactor suggestions generated",
            service.refactor_workspace(large_symbol_threshold=large_symbol_threshold),
        )

    def generate_wiki(
        self,
        context: ToolRequestContext,
        write_to_disk: bool = False,
    ) -> GraphOperationResult:
        service = self._service()
        return self._ok("Wiki generated", service.generate_wiki(write_to_disk=write_to_disk))
