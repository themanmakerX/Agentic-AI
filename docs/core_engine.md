# Core Engine Overview

This document describes the worker-owned core layer.

## Goals

- Track code structure at file and symbol level.
- Build a persistent graph that can be queried by later components.
- Support incremental updates instead of full rebuilds.
- Keep Tree-sitter as the primary parsing path, while allowing test doubles and future language adapters.

## Modules

- `code_review_graph.languages`
- `code_review_graph.parser`
- `code_review_graph.storage`
- `code_review_graph.incremental`

## Data Flow

1. Scan the workspace for tracked files.
2. Detect each file's language through the registry.
3. Hash file content and compare it with the stored snapshot.
4. Parse changed files with the parser backend.
5. Replace the stored graph data for those files.
6. Remove deleted files from the graph.
7. Refresh dependency resolution for unresolved imports.

## Storage Model

The SQLite database stores:

- file snapshots
- symbol nodes
- dependency edges
- parser diagnostics

File rows are the source of truth for incremental change detection. Symbol and edge rows are rebuilt for a file when that file changes.

## Incremental Strategy

Incremental updates are intentionally conservative:

- changed files are reparsed and fully replaced
- deleted files are removed
- unchanged files are skipped
- import edges are re-resolved after the batch completes

This trades a small amount of extra work for predictable behavior.

## Extending Languages

Add a language in `languages.py` by providing:

- language id
- file extensions
- optional Tree-sitter loader

If the loader is not available, the registry can still classify files for bookkeeping and tests can use fake parsers.

## Current Python API

- `code_review_graph.graph.builder.build_graph(root, db_path)`
- `code_review_graph.graph.builder.update_graph(root, db_path)`
- `code_review_graph.graph.storage.GraphStore`
- `code_review_graph.incremental.IncrementalIndexer`
- `code_review_graph.languages.build_default_registry()`
- `code_review_graph.parser.TreeSitterBackend`

The `graph.builder` layer uses a heuristic fallback backend so the project remains usable in environments where Tree-sitter grammars are not installed yet. The parser module still exposes the Tree-sitter path for production integration.

