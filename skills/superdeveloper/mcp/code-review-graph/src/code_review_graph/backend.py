"""High-level graph service built on the incremental indexer."""

from __future__ import annotations

from collections import Counter, deque
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .graph.builder import BuildSummary, UpdateSummary, build_graph, update_graph
from .incremental import IncrementalIndexer
from .languages import build_default_registry
from .parser import GraphParser
from .storage import SQLiteGraphStore


@dataclass(slots=True)
class GraphService:
    root_path: Path
    db_path: Path
    _embedding_model: Any = None

    def build(self) -> BuildSummary:
        return build_graph(self.root_path, self.db_path)

    def update(self) -> UpdateSummary:
        return update_graph(self.root_path, self.db_path)

    def _store(self) -> SQLiteGraphStore:
        return SQLiteGraphStore(self.db_path)

    def _known_files(self) -> list[dict[str, Any]]:
        with self._store() as store:
            return store.fetch_file_rows()

    def _files_by_id(self) -> dict[str, dict[str, Any]]:
        return {str(row["id"]): row for row in self._known_files()}

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [token for token in re.findall(r"[A-Za-z0-9_./:-]+", text.lower()) if token]

    def _resolve_target_file_ids(self, targets: list[str]) -> list[str]:
        files = self._known_files()
        with self._store() as store:
            symbols = store.fetch_symbols()
        lowered = [target.lower() for target in targets]

        resolved: set[str] = set()
        for file_row in files:
            haystack = " ".join(
                [
                    str(file_row["path"]),
                    str(file_row["module_name"]),
                    str(file_row["language_id"]),
                ]
            ).lower()
            if any(target in haystack for target in lowered):
                resolved.add(str(file_row["id"]))

        for symbol in symbols:
            haystack = " ".join(
                [
                    str(symbol.get("name", "")),
                    str(symbol.get("qualified_name", "")),
                    str(symbol.get("kind", "")),
                ]
            ).lower()
            if any(target in haystack for target in lowered) and symbol.get("file_id") is not None:
                resolved.add(str(symbol["file_id"]))

        return sorted(resolved)

    def _build_adjacency(self) -> dict[str, set[str]]:
        with self._store() as store:
            edges = store.fetch_edges()
        adjacency: dict[str, set[str]] = {}
        for edge in edges:
            source_file_id = edge.get("source_file_id")
            target_file_id = edge.get("target_file_id")
            if source_file_id is None or target_file_id is None:
                continue
            adjacency.setdefault(str(source_file_id), set()).add(str(target_file_id))
        return adjacency

    def _edge_rows(self) -> list[dict[str, Any]]:
        with self._store() as store:
            return store.fetch_edges()

    def _symbol_lookup(self) -> dict[str, list[dict[str, Any]]]:
        with self._store() as store:
            files = {str(row["id"]): row for row in store.fetch_file_rows()}
            symbols = store.fetch_symbols()
        lookup: dict[str, list[dict[str, Any]]] = {}
        for symbol in symbols:
            key_candidates = {
                str(symbol.get("name", "")),
                str(symbol.get("qualified_name", "")),
                f'{files.get(str(symbol.get("file_id")), {}).get("path", "")}:{symbol.get("name", "")}',
            }
            for key in key_candidates:
                if key:
                    lookup.setdefault(key, []).append(symbol)
        return lookup

    def _embedding_backend(self):
        if self._embedding_model is False:
            return None
        if self._embedding_model is not None:
            return self._embedding_model
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception:
            self._embedding_model = False
            return None

        model_name = os.environ.get("CRG_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        try:
            self._embedding_model = SentenceTransformer(model_name)
        except Exception:
            self._embedding_model = False
            return None
        return self._embedding_model

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _embed_texts(self, texts: list[str]) -> list[list[float]] | None:
        backend = self._embedding_backend()
        if backend is None:
            return None
        try:
            vectors = backend.encode(texts, normalize_embeddings=True)
        except Exception:
            return None
        try:
            return [list(map(float, vector)) for vector in vectors]
        except TypeError:
            return None

    @staticmethod
    def _file_text(row: dict[str, Any]) -> str:
        return " ".join(
            [
                str(row.get("path", "")),
                str(row.get("module_name", "")),
                str(row.get("language_id", "")),
            ]
        ).strip()

    @staticmethod
    def _symbol_text(row: dict[str, Any]) -> str:
        return " ".join(
            [
                str(row.get("name", "")),
                str(row.get("qualified_name", "")),
                str(row.get("kind", "")),
            ]
        ).strip()

    def stats(self) -> dict[str, Any]:
        with self._store() as store:
            return store.stats()

    def query(self, query: str, limit: int = 20) -> dict[str, Any]:
        query = query.strip()
        query_tokens = self._tokenize(query)
        with self._store() as store:
            files = {str(row["id"]): row for row in store.fetch_file_rows()}
            symbols = store.fetch_symbols()
            edges = store.fetch_edges()

        matches = []
        for symbol in symbols:
            file_row = files.get(str(symbol.get("file_id")))
            haystack = " ".join(
                [
                    str(symbol.get("name", "")),
                    str(symbol.get("qualified_name", "")),
                    str(symbol.get("kind", "")),
                    str(file_row.get("path", "") if file_row else ""),
                ]
            ).lower()
            if not query_tokens or all(token in haystack for token in query_tokens):
                matches.append(
                    {
                        "type": "symbol",
                        "file_path": file_row.get("path") if file_row else None,
                        "score": len([token for token in query_tokens if token in haystack]),
                        **symbol,
                    }
                )

        for edge in edges:
            haystack = " ".join(
                [
                    str(edge.get("edge_kind", "")),
                    str(edge.get("target_ref", "")),
                ]
            ).lower()
            if not query_tokens or all(token in haystack for token in query_tokens):
                matches.append({"type": "edge", "score": len([token for token in query_tokens if token in haystack]), **edge})

        matches.sort(key=lambda item: (-int(item.get("score", 0)), str(item.get("type", ""))))
        return {"query": query, "limit": limit, "matches": matches[:limit]}

    def semantic_search(self, query: str, limit: int = 20) -> dict[str, Any]:
        query_tokens = self._tokenize(query)
        with self._store() as store:
            files = store.fetch_file_rows()
            symbols = store.fetch_symbols()
        corpus: list[str] = []
        items: list[dict[str, Any]] = []
        for file_row in files:
            corpus.append(self._file_text(file_row))
            items.append({"type": "file", **file_row})
        for symbol in symbols:
            corpus.append(self._symbol_text(symbol))
            items.append({"type": "symbol", **symbol})

        query_vecs = self._embed_texts([query])
        item_vecs = self._embed_texts(corpus)
        scored: list[dict[str, Any]] = []
        for index, (item, text) in enumerate(zip(items, corpus)):
            overlap = len([token for token in query_tokens if token in text.lower()])
            lexical = overlap + (2 if query.lower() in text.lower() else 0)
            score = float(lexical)
            strategy = "token-overlap-ranking"
            if query_vecs is not None and item_vecs is not None:
                embedding_score = self._cosine_similarity(query_vecs[0], item_vecs[index])
                score = score + max(embedding_score, 0.0) * 10.0
                strategy = "hybrid-embedding-ranking"
            if overlap or query.lower() in text.lower() or score > 0:
                output = dict(item)
                output["score"] = round(score, 4)
                output["strategy"] = strategy
                if item["type"] == "symbol":
                    file_row = next((row for row in files if row["id"] == item["file_id"]), None)
                    output["file_path"] = file_row["path"] if file_row else None
                scored.append(output)

        scored.sort(key=lambda item: (-float(item["score"]), str(item.get("type", "")), str(item.get("name", item.get("path", "")))))
        return {
            "query": query,
            "limit": limit,
            "matches": scored[:limit],
            "strategy": "hybrid-embedding-ranking" if query_vecs is not None and item_vecs is not None else "token-overlap-ranking",
        }

    def find_files_by_pattern(self, pattern: str, limit: int = 50) -> dict[str, Any]:
        pattern = pattern.strip().lower()
        files = self._known_files()
        matches = [
            file_row
            for file_row in files
            if pattern in file_row["path"].lower() or pattern in file_row["module_name"].lower()
        ]
        return {"pattern": pattern, "matches": matches[:limit]}

    def _git_diff_names(self, base_ref: str, head_ref: str) -> list[str]:
        try:
            output = subprocess.check_output(
                ["git", "-C", str(self.root_path), "diff", "--name-only", base_ref, head_ref],
                stderr=subprocess.STDOUT,
                text=True,
            )
        except Exception:
            return []
        return [line.strip() for line in output.splitlines() if line.strip()]

    def detect_changes(self, base_ref: str, head_ref: str) -> dict[str, Any]:
        changed_paths = self._git_diff_names(base_ref, head_ref)
        with self._store() as store:
            files = store.fetch_file_rows()
            symbols = store.fetch_symbols()
            edges = store.fetch_edges()

        file_lookup = {str(row["path"]): row for row in files}
        impacted_symbols: list[dict[str, Any]] = []
        impacted_tests: list[str] = []
        file_statuses: list[dict[str, Any]] = []
        risk_score = 0

        referenced_symbol_ids = {str(edge["target_symbol_id"]) for edge in edges if edge.get("target_symbol_id") is not None}

        for path in changed_paths:
            row = file_lookup.get(path)
            if row is None:
                file_statuses.append({"path": path, "status": "untracked"})
                continue

            file_symbols = [symbol for symbol in symbols if str(symbol.get("file_id")) == str(row["id"])]
            file_edges = [edge for edge in edges if str(edge.get("source_file_id")) == str(row["id"])]
            impacted_symbols.extend(
                {
                    "name": symbol.get("name"),
                    "qualified_name": symbol.get("qualified_name"),
                    "kind": symbol.get("kind"),
                    "file_path": row["path"],
                }
                for symbol in file_symbols
            )
            if "/test" in path.lower() or path.lower().startswith("test_") or path.endswith("_test.py"):
                impacted_tests.append(path)
            if row["language_id"] == "python":
                risk_score += 2
            risk_score += min(3, len(file_symbols))
            risk_score += min(2, len(file_edges))
            if not file_edges:
                risk_score += 1
            file_statuses.append(
                {
                    "path": path,
                    "status": "tracked",
                    "language_id": row["language_id"],
                    "module_name": row["module_name"],
                    "symbol_count": len(file_symbols),
                    "edge_count": len(file_edges),
                }
            )

        impacted_tests = sorted(set(impacted_tests))
        risk_level = "low"
        if risk_score >= 12:
            risk_level = "high"
        elif risk_score >= 6:
            risk_level = "medium"

        return {
            "base_ref": base_ref,
            "head_ref": head_ref,
            "changed_paths": changed_paths,
            "files": file_statuses,
            "impacted_symbols": impacted_symbols[:200],
            "tests": impacted_tests,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "summary": f"{len(changed_paths)} files changed, {len(impacted_symbols)} symbols impacted, risk={risk_level}.",
        }

    def _resolve_seed_files(self, targets: list[str]) -> list[str]:
        with self._store() as store:
            files = store.fetch_file_rows()
            symbols = store.fetch_symbols()
        seed_ids: set[str] = set()
        lowered = [target.lower() for target in targets]
        for file_row in files:
            haystack = " ".join(
                [
                    str(file_row["path"]),
                    str(file_row["module_name"]),
                    str(file_row["language_id"]),
                ]
            ).lower()
            if any(target in haystack for target in lowered):
                seed_ids.add(str(file_row["id"]))
        for symbol in symbols:
            haystack = " ".join(
                [
                    str(symbol.get("name", "")),
                    str(symbol.get("qualified_name", "")),
                    str(symbol.get("kind", "")),
                ]
            ).lower()
            if any(target in haystack for target in lowered):
                file_id = symbol.get("file_id")
                if file_id is not None:
                    seed_ids.add(str(file_id))
        return sorted(seed_ids)

    def impact_radius(self, targets: list[str], depth: int = 2) -> dict[str, Any]:
        with self._store() as store:
            files = {str(row["id"]): row for row in store.fetch_file_rows()}
            edges = store.fetch_edges()

        seed_ids = self._resolve_seed_files(targets)
        if not seed_ids:
            lowered = [target.lower() for target in targets]
            seed_ids = [
                file_id
                for file_id, row in files.items()
                if any(target in str(row["path"]).lower() or target in str(row["module_name"]).lower() for target in lowered)
            ]

        adjacency: dict[str, set[str]] = {}
        reverse_adj: dict[str, set[str]] = {}
        for edge in edges:
            source_file_id = edge.get("source_file_id")
            target_file_id = edge.get("target_file_id")
            if source_file_id is None or target_file_id is None:
                continue
            source = str(source_file_id)
            target = str(target_file_id)
            adjacency.setdefault(source, set()).add(target)
            reverse_adj.setdefault(target, set()).add(source)

        impacted = set(seed_ids)
        frontier = set(seed_ids)
        for _ in range(max(depth, 0)):
            next_frontier: set[str] = set()
            for file_id in frontier:
                for neighbor in adjacency.get(file_id, set()) | reverse_adj.get(file_id, set()):
                    if neighbor not in impacted:
                        impacted.add(neighbor)
                        next_frontier.add(neighbor)
            frontier = next_frontier
            if not frontier:
                break

        impacted_paths = sorted(str(files[file_id]["path"]) for file_id in impacted if file_id in files)
        tests = [
            path
            for path in impacted_paths
            if "/test" in path.lower() or path.lower().startswith("test_") or path.endswith("_test.py")
        ]
        return {
            "targets": targets,
            "seed_paths": [str(files[file_id]["path"]) for file_id in seed_ids if file_id in files],
            "impacted_paths": impacted_paths,
            "tests": sorted(tests),
            "depth": depth,
            "status": "tracked",
        }

    def review_context(self, targets: list[str], max_files: int = 10, max_tokens: int = 8000) -> dict[str, Any]:
        radius = self.impact_radius(targets=targets, depth=2)
        relevant = radius["impacted_paths"][:max_files]
        return {
            "targets": targets,
            "relevant_paths": relevant,
            "estimated_tokens": min(max_tokens, max(1, len(relevant)) * 400),
            "summary": "Context selected from the local structural graph.",
        }

    def trace_dataflow(self, source: str, sink: str, max_depth: int = 4) -> dict[str, Any]:
        files = self._files_by_id()
        source_ids = self._resolve_seed_files([source])
        sink_ids = self._resolve_seed_files([sink])
        adjacency = self._build_adjacency()
        with self._store() as store:
            edges = store.fetch_edges()
        for edge in edges:
            source_file_id = edge.get("source_file_id")
            target_file_id = edge.get("target_file_id")
            if source_file_id is None or target_file_id is None:
                continue
            adjacency.setdefault(str(source_file_id), set()).add(str(target_file_id))

        if not source_ids or not sink_ids:
            return {
                "source": source,
                "sink": sink,
                "found": False,
                "paths": [],
                "reason": "Source or sink could not be resolved to indexed files.",
            }

        queue: deque[tuple[str, list[str]]] = deque((source_id, [source_id]) for source_id in source_ids)
        seen = set(source_ids)
        sink_id_set = set(sink_ids)

        while queue:
            current, path_ids = queue.popleft()
            if current in sink_id_set:
                path = [str(files[file_id]["path"]) for file_id in path_ids if file_id in files]
                return {
                    "source": source,
                    "sink": sink,
                    "found": True,
                    "hops": max(len(path_ids) - 1, 0),
                    "path_ids": path_ids,
                    "paths": path,
                }
            if len(path_ids) > max_depth + 1:
                continue
            for neighbor in adjacency.get(current, set()):
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                queue.append((neighbor, path_ids + [neighbor]))

        explored = self.impact_radius(targets=[source], depth=max_depth)["impacted_paths"]
        return {
            "source": source,
            "sink": sink,
            "found": False,
            "paths": explored,
            "reason": "No shortest path found within the current indexed graph.",
        }

    def _connected_components(self) -> list[list[str]]:
        adjacency = self._build_adjacency()
        reverse_adj: dict[str, set[str]] = {}
        for src, targets in adjacency.items():
            for target in targets:
                reverse_adj.setdefault(target, set()).add(src)

        all_nodes = set(adjacency)
        for targets in adjacency.values():
            all_nodes.update(targets)
        all_nodes.update(self._files_by_id())

        components: list[list[str]] = []
        seen: set[str] = set()
        for node in sorted(all_nodes):
            if node in seen:
                continue
            stack = [node]
            component: list[str] = []
            seen.add(node)
            while stack:
                current = stack.pop()
                component.append(current)
                neighbors = adjacency.get(current, set()) | reverse_adj.get(current, set())
                for neighbor in neighbors:
                    if neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
            components.append(sorted(component))
        return sorted(components, key=len, reverse=True)

    def audit_workspace(self) -> dict[str, Any]:
        with self._store() as store:
            files = store.fetch_file_rows()
            symbols = store.fetch_symbols()
            edges = store.fetch_edges()
            diagnostics = store.fetch_diagnostics()

        stats = self.stats()
        files_with_symbols = {str(symbol["file_id"]) for symbol in symbols if symbol.get("file_id") is not None}
        language_counts = Counter(str(file_row["language_id"]) for file_row in files)
        unresolved_import_edges = sum(
            1
            for edge in edges
            if edge.get("edge_kind") == "imports" and edge.get("target_file_id") is None
        )
        files_with_diagnostics = {str(diag["file_id"]) for diag in diagnostics if diag.get("file_id") is not None}
        return {
            "status": "ok" if stats.get("files", 0) else "empty",
            "stats": stats,
            "coverage": {
                "files_indexed": stats.get("files", 0),
                "files_with_symbols": len(files_with_symbols),
                "coverage_ratio": round(len(files_with_symbols) / max(stats.get("files", 1), 1), 3),
            },
            "language_counts": dict(sorted(language_counts.items())),
            "unresolved_import_edges": unresolved_import_edges,
            "files_with_diagnostics": len(files_with_diagnostics),
            "diagnostic_count": len(diagnostics),
            "notes": [
                "Semantic search uses token-overlap ranking over file, module, and symbol names.",
                "Trace dataflow returns the shortest known structural path between indexed source and sink targets.",
                "Import edges are resolved against indexed module names after each update.",
            ],
        }

    def list_communities(self, min_size: int = 2) -> dict[str, Any]:
        files = self._files_by_id()
        components = self._connected_components()
        communities = []
        for index, component in enumerate(components, start=1):
            if len(component) < min_size:
                continue
            component_rows = [files[file_id] for file_id in component if file_id in files]
            languages = Counter(str(row["language_id"]) for row in component_rows)
            communities.append(
                {
                    "id": index,
                    "size": len(component_rows),
                    "files": [row["path"] for row in component_rows[:50]],
                    "languages": dict(sorted(languages.items())),
                    "hub_files": [row["path"] for row in component_rows[:5]],
                }
            )
        return {"min_size": min_size, "communities": communities, "count": len(communities)}

    def get_architecture_overview(self) -> dict[str, Any]:
        files = self._files_by_id()
        communities = self.list_communities(min_size=1)["communities"]
        language_counts = Counter(str(row["language_id"]) for row in files.values())
        adjacency = self._build_adjacency()
        degree_counts = Counter()
        for source, targets in adjacency.items():
            degree_counts[source] += len(targets)
            for target in targets:
                degree_counts[target] += 1
        hottest = [
            {"path": files[file_id]["path"], "degree": degree}
            for file_id, degree in degree_counts.most_common(10)
            if file_id in files
        ]
        largest = communities[0] if communities else {"size": 0, "files": []}
        return {
            "community_count": len(communities),
            "largest_community": largest,
            "language_counts": dict(sorted(language_counts.items())),
            "top_hubs": hottest,
            "summary": (
                f"{len(files)} files across {len(communities)} communities. "
                f"Largest community contains {largest.get('size', 0)} files."
            ),
        }

    def refactor_workspace(self, large_symbol_threshold: int = 80) -> dict[str, Any]:
        with self._store() as store:
            files = {str(row["id"]): row for row in store.fetch_file_rows()}
            symbols = store.fetch_symbols()
            edges = store.fetch_edges()

        references_by_symbol = Counter(
            str(edge["target_symbol_id"])
            for edge in edges
            if edge.get("target_symbol_id") is not None
        )
        large_symbols = []
        dead_code_candidates = []
        rename_candidates = []

        for symbol in symbols:
            start_line = symbol.get("start_line")
            end_line = symbol.get("end_line")
            line_span = (int(end_line) - int(start_line) + 1) if start_line and end_line else 0
            file_row = files.get(str(symbol.get("file_id")))
            file_path = file_row["path"] if file_row else None
            if line_span and line_span >= large_symbol_threshold:
                large_symbols.append(
                    {
                        "name": symbol.get("name"),
                        "qualified_name": symbol.get("qualified_name"),
                        "file_path": file_path,
                        "line_span": line_span,
                        "kind": symbol.get("kind"),
                    }
                )
            if references_by_symbol.get(str(symbol["id"]), 0) == 0 and file_path and not file_path.lower().startswith("test"):
                dead_code_candidates.append(
                    {
                        "name": symbol.get("name"),
                        "qualified_name": symbol.get("qualified_name"),
                        "file_path": file_path,
                        "kind": symbol.get("kind"),
                    }
                )
            name = str(symbol.get("name", ""))
            if len(name) <= 4 or name in {"tmp", "data", "item", "obj", "util"}:
                rename_candidates.append(
                    {
                        "name": name,
                        "qualified_name": symbol.get("qualified_name"),
                        "file_path": file_path,
                        "reason": "ambiguous_or_short_name",
                    }
                )

        return {
            "large_symbol_threshold": large_symbol_threshold,
            "large_symbols": large_symbols,
            "dead_code_candidates": dead_code_candidates[:200],
            "rename_candidates": rename_candidates[:200],
            "summary": (
                f"{len(large_symbols)} large symbols, "
                f"{len(dead_code_candidates)} potential dead-code symbols, "
                f"{len(rename_candidates)} rename candidates."
            ),
        }

    def generate_wiki(self, write_to_disk: bool = False) -> dict[str, Any]:
        files = self._files_by_id()
        communities = self.list_communities(min_size=1)["communities"]
        overview = self.get_architecture_overview()
        max_community_pages = 20
        selected_communities = communities[:max_community_pages]
        pages: dict[str, str] = {}

        index_lines = [
            "# Repository Wiki",
            "",
            "## Overview",
            "",
            overview["summary"],
            "",
            "## Communities",
        ]
        for community in communities:
            index_lines.append(
                f"- Community {community['id']}: {community['size']} files"
            )
        if len(communities) > max_community_pages:
            index_lines.append("")
            index_lines.append(f"Only the first {max_community_pages} community pages are emitted in full.")
        pages["index.md"] = "\n".join(index_lines) + "\n"

        for community in selected_communities:
            lines = [
                f"# Community {community['id']}",
                "",
                f"Size: {community['size']}",
                "",
                "## Files",
            ]
            for path in community["files"]:
                lines.append(f"- {path}")
            lines.append("")
            lines.append("## Languages")
            for language, count in community["languages"].items():
                lines.append(f"- {language}: {count}")
            pages[f"communities/community-{community['id']}.md"] = "\n".join(lines) + "\n"

        if len(communities) > max_community_pages:
            pages["communities/summary.md"] = "\n".join(
                [
                    "# Community Summary",
                    "",
                    f"Total communities: {len(communities)}",
                    f"Rendered community pages: {len(selected_communities)}",
                ]
            ) + "\n"

        pages["architecture.md"] = "\n".join(
            [
                "# Architecture",
                "",
                overview["summary"],
                "",
                "## Top Hubs",
                *[f"- {item['path']} ({item['degree']})" for item in overview["top_hubs"]],
            ]
        ) + "\n"

        output_dir = self.root_path / ".code-review-graph" / "wiki"
        if write_to_disk:
            for relative_path, content in pages.items():
                target = output_dir / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

        return {
            "write_to_disk": write_to_disk,
            "output_dir": str(output_dir),
            "page_count": len(pages),
            "pages": pages,
            "summary": f"Generated {len(pages)} wiki pages from {len(files)} indexed files.",
        }


def create_service(root_path: Path, db_path: Path) -> GraphService:
    return GraphService(root_path=Path(root_path).resolve(), db_path=Path(db_path).resolve())
