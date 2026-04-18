# Architecture

Code Review Graph is organized around four layers:

1. **CLI layer** - builds, updates, and configures the server
2. **Parser layer** - extracts files, symbols, and dependency edges
3. **Graph storage layer** - persists repository structure in SQLite
4. **MCP layer** - exposes graph queries to assistants and tools

## Data Flow

1. The CLI scans a repository.
2. Each source file is parsed into a language-aware structure.
3. The graph store persists files, symbols, and edges.
4. MCP tools query the store to return review context.

## Graph Semantics

The current implementation stores:

- file snapshots with content hashes and language IDs
- symbol records with spans and metadata
- edge records for imports and symbol references
- diagnostics for parse or indexing warnings

The backend now exposes:

- ranked graph queries
- hybrid semantic search with optional embeddings
- impact-radius analysis
- shortest-path structural tracing
- workspace audit signals
- connected-component communities
- architecture overview summaries
- refactor heuristics
- wiki generation output

## Current Scope

This first implementation focuses on:

- local graph storage
- incremental updates
- `config.toml` integration
- English-only documentation
- clear MCP tool docstrings and structured responses

## Next Planned Extensions

- Tree-sitter parser coverage for more languages and stronger grammar loaders
- deeper dataflow analysis
- persisted wiki publishing
