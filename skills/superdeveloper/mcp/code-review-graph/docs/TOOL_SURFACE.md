# Tool Surface

This document defines the server contract exposed to MCP clients.

## `build_or_update_graph`

Builds the graph for a workspace or updates existing indexes incrementally.
The response is always a JSON-safe object shaped as:

```json
{
  "ok": true,
  "summary": "short status message",
  "data": {}
}
```

Example request:

```json
{
  "root_path": "E:/Education/my-repo",
  "incremental": true
}
```

Example response:

```json
{
  "ok": true,
  "summary": "Indexed 14 changed files and refreshed 83 edges.",
  "data": {
    "changed_files": 14,
    "refreshed_edges": 83
  }
}
```

## `get_impact_radius`

Returns the structural blast radius for one or more file or symbol targets.
The result includes seed paths, impacted paths, test candidates, and the depth used.

Example request:

```json
{
  "targets": ["src/services/payment.py:charge_card"],
  "depth": 2
}
```

## `get_review_context`

Returns the smallest useful review bundle for a change set.
This is the main tool for feeding a minimal context bundle into the reviewer model.

Expected output usually includes:

- primary files
- directly impacted neighbors
- important symbols
- a compact summary for review consumption

## `query_graph`

Runs a structural graph query.

Use this for direct lookups such as:

- symbol name matches
- file-to-file relations
- import chains
- ownership or dependency checks

## `semantic_search_nodes`

Runs hybrid semantic ranking over graph nodes.
If embeddings are available, the backend uses them; otherwise it falls back to token-overlap ranking.

## `list_graph_stats`

Returns graph health and coverage data such as:

- number of files
- number of symbols
- number of edges
- index freshness

## `find_files_by_pattern`

Returns files matching a path, module name, or symbol-aware pattern supported by the backend.

## `detect_changes`

Compares two refs and summarizes graph-relevant changes.

Useful for pull request review pipelines.

## `trace_dataflow`

Returns the shortest known structural path between a source and a sink.
If the sink cannot be resolved or no path exists, the response explains why.

## `audit_workspace`

Returns a readiness report for the current workspace.
The audit includes coverage, language distribution, unresolved imports, and diagnostics.

## `list_communities`

Returns connected components in the file graph as communities.

## `get_architecture_overview`

Returns a compact architecture summary with community counts and hub files.

## `refactor_workspace`

Returns heuristic refactor suggestions, including large symbols, dead-code candidates, and rename candidates.

## `generate_wiki`

Returns Markdown wiki pages derived from the graph and optionally writes them to disk.
The wiki includes an index, architecture page, and up to 20 full community pages;
if the repo has more communities, a summary page is added.

Useful for checking whether the graph is complete enough for review use.

## Tool behavior rules

- Tools should be deterministic for the same workspace state.
- Tools should return JSON-safe objects.
- Tools should keep summaries short and actionable.
- Tools should not expose parser internals unless the backend explicitly chooses to include them.
