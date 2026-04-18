import json
import os
import sys
from pathlib import Path

from vault_core import (
    DEFAULT_HOME,
    add_fact,
    add_journal_entry,
    add_link,
    add_record,
    create_vault,
    dedup_records,
    default_vault_path,
    export_vault_snapshot,
    get_active_vault,
    list_vaults,
    query_facts,
    rebuild_index,
    search_records,
    set_active_vault,
    timeline,
    vault_status,
)


HOME = str(Path(os.environ.get("VAULT_HOME", DEFAULT_HOME)).expanduser().resolve())


def emit(value):
    sys.stdout.write(json.dumps(value, indent=2) + "\n")


def require_active_vault():
    active = get_active_vault(HOME)
    if not active:
        return None, vault_status(HOME)
    return active, None


def read_args():
    args = sys.argv[1:]
    command = args[0] if args else None
    args = args[1:] if args else []
    out = {"command": command, "flags": {}, "positionals": []}
    index = 0
    while index < len(args):
        arg = args[index]
        if arg.startswith("--"):
            key = arg[2:]
            next_value = args[index + 1] if index + 1 < len(args) else None
            if next_value and not next_value.startswith("--"):
                out["flags"][key] = next_value
                index += 2
                continue
            out["flags"][key] = True
        else:
            out["positionals"].append(arg)
        index += 1
    return out


def main():
    parsed = read_args()
    command = parsed["command"]
    flags = parsed["flags"]
    positionals = parsed["positionals"]

    if command == "status":
        emit(vault_status(HOME))
        return
    if command == "list-vaults":
        emit({"vaults": list_vaults(HOME), "activeVault": get_active_vault(HOME)})
        return
    if command == "create-vault":
        target_path = str(Path(flags.get("path") or default_vault_path()).expanduser().resolve())
        emit(
            create_vault(
                vault_path=target_path,
                name=flags.get("name") or Path(target_path).name,
                home_dir=HOME,
                activate=flags.get("activate") != "false",
            )
        )
        return
    if command == "use-vault":
        emit({"activeVaultPath": set_active_vault(vault_path=flags["path"], home_dir=HOME)})
        return

    active, fallback = require_active_vault()
    if not active:
        emit(fallback)
        return

    if command == "search":
        emit(search_records(vault_path=active["path"], query=" ".join(positionals), limit=int(flags.get("limit", 5))))
        return
    if command == "add-record":
        emit(
            add_record(
                vault_path=active["path"],
                title=flags.get("title", ""),
                content=" ".join(positionals),
                tags=str(flags.get("tags", "")).split(",") if flags.get("tags") else [],
                source=flags.get("source", ""),
            )
        )
        return
    if command == "add-fact":
        emit(
            add_fact(
                vault_path=active["path"],
                subject=flags["subject"],
                predicate=flags["predicate"],
                object_value=flags["object"],
                valid_from=flags.get("valid_from"),
                valid_to=flags.get("valid_to"),
                confidence=float(flags.get("confidence", 1)),
            )
        )
        return
    if command == "add-link":
        emit(
            add_link(
                vault_path=active["path"],
                from_record_id=flags["from"],
                to_record_id=flags["to"],
                label=flags.get("label", ""),
            )
        )
        return
    if command == "journal":
        emit(
            add_journal_entry(
                vault_path=active["path"],
                session_id=flags.get("session", ""),
                entry_type=flags.get("type", "checkpoint"),
                note=" ".join(positionals),
            )
        )
        return
    if command == "query-entity":
        emit(
            query_facts(
                vault_path=active["path"],
                subject=flags["subject"],
                as_of=flags.get("as_of"),
                direction=flags.get("direction", "both"),
            )
        )
        return
    if command == "timeline":
        emit(timeline(vault_path=active["path"], subject=flags.get("subject")))
        return
    if command == "rebuild-index":
        emit(rebuild_index(vault_path=active["path"]))
        return
    if command == "dedup":
        emit(
            dedup_records(
                vault_path=active["path"],
                threshold=float(flags.get("threshold", 0.9)),
                dry_run=flags.get("dry_run") != "false",
            )
        )
        return
    if command == "snapshot":
        emit(export_vault_snapshot(active["path"]))
        return

    emit(vault_status(HOME))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        sys.stderr.write(f"{error}\n")
        sys.exit(1)
