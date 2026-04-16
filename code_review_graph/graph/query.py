"""Graph query helpers."""

from __future__ import annotations

from dataclasses import asdict

from .models import ImpactResult, ReviewContext
from .storage import GraphStore


def get_graph_stats(store: GraphStore) -> dict[str, object]:
    return store.status()


def get_impact_radius(store: GraphStore, changed_paths: list[str]) -> ImpactResult:
    with store.connect() as conn:
        impacted = []
        for path in changed_paths:
            rows = conn.execute(
                "SELECT DISTINCT target_path FROM edges WHERE source_path = ? OR target_path = ?",
                (path, path),
            ).fetchall()
            impacted.extend(row["target_path"] for row in rows)
    impacted_paths = sorted(set(impacted) - set(changed_paths))
    tests = [path for path in impacted_paths if "/test" in path or path.endswith("_test.py") or path.startswith("test_")]
    return ImpactResult(
        changed_paths=changed_paths,
        impacted_paths=impacted_paths,
        tests=tests,
        confidence=0.5 if impacted_paths else 1.0,
    )


def get_review_context(store: GraphStore, target_paths: list[str]) -> ReviewContext:
    impact = get_impact_radius(store, target_paths)
    relevant = sorted(set(target_paths) | set(impact.impacted_paths) | set(impact.tests))
    summary = "Relevant files were selected from the local dependency graph."
    return ReviewContext(target_paths=target_paths, relevant_paths=relevant, summary=summary)


def query_graph(store: GraphStore, name: str) -> dict[str, object]:
    with store.connect() as conn:
        symbol_rows = conn.execute(
            "SELECT file_path, name, kind, start_line, end_line FROM symbols WHERE name LIKE ?",
            (f"%{name}%",),
        ).fetchall()
        edge_rows = conn.execute(
            "SELECT source_path, target_path, edge_type FROM edges WHERE source_path LIKE ? OR target_path LIKE ?",
            (f"%{name}%", f"%{name}%"),
        ).fetchall()
    return {
        "symbols": [dict(row) for row in symbol_rows],
        "edges": [dict(row) for row in edge_rows],
    }

