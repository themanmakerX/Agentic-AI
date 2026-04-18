import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from vault_core import (
    DEFAULT_HOME,
    add_fact,
    add_journal_entry,
    add_link,
    add_record,
    create_vault,
    dedup_records,
    export_vault_snapshot,
    get_active_vault,
    get_vault_files,
    list_vaults,
    query_facts,
    rebuild_index,
    search_records,
    set_active_vault,
    timeline,
    vault_status,
)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as error:  # pragma: no cover
    raise RuntimeError("mcp is not installed in the configured Python environment.") from error


DEFAULT_SERVER_NAME = "vault"
HOME = str(Path(os.environ.get("VAULT_HOME", DEFAULT_HOME)).expanduser().resolve())
CLI_ARGS = None


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run the Vault MCP server.")
    parser.add_argument("--name", default=DEFAULT_SERVER_NAME, help="MCP server name.")
    parser.add_argument("--vault", dest="vault_path", default=None, help="Vault path to activate at startup.")
    parser.add_argument("--auto-create", action="store_true", help="Create the default vault if none exists.")
    return parser.parse_args(argv)


def ensure_runtime_vault():
    if CLI_ARGS and CLI_ARGS.vault_path:
        return create_vault(
            vault_path=str(Path(CLI_ARGS.vault_path).expanduser().resolve()),
            name=Path(CLI_ARGS.vault_path).name,
            home_dir=HOME,
            activate=True,
        )
    active = get_active_vault(HOME)
    if active:
        return active
    if not (CLI_ARGS and CLI_ARGS.auto_create):
        return None
    default_path = str(Path.home() / "Vault")
    return create_vault(
        vault_path=default_path,
        name="Vault",
        home_dir=HOME,
        activate=True,
    )


def _with_active(callback):
    active = ensure_runtime_vault()
    if not active:
        return vault_status(HOME)
    return callback(active)


def _get_record_by_id(active_path, record_id):
    records_path = Path(get_vault_files(active_path)["records"])
    if not records_path.exists():
        return {"error": f"Record not found: {record_id}"}
    for line in records_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("id") == record_id:
            return record
    return {"error": f"Record not found: {record_id}"}


def _read_journal(active, last_n):
    journal_path = Path(get_vault_files(active["path"])["journal"])
    entries = []
    if journal_path.exists():
        for line in journal_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(json.loads(line))
    return {"vault": active["name"], "entries": entries[-max(0, int(last_n or 10)) :]}


def _checkpoint(active, session_id="", note="", summary="", source=""):
    journal_entry = add_journal_entry(
        vault_path=active["path"],
        session_id=session_id,
        entry_type="checkpoint",
        note=note,
        metadata={"source": source},
    )
    record = None
    if str(summary).strip():
        record = add_record(
            vault_path=active["path"],
            title=f"Checkpoint {journal_entry['createdAt']}",
            content=summary,
            tags=["checkpoint"],
            source=source,
            kind="checkpoint",
        )
    return {"journalEntry": journal_entry, "record": record}


