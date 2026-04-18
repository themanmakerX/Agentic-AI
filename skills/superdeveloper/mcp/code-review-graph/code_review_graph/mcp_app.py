"""MCP application and tool definitions."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .graph.builder import build_graph, update_graph
from .graph.query import (
    get_graph_stats,
    get_impact_radius,
    get_review_context,
    query_graph,
)
from .graph.storage import GraphStore


def create_mcp_app(root: Path, db_path: Path) -> FastMCP:
    mcp = FastMCP("code-review-graph")

    @mcp.tool()
    def build_or_update_graph() -> dict:
        summary = update_graph(root, db_path)
        return summary.as_dict()

    @mcp.tool()
    def get_impact_radius(changed_paths: list[str]) -> dict:
        store = GraphStore(db_path)
        return get_impact_radius(store, changed_paths).as_dict()

    @mcp.tool()
    def get_review_context(target_paths: list[str]) -> dict:
        store = GraphStore(db_path)
        return get_review_context(store, target_paths).as_dict()

    @mcp.tool()
    def query_graph(name: str) -> dict:
        store = GraphStore(db_path)
        return query_graph(store, name)

    @mcp.tool()
    def list_graph_stats() -> dict:
        store = GraphStore(db_path)
        return get_graph_stats(store)

    @mcp.tool()
    def build_graph_tool() -> dict:
        summary = build_graph(root, db_path)
        return summary.as_dict()

    return mcp

