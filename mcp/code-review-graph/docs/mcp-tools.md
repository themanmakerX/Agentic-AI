# MCP Tools

The server currently exposes the following tools:

## `build_or_update_graph`

Builds the graph from scratch or refreshes it incrementally when the workspace has changed.
Returns:
- `ok`
- `summary`
- `data`

## `get_impact_radius`

Computes the blast radius for a set of file or symbol targets.
The response includes seed paths, impacted paths, test candidates, and the search depth used.

## `get_review_context`

Returns a review-ready subset of the repository derived from the impact radius.
This is the preferred tool when you want the assistant to inspect only the files that matter.

## `query_graph`

Performs a structural lookup over files, symbols, and edges.
Results are ranked and include a score for each match.

## `list_graph_stats`

Returns graph counts and health metrics from the SQLite store.

## `find_files_by_pattern`

Finds indexed files by path, module name, or symbol-aware pattern.

## `detect_changes`

Compares two Git refs and returns the changed file set.

## `semantic_search_nodes`

Runs hybrid semantic ranking across indexed files and symbols.
If `sentence-transformers` is available, the backend uses embeddings.
Otherwise it falls back to token-overlap ranking.

## `trace_dataflow`

Finds the shortest known structural path between source and sink targets.
If no path is found, the response includes a best-effort exploration result and a reason.

## `audit_workspace`

Returns workspace health information including coverage, language distribution,
unresolved import edges, and diagnostics.

## `list_communities`

Lists graph communities derived from connected components in the file graph.

## `get_architecture_overview`

Returns a compact overview with community counts, language distribution, and hub files.

## `refactor_workspace`

Returns heuristic refactor suggestions, including large symbols, dead-code candidates,
and rename candidates.

## `generate_wiki`

Generates Markdown wiki pages from the current graph.
When `write_to_disk` is true, the pages are also written to `.code-review-graph/wiki`.
The output includes an index, an architecture page, and up to 20 full community pages,
plus a summary page when the repo has more communities than that cap.

## Response Contract

Every tool returns a structured object shaped like:

```json
{
  "ok": true,
  "summary": "short human-readable message",
  "data": {}
}
```
