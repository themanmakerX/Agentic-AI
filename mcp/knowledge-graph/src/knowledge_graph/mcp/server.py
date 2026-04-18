"""MCP server surface for knowledge graph operations."""

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
from .backend import KnowledgeGraphBackend

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - importability fallback
    FastMCP = None  # type: ignore[assignment]


DEFAULT_SERVER_NAME = "knowledge-graph"


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
        """Build or refresh the graph for one workspace root.

        `root_path` is the authoritative workspace location. If omitted, the
        current working directory is used. `workspace_path` is accepted for
        compatibility but should usually be left unset.

        Use `incremental=true` for normal refreshes and `false` for a full
        rebuild. The tool returns immediately with a `job_id` and persists
        progress under `.graph_db/jobs/<job_id>.json` while indexing continues
        in the background.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.build_or_update_graph(context=context, incremental=incremental))

    @mcp.tool()
    def get_build_status(job_id: str) -> dict[str, Any]:
        """Return the latest background build status for one job id."""

        return _result_to_dict(backend.get_build_status(job_id=job_id))

    @mcp.tool()
    def cancel_build(job_id: str | None = None, root_path: str | None = None) -> dict[str, Any]:
        """Cancel one running or queued build by job id or workspace root."""

        resolved_root = _normalize_root_path(root_path) if root_path is not None else None
        return _result_to_dict(backend.cancel_build(job_id=job_id, root_path=resolved_root))

    @mcp.tool()
    def stop_web_server() -> dict[str, Any]:
        """Stop the background web server explicitly."""

        return _result_to_dict(backend.stop_web_server())

    @mcp.tool()
    def autocomplete_entities(
        prefix: str,
        limit: int = 20,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Return files and symbols that match a prefix or partial query.

        This is the lightweight entity picker used by the web UI. It is
        optimized for autocomplete-style search over file paths, module names,
        and symbol names.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.autocomplete_entities(context=context, prefix=prefix, limit=limit))

    @mcp.tool()
    def get_neighbors(
        targets: list[str],
        depth: int = 1,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Return the immediate neighborhood around one or more targets.

        This is the graph-browsing primitive that makes the UI feel connected:
        it returns the seed files plus nearby files and edges within `depth`
        hops, so callers can drill into a focused subgraph instead of the full
        repository.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.get_neighbors(context=context, targets=targets, depth=depth))

    @mcp.tool()
    def get_impact_radius(
        targets: list[str],
        depth: int = 2,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Compute the dependency blast radius for indexed files or symbols.

        `targets` should contain file paths, module names, or symbol names that
        already exist in the current graph. `depth` controls how many dependency
        hops are explored outward from the seed set.
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
        """Return a compact, review-ready subset of the indexed repository.

        The backend expands the dependency radius around `targets`, then caps
        the output using `max_files` and `max_tokens` so the caller can stay
        within token budget while still getting the most relevant files.
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

        Use this for exact or partial name lookups. Results are token-ranked and
        include the matched row type plus the resolved file path when available.
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
        """Search graph nodes using semantic or lexical ranking.

        The backend uses embeddings when available and falls back to
        token-overlap ranking when no embedding model can be loaded. This is
        the right tool for concept-level search, not exact path matching.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.semantic_search_nodes(context=context, query=query, limit=limit))

    @mcp.tool()
    def list_graph_stats(
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Return repository indexing statistics and health metrics.

        Use this when you only need a quick sanity check on file, symbol, edge,
        and diagnostics counts.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.list_graph_stats(context=context))

    @mcp.tool()
    def find_files_by_pattern(
        pattern: str,
        limit: int = 50,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Find indexed files by path or module-name substring.

        This is the cheapest way to locate file-level matches before asking for
        richer structural context.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.find_files_by_pattern(context=context, pattern=pattern, limit=limit))

    @mcp.tool()
    def detect_changes(
        base_ref: str,
        head_ref: str,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Compare two Git refs and summarize the changed file set.

        Useful for review workflows where you need the graph-aware blast radius
        of a branch diff rather than a raw Git patch.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.detect_changes(context=context, base_ref=base_ref, head_ref=head_ref))

    @mcp.tool()
    def find_paths(
        source: str,
        sink: str,
        max_depth: int = 4,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Find the path between two indexed files or symbols.

        This is a direct path-discovery primitive for review workflows and
        mirrors the shortest-path style exploration used by graph browsers.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.find_paths(context=context, source=source, sink=sink, max_depth=max_depth))

    @mcp.tool()
    def trace_dataflow(
        source: str,
        sink: str,
        max_depth: int = 4,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Trace the shortest known structural path between source and sink.

        Use this when you need an exact dependency chain from one symbol/file to
        another. If no path exists within `max_depth`, the tool returns the best
        explored approximation and an explanation.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(
            backend.trace_dataflow(context=context, source=source, sink=sink, max_depth=max_depth)
        )

    @mcp.tool()
    def ask_graph(
        question: str,
        limit: int = 8,
        depth: int = 2,
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Return a retrieval-backed answer packet for a graph question.

        This is the MCP equivalent of GraphRAG-style chat: it retrieves the
        most relevant files, expands the local neighborhood, and returns a
        concise answer plus the evidence used to derive it.
        """

        context = _make_context(root_path, workspace_path)
        return _result_to_dict(backend.ask_graph(context=context, question=question, limit=limit, depth=depth))

    @mcp.tool()
    def audit_workspace(
        root_path: str | None = None,
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Return a workspace health report for the current graph state.

        This is the main integrity check: it reports coverage, language mix,
        unresolved imports, diagnostics, and other indexing health signals.
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

        Communities are connected components in the current structural graph and
        are useful for understanding module clusters, ownership hotspots, and
        architecture boundaries.
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
        files so the assistant can quickly orient itself in the codebase before
        diving into lower-level queries.
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
        true, the wiki is written under `.graph_db/wiki/<workspace>`.
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
    database to `<root>/.graph_db/graph.sqlite3`.
    The backend is injected from the graph core package or a test double.
    """

    if root_path is not None and db_path is None:
        root = Path(root_path).resolve()
        db_path = root / ".graph_db" / "graph.sqlite3"
    if backend is None and root_path is not None and db_path is not None:
        backend = KnowledgeGraphBackend(root_path=Path(root_path), db_path=Path(db_path))
    return _build_server(backend or UnavailableGraphBackend(), name=name)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the knowledge graph MCP server.")
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



