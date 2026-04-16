# Consuming the Graph Later

The MCP server is only the access layer. Downstream consumers should rely on the tool outputs, not on any internal storage format.

## Recommended flow

1. Call `build_or_update_graph`.
2. Call `list_graph_stats` to confirm the index is healthy.
3. Call `detect_changes` or `get_impact_radius` for the relevant change.
4. Call `get_review_context` to fetch the final review bundle.
5. Call `get_architecture_overview` when you need a fast high-level map.
6. Call `list_communities` for module clustering and ownership analysis.

If you need a deeper investigation:

1. Use `query_graph` for exact structural lookups.
2. Use `semantic_search_nodes` for ranked fuzzy matches.
3. Use `trace_dataflow` when you want the shortest known path between two targets.
4. Use `audit_workspace` before trusting the graph for a review pass.
5. Use `refactor_workspace` to identify maintainability risks.
6. Use `generate_wiki` to emit Markdown pages for onboarding or documentation.

## Example consumer pattern

```text
1. User changes 3 files in a pull request.
2. The client calls detect_changes(base_ref, head_ref).
3. The client feeds the changed symbols into get_impact_radius().
4. The client requests get_review_context() to prepare the prompt payload.
5. The client only sends the minimal context to the reviewer model.
```

## What to consume

Prefer these fields from backend responses:

- changed files
- affected symbols
- dependency edges
- file summaries
- review-ready context blocks
- ranked search results with scores
- audit coverage and diagnostics
- architecture summaries
- community breakdowns
- refactor suggestions
- wiki pages

## What not to consume

Do not depend on:

- parser implementation details
- database table names
- internal cache keys
- backend-specific debug traces unless you explicitly need them

## Stable contract expectation

The server contract is intentionally narrow so the graph core can change without breaking MCP clients.

If you later swap the backend implementation, the consumer should continue to work as long as it preserves:

- the same tool names
- the same top-level response shape
- compatible JSON payloads
