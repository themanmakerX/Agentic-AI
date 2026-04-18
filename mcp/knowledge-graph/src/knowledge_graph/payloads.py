from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any

from .storage import SQLiteGraphStore


def _connected_components(files: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[list[str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for row in files:
        adjacency.setdefault(str(row["id"]), set())
    for edge in edges:
        source = edge.get("source_file_id")
        target = edge.get("target_file_id")
        if source is None or target is None:
            continue
        source_id = str(source)
        target_id = str(target)
        adjacency.setdefault(source_id, set()).add(target_id)
        adjacency.setdefault(target_id, set()).add(source_id)

    seen: set[str] = set()
    components: list[list[str]] = []
    for start in adjacency:
        if start in seen:
            continue
        queue: deque[str] = deque([start])
        component: list[str] = []
        seen.add(start)
        while queue:
            node = queue.popleft()
            component.append(node)
            for neighbor in adjacency.get(node, set()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append(sorted(component))
    components.sort(key=lambda component: (-len(component), component[0] if component else ""))
    return components


def load_graph_payload(root_path: Path, db_path: Path) -> dict[str, Any]:
    root_path = Path(root_path).resolve()
    db_path = Path(db_path).resolve()
    with SQLiteGraphStore(db_path) as store:
        files = store.fetch_file_rows()
        symbols = store.fetch_symbols()
        edges = store.fetch_edges()
        diagnostics = store.fetch_diagnostics()
        stats = store.stats()

    symbol_counts = Counter(str(symbol["file_id"]) for symbol in symbols if symbol.get("file_id") is not None)
    incoming_counts = Counter(str(edge["target_file_id"]) for edge in edges if edge.get("target_file_id") is not None)
    outgoing_counts = Counter(str(edge["source_file_id"]) for edge in edges if edge.get("source_file_id") is not None)

    file_rows = []
    directories: set[str] = set()
    for row in files:
        file_id = str(row["id"])
        path_value = str(row["path"])
        directories.add(str(Path(path_value).parent))
        file_rows.append(
            {
                **row,
                "directory": str(Path(path_value).parent),
                "symbol_count": symbol_counts.get(file_id, 0),
                "incoming_count": incoming_counts.get(file_id, 0),
                "outgoing_count": outgoing_counts.get(file_id, 0),
                "degree": incoming_counts.get(file_id, 0) + outgoing_counts.get(file_id, 0),
            }
        )

    components = _connected_components(files, edges)
    component_lookup: dict[str, int] = {}
    for index, component in enumerate(components, start=1):
        for file_id in component:
            component_lookup[file_id] = index
    for row in file_rows:
        row["component"] = component_lookup.get(str(row["id"]), 0)

    hottest = sorted(file_rows, key=lambda row: (-int(row.get("degree", 0)), str(row.get("path", ""))))[:20]

    return {
        "root_path": str(root_path),
        "db_path": str(db_path),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "counts": {
            "directories": len(directories),
            "files": len(file_rows),
            "symbols": len(symbols),
            "edges": len(edges),
            "diagnostics": len(diagnostics),
        },
        "stats": stats,
        "files": file_rows,
        "symbols": symbols,
        "edges": edges,
        "diagnostics": diagnostics,
        "components": [{"id": index, "size": len(component)} for index, component in enumerate(components, start=1)],
        "top_hubs": hottest,
    }


def _aggregate_edges(files: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    file_lookup = {str(row["id"]): row for row in files}
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for edge in edges:
        source_id = edge.get("source_file_id")
        target_id = edge.get("target_file_id")
        if source_id is None or target_id is None:
            continue
        source_key = str(source_id)
        target_key = str(target_id)
        if source_key == target_key:
            continue
        key = (source_key, target_key)
        bucket = grouped.setdefault(
            key,
            {
                "source_file_id": source_key,
                "target_file_id": target_key,
                "source_path": file_lookup.get(source_key, {}).get("path"),
                "target_path": file_lookup.get(target_key, {}).get("path"),
                "weight": 0,
                "kind_counts": Counter(),
                "sample_refs": [],
            },
        )
        edge_kind = str(edge.get("edge_kind") or "imports")
        bucket["weight"] += 1
        bucket["kind_counts"][edge_kind] += 1
        ref = edge.get("target_ref")
        if ref and len(bucket["sample_refs"]) < 4 and ref not in bucket["sample_refs"]:
            bucket["sample_refs"].append(ref)

    aggregated = []
    for bucket in grouped.values():
        kind_counts: Counter = bucket["kind_counts"]
        primary_kind = kind_counts.most_common(1)[0][0] if kind_counts else "imports"
        aggregated.append(
            {
                "source_file_id": bucket["source_file_id"],
                "target_file_id": bucket["target_file_id"],
                "source_path": bucket["source_path"],
                "target_path": bucket["target_path"],
                "weight": bucket["weight"],
                "primary_kind": primary_kind,
                "kind_counts": dict(kind_counts),
                "sample_refs": bucket["sample_refs"],
                "label": ", ".join(f"{kind} x{count}" for kind, count in kind_counts.most_common()),
            }
        )
    aggregated.sort(key=lambda item: (-int(item["weight"]), str(item.get("source_path", "")), str(item.get("target_path", ""))))
    return aggregated


def build_graph_view(payload: dict[str, Any], *, target: str | None = None, depth: int = 1, limit: int = 300) -> dict[str, Any]:
    files = payload["files"]
    edges = payload["edges"]
    aggregated_edges = _aggregate_edges(files, edges)
    if not target:
        if len(files) <= limit:
            file_ids = {str(row["id"]) for row in files}
        else:
            ranked = sorted(files, key=lambda row: (-int(row.get("degree", 0)), -int(row.get("symbol_count", 0)), str(row.get("path", ""))))
            file_ids = {str(row["id"]) for row in ranked[:limit]}
    else:
        lowered = target.lower()
        seed_ids = {
            str(row["id"])
            for row in files
            if lowered in str(row.get("path", "")).lower() or lowered in str(row.get("module_name", "")).lower()
        }
        adjacency: dict[str, set[str]] = defaultdict(set)
        reverse_adj: dict[str, set[str]] = defaultdict(set)
        for edge in aggregated_edges:
            source = edge.get("source_file_id")
            sink = edge.get("target_file_id")
            if source is None or sink is None:
                continue
            source_id = str(source)
            sink_id = str(sink)
            adjacency[source_id].add(sink_id)
            reverse_adj[sink_id].add(source_id)
        file_ids = set(seed_ids)
        frontier = set(seed_ids)
        for _ in range(max(depth, 0)):
            next_frontier: set[str] = set()
            for file_id in frontier:
                for neighbor in adjacency.get(file_id, set()) | reverse_adj.get(file_id, set()):
                    if neighbor not in file_ids and len(file_ids) < limit:
                        file_ids.add(neighbor)
                        next_frontier.add(neighbor)
            frontier = next_frontier
            if not frontier:
                break

    visible_files = [row for row in files if str(row["id"]) in file_ids]
    visible_edges = [
        edge
        for edge in aggregated_edges
        if str(edge.get("source_file_id")) in file_ids and str(edge.get("target_file_id")) in file_ids
    ]
    return {
        "nodes": visible_files,
        "edges": visible_edges,
        "truncated": len(visible_files) < len(files),
        "visible_count": len(visible_files),
        "total_count": len(files),
        "target": target,
        "depth": depth,
    }


def build_file_details(payload: dict[str, Any], file_path: str) -> dict[str, Any] | None:
    files = payload["files"]
    edges = payload["edges"]
    symbols = payload["symbols"]
    aggregated_edges = _aggregate_edges(files, edges)
    file_row = next((row for row in files if str(row.get("path")) == file_path), None)
    if file_row is None:
        return None
    file_id = str(file_row["id"])
    outgoing = []
    incoming = []
    for edge in aggregated_edges:
        source_id = str(edge.get("source_file_id"))
        target_id = str(edge.get("target_file_id"))
        if source_id == file_id:
            outgoing.append(dict(edge))
        if target_id == file_id:
            incoming.append(dict(edge))
    file_symbols = [symbol for symbol in symbols if str(symbol.get("file_id")) == file_id]
    return {
        "file": file_row,
        "symbols": file_symbols,
        "incoming": incoming,
        "outgoing": outgoing,
    }
