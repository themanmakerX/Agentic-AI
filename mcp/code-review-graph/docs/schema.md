# SQLite Schema

## files

Stores one row per tracked file.

Important columns:

- `path`: workspace-relative path
- `module_name`: normalized module identifier
- `language_id`: registry language id
- `content_hash`: SHA-256 hash used for change detection
- `size`, `mtime_ns`: filesystem metadata

## symbols

Stores structural nodes extracted from the syntax tree.

Each row belongs to one file.

## edges

Stores dependency relationships.

Current supported edge kinds:

- `imports`
- `references`

Targets can be unresolved using `target_ref`, then resolved to `target_file_id` later.

## diagnostics

Stores parser warnings and parse anomalies.