def _build_server(name=DEFAULT_SERVER_NAME):
    mcp = FastMCP(name)

    @mcp.tool(name="vault_status")
    def vault_status_tool() -> dict:
        """Show the current vault, configured vaults, and whether setup is needed."""

        return vault_status(HOME)

    @mcp.tool(name="vault_list_vaults")
    def vault_list_vaults_tool() -> dict:
        """List all known vaults and the active one."""

        return {"vaults": list_vaults(HOME), "activeVault": get_active_vault(HOME)}

    @mcp.tool(name="vault_create_vault")
    def vault_create_vault_tool(vault_path: str, name: str | None = None, activate: bool = True) -> dict:
        """Create a vault directory and activate it."""

        return create_vault(
            vault_path=vault_path,
            name=name or Path(vault_path).name,
            home_dir=HOME,
            activate=activate,
        )

    @mcp.tool(name="vault_use_vault")
    def vault_use_vault_tool(vault_path: str) -> dict:
        """Switch the active vault to an existing vault path."""

        return {"activeVaultPath": set_active_vault(vault_path=vault_path, home_dir=HOME)}

    @mcp.tool(name="vault_add_record")
    def vault_add_record_tool(
        content: str,
        title: str = "",
        tags: list[str] | None = None,
        source: str = "",
        kind: str = "record",
    ) -> dict:
        """Store a verbatim record in the active vault."""

        return _with_active(
            lambda active: add_record(
                vault_path=active["path"],
                title=title,
                content=content,
                tags=tags or [],
                source=source,
                kind=kind,
            )
        )

    @mcp.tool(name="vault_ingest_text")
    def vault_ingest_text_tool(
        content: str,
        title: str = "",
        tags: list[str] | None = None,
        source: str = "",
    ) -> dict:
        """Ingest plain text with optional tags and source metadata."""

        def runner(active):
            record = add_record(
                vault_path=active["path"],
                title=title,
                content=content,
                tags=tags or [],
                source=source,
                kind="ingest",
            )
            add_journal_entry(
                vault_path=active["path"],
                entry_type="ingest",
                note=f"Ingested: {title}" if title else "Ingested text",
                metadata={"recordId": record["id"], "source": source},
            )
            return record

        return _with_active(runner)

    @mcp.tool(name="vault_search")
    def vault_search_tool(query: str, limit: int = 5, kind: str | None = None, tag: str | None = None) -> dict:
        """Search the active vault."""

        return _with_active(
            lambda active: {
                "vault": active["name"],
                "results": search_records(
                    vault_path=active["path"],
                    query=query,
                    limit=limit,
                    kind=kind,
                    tag=tag,
                ),
            }
        )

    @mcp.tool(name="vault_get_record")
    def vault_get_record_tool(record_id: str) -> dict:
        """Fetch a single record by id."""

        return _with_active(lambda active: _get_record_by_id(active["path"], record_id))

    @mcp.tool(name="vault_add_fact")
    def vault_add_fact_tool(
        subject: str,
        predicate: str,
        object: str,
        valid_from: str | None = None,
        valid_to: str | None = None,
        confidence: float = 1.0,
    ) -> dict:
        """Add a structured fact to the active vault."""

        return _with_active(
            lambda active: add_fact(
                vault_path=active["path"],
                subject=subject,
                predicate=predicate,
                object_value=object,
                valid_from=valid_from,
                valid_to=valid_to,
                confidence=confidence,
            )
        )

    @mcp.tool(name="vault_query_entity")
    def vault_query_entity_tool(subject: str, as_of: str | None = None, direction: str = "both") -> dict:
        """Query structured facts for an entity."""

        return _with_active(
            lambda active: {
                "subject": subject,
                "facts": query_facts(
                    vault_path=active["path"],
                    subject=subject,
                    as_of=as_of,
                    direction=direction,
                ),
                "timeline": timeline(vault_path=active["path"], subject=subject),
            }
        )

    @mcp.tool(name="vault_add_link")
    def vault_add_link_tool(from_record_id: str, to_record_id: str, label: str = "") -> dict:
        """Add an explicit link between two records."""

        return _with_active(
            lambda active: add_link(
                vault_path=active["path"],
                from_record_id=from_record_id,
                to_record_id=to_record_id,
                label=label,
            )
        )

    @mcp.tool(name="vault_journal_write")
    def vault_journal_write_tool(note: str, session_id: str = "", entry_type: str = "checkpoint") -> dict:
        """Write a checkpoint or session note into the active vault journal."""

        return _with_active(
            lambda active: add_journal_entry(
                vault_path=active["path"],
                session_id=session_id,
                entry_type=entry_type,
                note=note,
            )
        )

    @mcp.tool(name="vault_journal_read")
    def vault_journal_read_tool(last_n: int = 10) -> dict:
        """Read recent journal entries."""

        return _with_active(lambda active: _read_journal(active, last_n))

    @mcp.tool(name="vault_checkpoint")
    def vault_checkpoint_tool(note: str, session_id: str = "", summary: str = "", source: str = "") -> dict:
        """Store a checkpoint and optionally a short summary record."""

        return _with_active(
            lambda active: _checkpoint(
                active,
                session_id=session_id,
                note=note,
                summary=summary,
                source=source,
            )
        )

    @mcp.tool(name="vault_rebuild_index")
    def vault_rebuild_index_tool() -> dict:
        """Rebuild the derived search index for the active vault."""

        return _with_active(lambda active: rebuild_index(vault_path=active["path"]))

    @mcp.tool(name="vault_dedup")
    def vault_dedup_tool(threshold: float = 0.9, dry_run: bool = True) -> dict:
        """Deduplicate near-identical records."""

        return _with_active(
            lambda active: dedup_records(
                vault_path=active["path"],
                threshold=threshold,
                dry_run=dry_run,
            )
        )

    @mcp.tool(name="vault_export_snapshot")
    def vault_export_snapshot_tool() -> dict:
        """Export the current vault contents in one object."""

        return _with_active(lambda active: export_vault_snapshot(active["path"]))

    return mcp


def main(argv=None):
    global CLI_ARGS
    CLI_ARGS = parse_args(argv)
    ensure_runtime_vault()
    server = _build_server(CLI_ARGS.name)
    server.run()


if __name__ == "__main__":
    main()
