"""Shared service contracts for the MCP server.

This module defines the stable interface that the MCP layer consumes.
The graph core can implement these protocols without exposing its internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


JsonDict = dict[str, Any]


@dataclass(slots=True)
class ToolRequestContext:
    """Common request metadata passed to backend operations.

    `root_path` is the workspace root that every backend call should treat as
    authoritative for indexing and graph reads.
    """

    root_path: Path
    workspace_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GraphOperationResult:
    """Generic response container used by backend implementations."""

    ok: bool
    summary: str
    data: JsonDict = field(default_factory=dict)


@runtime_checkable
class GraphBackend(Protocol):
    """Stable contract consumed by the MCP server."""

    def build_or_update_graph(self, context: ToolRequestContext, incremental: bool = True) -> GraphOperationResult:
        ...

    def get_build_status(self, job_id: str) -> GraphOperationResult:
        ...

    def cancel_build(self, job_id: str | None = None, root_path: Path | None = None) -> GraphOperationResult:
        ...

    def stop_web_server(self) -> GraphOperationResult:
        ...

    def autocomplete_entities(self, context: ToolRequestContext, prefix: str, limit: int = 20) -> GraphOperationResult:
        ...

    def get_neighbors(self, context: ToolRequestContext, targets: list[str], depth: int = 1) -> GraphOperationResult:
        ...

    def get_impact_radius(self, context: ToolRequestContext, targets: list[str], depth: int = 2) -> GraphOperationResult:
        ...

    def get_review_context(
        self,
        context: ToolRequestContext,
        targets: list[str],
        max_files: int = 10,
        max_tokens: int = 8000,
    ) -> GraphOperationResult:
        ...

    def query_graph(self, context: ToolRequestContext, query: str, limit: int = 20) -> GraphOperationResult:
        ...

    def semantic_search_nodes(self, context: ToolRequestContext, query: str, limit: int = 20) -> GraphOperationResult:
        ...

    def list_graph_stats(self, context: ToolRequestContext) -> GraphOperationResult:
        ...

    def find_files_by_pattern(self, context: ToolRequestContext, pattern: str, limit: int = 50) -> GraphOperationResult:
        ...

    def detect_changes(self, context: ToolRequestContext, base_ref: str, head_ref: str) -> GraphOperationResult:
        ...

    def find_paths(self, context: ToolRequestContext, source: str, sink: str, max_depth: int = 4) -> GraphOperationResult:
        ...

    def trace_dataflow(self, context: ToolRequestContext, source: str, sink: str, max_depth: int = 4) -> GraphOperationResult:
        ...

    def ask_graph(self, context: ToolRequestContext, question: str, limit: int = 8, depth: int = 2) -> GraphOperationResult:
        ...

    def audit_workspace(self, context: ToolRequestContext) -> GraphOperationResult:
        ...

    def list_communities(self, context: ToolRequestContext, min_size: int = 2) -> GraphOperationResult:
        ...

    def get_architecture_overview(self, context: ToolRequestContext) -> GraphOperationResult:
        ...

    def refactor_workspace(
        self,
        context: ToolRequestContext,
        large_symbol_threshold: int = 80,
    ) -> GraphOperationResult:
        ...

    def generate_wiki(
        self,
        context: ToolRequestContext,
        write_to_disk: bool = False,
    ) -> GraphOperationResult:
        ...


class MissingBackendError(RuntimeError):
    """Raised when the graph backend is not available."""


class UnavailableGraphBackend:
    """Fallback backend that keeps the MCP surface importable.

    The server remains usable as soon as the graph core provides a real backend.
    """

    def _fail(self, operation: str) -> GraphOperationResult:
        raise MissingBackendError(
            f"Graph backend is not configured. Cannot execute '{operation}'. "
            "Install the graph core implementation and pass a backend instance to create_server()."
        )

    def build_or_update_graph(self, context: ToolRequestContext, incremental: bool = True) -> GraphOperationResult:
        return self._fail("build_or_update_graph")

    def get_build_status(self, job_id: str) -> GraphOperationResult:
        return self._fail("get_build_status")

    def cancel_build(self, job_id: str | None = None, root_path: Path | None = None) -> GraphOperationResult:
        return self._fail("cancel_build")

    def stop_web_server(self) -> GraphOperationResult:
        return self._fail("stop_web_server")

    def autocomplete_entities(self, context: ToolRequestContext, prefix: str, limit: int = 20) -> GraphOperationResult:
        return self._fail("autocomplete_entities")

    def get_neighbors(self, context: ToolRequestContext, targets: list[str], depth: int = 1) -> GraphOperationResult:
        return self._fail("get_neighbors")

    def get_impact_radius(self, context: ToolRequestContext, targets: list[str], depth: int = 2) -> GraphOperationResult:
        return self._fail("get_impact_radius")

    def get_review_context(
        self,
        context: ToolRequestContext,
        targets: list[str],
        max_files: int = 10,
        max_tokens: int = 8000,
    ) -> GraphOperationResult:
        return self._fail("get_review_context")

    def query_graph(self, context: ToolRequestContext, query: str, limit: int = 20) -> GraphOperationResult:
        return self._fail("query_graph")

    def semantic_search_nodes(self, context: ToolRequestContext, query: str, limit: int = 20) -> GraphOperationResult:
        return self._fail("semantic_search_nodes")

    def list_graph_stats(self, context: ToolRequestContext) -> GraphOperationResult:
        return self._fail("list_graph_stats")

    def find_files_by_pattern(self, context: ToolRequestContext, pattern: str, limit: int = 50) -> GraphOperationResult:
        return self._fail("find_files_by_pattern")

    def detect_changes(self, context: ToolRequestContext, base_ref: str, head_ref: str) -> GraphOperationResult:
        return self._fail("detect_changes")

    def find_paths(self, context: ToolRequestContext, source: str, sink: str, max_depth: int = 4) -> GraphOperationResult:
        return self._fail("find_paths")

    def trace_dataflow(self, context: ToolRequestContext, source: str, sink: str, max_depth: int = 4) -> GraphOperationResult:
        return self._fail("trace_dataflow")

    def ask_graph(self, context: ToolRequestContext, question: str, limit: int = 8, depth: int = 2) -> GraphOperationResult:
        return self._fail("ask_graph")

    def audit_workspace(self, context: ToolRequestContext) -> GraphOperationResult:
        return self._fail("audit_workspace")

    def list_communities(self, context: ToolRequestContext, min_size: int = 2) -> GraphOperationResult:
        return self._fail("list_communities")

    def get_architecture_overview(self, context: ToolRequestContext) -> GraphOperationResult:
        return self._fail("get_architecture_overview")

    def refactor_workspace(
        self,
        context: ToolRequestContext,
        large_symbol_threshold: int = 80,
    ) -> GraphOperationResult:
        return self._fail("refactor_workspace")

    def generate_wiki(
        self,
        context: ToolRequestContext,
        write_to_disk: bool = False,
    ) -> GraphOperationResult:
        return self._fail("generate_wiki")

