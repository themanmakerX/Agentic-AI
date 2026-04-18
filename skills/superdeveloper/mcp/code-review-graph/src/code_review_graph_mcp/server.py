"""MCP server surface for code review graph operations."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .contracts import (
    GraphBackend,
    GraphOperationResult,
    ToolRequestContext,
    UnavailableGraphBackend,
)
from .backend import CodeReviewGraphBackend

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - importability fallback
    FastMCP = None  # type: ignore[assignment]


DEFAULT_SERVER_NAME = "code-review-graph"


def _normalize_root_path(root_path: str | Path | None) -> Path:
    return Path(root_path or Path.cwd()).resolve()


def _make_context(root_path: str | Path | None, workspace_path: str | Path | None = None) -> ToolRequestContext:
    return ToolRequestContext(
        root_path=_normalize_root_path(root_path),
        workspace_path=Path(workspace_path).resolve() if workspace_path else None,
    )


def _result_to_dict(result: GraphOperationResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "summary": result.summary,
        "data": result.data,
    }


def _build_server(backend: GraphBackend, name: str = DEFAULT_SERVER_NAME):
    if FastMCP is None:
        raise RuntimeError(
            "mcp is not installed. Install project dependencies before starting the server."
        )

    mcp = FastMCP(name)

    @mcp.tool()
    def build_or_update_graph(
        root_path: str | None = None,
        workspace_path: str | None = None,
        incremental: bool = True,
    ) -> dict[str, Any]:
        """Build or refresh the local graph for a workspace.

        Returns a structured result with `ok`, `summary`, and `data`.
        When `incremental` is true, the backend updates only changed files.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.build_or_update_graph(context=context, incremental=incremental))

    @mcp.tool()
    def get_impact_radius(
        targets: list[str],
        depth: int = 2,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Compute the dependency blast radius for the supplied targets.

        The response identifies the indexed files that are directly or indirectly
        affected by the provided file or symbol names.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.get_impact_radius(context=context, targets=targets, depth=depth))

    @mcp.tool()
    def get_review_context(
        targets: list[str],
        max_files: int = 10,
        max_tokens: int = 8000,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Return a review-ready subset of the indexed repository.

        The backend selects the minimal relevant file set derived from the
        impact radius and caps the result using `max_files` and `max_tokens`.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(
            backend.get_review_context(
                context=context,
                targets=targets,
                max_files=max_files,
                max_tokens=max_tokens,
            )
        )

    @mcp.tool()
    def query_graph(
        query: str,
        limit: int = 20,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Run a structural lookup over indexed files, symbols, and edges.

        Results are returned in ranked order so assistants can inspect the most
        relevant structural matches first.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.query_graph(context=context, query=query, limit=limit))

    @mcp.tool()
    def semantic_search_nodes(
        query: str,
        limit: int = 20,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Search graph nodes using hybrid semantic ranking.

        The backend uses embeddings when available and falls back to
        token-overlap ranking when no embedding model can be loaded.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.semantic_search_nodes(context=context, query=query, limit=limit))

    @mcp.tool()
    def list_graph_stats(
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Return repository indexing statistics and health metrics."""

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.list_graph_stats(context=context))

    @mcp.tool()
    def find_files_by_pattern(
        pattern: str,
        limit: int = 50,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Find indexed files by path, module name, or symbol-aware pattern."""

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.find_files_by_pattern(context=context, pattern=pattern, limit=limit))

    @mcp.tool()
    def detect_changes(
        base_ref: str,
        head_ref: str,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Compare two Git refs and summarize the changed file set."""

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.detect_changes(context=context, base_ref=base_ref, head_ref=head_ref))

    @mcp.tool()
    def trace_dataflow(
        source: str,
        sink: str,
        max_depth: int = 4,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Trace the shortest known structural path between source and sink.

        The backend returns an exact indexed path when available, otherwise a
        best-effort exploration result with an explanation.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(
            backend.trace_dataflow(context=context, source=source, sink=sink, max_depth=max_depth)
        )

    @mcp.tool()
    def audit_workspace(
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Return a workspace health report for the current graph state.

        The audit includes coverage, language distribution, unresolved import
        edges, diagnostics, and other indexing health signals.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.audit_workspace(context=context))

    @mcp.tool()
    def list_communities(
        min_size: int = 2,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """List connected-code communities discovered in the graph.

        Communities are derived from the current structural graph and are useful
        for understanding module clusters, ownership hotspots, and architecture
        boundaries.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.list_communities(context=context, min_size=min_size))

    @mcp.tool()
    def get_architecture_overview(
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Return a compact architecture summary of the indexed repository.

        The overview combines community counts, language distribution, and hub
        files so the assistant can quickly orient itself in the codebase.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.get_architecture_overview(context=context))

    @mcp.tool()
    def refactor_workspace(
        large_symbol_threshold: int = 80,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Return heuristic refactor suggestions for the indexed workspace.

        The backend highlights large symbols, possible dead code, and rename
        candidates so reviewers can focus on maintainability risks.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(
            backend.refactor_workspace(context=context, large_symbol_threshold=large_symbol_threshold)
        )

    @mcp.tool()
    def generate_wiki(
        write_to_disk: bool = False,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Generate a lightweight Markdown wiki from the current graph.

        The returned payload includes page contents. When `write_to_disk` is
        true, the wiki is also written under `.code-review-graph/wiki`.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.generate_wiki(context=context, write_to_disk=write_to_disk))

    return mcp


def create_server(
    backend: GraphBackend | None = None,
    *,
    root_path: str | Path | None = None,
    db_path: str | Path | None = None,
    name: str = DEFAULT_SERVER_NAME,
):
    """Create a configured MCP server instance.

    If `root_path` is provided without `db_path`, the server defaults the
    database to `<root>/.code-review-graph/graph.sqlite3`.
    The backend is injected from the graph core package or a test double.
    """

    if root_path is not None and db_path is None:
        root = Path(root_path).resolve()
        db_path = root / ".code-review-graph" / "graph.sqlite3"
    if backend is None and root_path is not None and db_path is not None:
        backend = CodeReviewGraphBackend(root_path=Path(root_path), db_path=Path(db_path))
    return _build_server(backend or UnavailableGraphBackend(), name=name)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the code review graph MCP server.")
    parser.add_argument("--root", dest="root_path", default=None, help="Workspace root path.")
    parser.add_argument("--db", dest="db_path", default=None, help="SQLite database path.")
    parser.add_argument("--name", default=DEFAULT_SERVER_NAME, help="MCP server name.")
    args = parser.parse_args(argv)

    server = create_server(root_path=args.root_path, db_path=args.db_path, name=args.name)

    # FastMCP provides its own runner; the workspace root is handled by the tool calls.
    # The graph backend should be injected by the graph core layer before production use.
    if hasattr(server, "run"):
        server.run()
    else:  # pragma: no cover - defensive fallback
        raise RuntimeError("FastMCP server object does not expose run().")
