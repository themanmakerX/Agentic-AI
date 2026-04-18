import json
import os
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_HOME = str(Path.home() / ".vault")
GLOBAL_CONFIG_FILE = "config.json"
VAULT_META_DIR = ".vault"

DEFAULT_STATE = {
    "version": 1,
    "activeVaultPath": None,
    "vaults": [],
}

DATA_FILES = {
    "metadata": "vault.json",
    "records": "records.jsonl",
    "facts": "facts.jsonl",
    "links": "links.jsonl",
    "journal": "journal.jsonl",
    "index": "index.json",
}

TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_text(value):
    return (
        str(value or "")
        .strip()
        .lower()
    )


def sanitize_text(value, *, allow_empty=True):
    original = str(value or "")
    ascii_text = (
        unicodedata.normalize("NFKD", original)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    ascii_text = re.sub(r"\s+", " ", ascii_text).strip()
    if not ascii_text and original.strip() and not allow_empty:
        raise ValueError("Only English text is allowed for stored values.")
    return ascii_text


def sanitize_list(values):
    out = []
    for value in values or []:
        cleaned = sanitize_text(value, allow_empty=False)
        if cleaned:
            out.append(cleaned)
    return out


def sanitize_metadata(value):
    if isinstance(value, dict):
        return {str(key): sanitize_metadata(val) for key, val in value.items()}
    if isinstance(value, list):
        return [sanitize_metadata(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value, allow_empty=True)
    return value


def tokenize(value):
    return TOKEN_RE.findall(sanitize_text(value).lower())


def ensure_dir(directory):
    Path(directory).mkdir(parents=True, exist_ok=True)


def read_json(file_path, fallback):
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return fallback


def write_json(file_path, value):
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")


def append_jsonl(file_path, value):
    with open(file_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=True) + "\n")


def read_jsonl(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle.readlines()]
        return [json.loads(line) for line in lines if line]
    except Exception:
        return []


def resolve_global_home(home_dir=DEFAULT_HOME):
    return str(Path(home_dir).expanduser().resolve())


def global_config_path(home_dir=DEFAULT_HOME):
    return str(Path(resolve_global_home(home_dir)) / GLOBAL_CONFIG_FILE)


def default_vault_path():
    return str(Path.home() / "Vault")


def ensure_vault_metadata(vault_root, name):
    meta_dir = Path(vault_root).resolve() / VAULT_META_DIR
    ensure_dir(meta_dir)
    for file_name in DATA_FILES.values():
        file_path = meta_dir / file_name
        if file_path.exists():
            continue
        if file_name.endswith(".json"):
            write_json(file_path, {"rebuiltAt": None} if file_name == DATA_FILES["index"] else {})
        else:
            file_path.write_text("", encoding="utf-8")

    vault_file = meta_dir / DATA_FILES["metadata"]
    existing = read_json(vault_file, None)
    if not existing or not existing.get("id"):
        created_at = now_iso()
        metadata = {
            "id": str(uuid.uuid4()),
            "name": sanitize_text(name or Path(vault_root).name, allow_empty=False),
            "path": str(Path(vault_root).resolve()),
            "createdAt": created_at,
            "lastOpenedAt": created_at,
        }
        write_json(vault_file, metadata)
        return metadata
    return existing


def load_state(home_dir=DEFAULT_HOME):
    root = resolve_global_home(home_dir)
    ensure_dir(root)
    file_path = global_config_path(root)
    state = read_json(file_path, None)
    if not isinstance(state, dict):
        write_json(file_path, DEFAULT_STATE)
        return dict(DEFAULT_STATE)
    return {
        **DEFAULT_STATE,
        **state,
        "vaults": state.get("vaults") if isinstance(state.get("vaults"), list) else [],
    }


def save_state(state, home_dir=DEFAULT_HOME):
    root = resolve_global_home(home_dir)
    ensure_dir(root)
    write_json(global_config_path(root), state)


def list_vaults(home_dir=DEFAULT_HOME):
    state = load_state(home_dir)
    active_path = state.get("activeVaultPath")
    vaults = []
    for vault in state["vaults"]:
        path_value = str(Path(vault["path"]).resolve())
        vaults.append(
            {
                **vault,
                "path": path_value,
                "active": bool(active_path and str(Path(active_path).resolve()) == path_value),
            }
        )
    return sorted(vaults, key=lambda item: str(item.get("name", "")))


def register_vault(*, vault_path, name, home_dir=DEFAULT_HOME, activate=True):
    resolved_vault_path = str(Path(vault_path).expanduser().resolve())
    ensure_dir(resolved_vault_path)
    metadata = ensure_vault_metadata(resolved_vault_path, name)
    state = load_state(home_dir)
    entry = {
        "id": metadata["id"],
        "name": sanitize_text(metadata["name"], allow_empty=False),
        "path": resolved_vault_path,
        "createdAt": metadata["createdAt"],
        "lastOpenedAt": now_iso(),
    }

    existing_index = next(
        (index for index, vault in enumerate(state["vaults"]) if str(Path(vault["path"]).resolve()) == resolved_vault_path),
        None,
    )
    if existing_index is None:
        state["vaults"].append(entry)
    else:
        state["vaults"][existing_index] = {**state["vaults"][existing_index], **entry}

    if activate:
        state["activeVaultPath"] = resolved_vault_path

    save_state(state, home_dir)
    write_json(
        Path(resolved_vault_path) / VAULT_META_DIR / DATA_FILES["metadata"],
        {
            **metadata,
            "name": entry["name"],
            "path": resolved_vault_path,
            "lastOpenedAt": entry["lastOpenedAt"],
        },
    )
    return entry


def choose_vault(*, vault_path, name, home_dir=DEFAULT_HOME):
    return register_vault(vault_path=vault_path, name=name, home_dir=home_dir, activate=True)


def ensure_active_vault(home_dir=DEFAULT_HOME):
    state = load_state(home_dir)
    active_path = state.get("activeVaultPath")
    if not active_path:
        return {"state": state, "active": None}
    active_path = str(Path(active_path).resolve())
    active = next((vault for vault in list_vaults(home_dir) if str(Path(vault["path"]).resolve()) == active_path), None)
    return {"state": state, "active": active}


def get_vault_files(vault_path):
    meta_dir = Path(vault_path).resolve() / VAULT_META_DIR
    return {
        "metaDir": str(meta_dir),
        "metadata": str(meta_dir / DATA_FILES["metadata"]),
        "records": str(meta_dir / DATA_FILES["records"]),
        "facts": str(meta_dir / DATA_FILES["facts"]),
        "links": str(meta_dir / DATA_FILES["links"]),
        "journal": str(meta_dir / DATA_FILES["journal"]),
        "index": str(meta_dir / DATA_FILES["index"]),
    }


def ensure_vault(*, vault_path, name, home_dir=DEFAULT_HOME):
    entry = register_vault(vault_path=vault_path, name=name, home_dir=home_dir, activate=True)
    return {**entry, "files": get_vault_files(entry["path"])}


def get_active_vault(home_dir=DEFAULT_HOME):
    return ensure_active_vault(home_dir)["active"]


def set_active_vault(*, vault_path, home_dir=DEFAULT_HOME):
    state = load_state(home_dir)
    resolved = str(Path(vault_path).expanduser().resolve())
    if not any(str(Path(vault["path"]).resolve()) == resolved for vault in state["vaults"]):
        raise ValueError(f"Vault not registered: {resolved}")
    state["activeVaultPath"] = resolved
    save_state(state, home_dir)
    return resolved


def create_vault(*, vault_path, name, home_dir=DEFAULT_HOME, activate=True):
    entry = register_vault(vault_path=vault_path, name=name, home_dir=home_dir, activate=activate)
    return {**entry, "files": get_vault_files(entry["path"])}


def load_records(vault_path):
    return read_jsonl(get_vault_files(vault_path)["records"])


def load_facts(vault_path):
    return read_jsonl(get_vault_files(vault_path)["facts"])


def load_links(vault_path):
    return read_jsonl(get_vault_files(vault_path)["links"])


def load_journal(vault_path):
    return read_jsonl(get_vault_files(vault_path)["journal"])


def add_record(*, vault_path, title="", content, tags=None, source="", kind="record", metadata=None):
    files = get_vault_files(vault_path)
    created_at = now_iso()
    record = {
        "id": str(uuid.uuid4()),
        "title": sanitize_text(title, allow_empty=True),
        "content": sanitize_text(content, allow_empty=False),
        "tags": sanitize_list(tags or []),
        "source": str(source or "").strip(),
        "kind": sanitize_text(kind, allow_empty=False),
        "createdAt": created_at,
        "updatedAt": created_at,
        "metadata": sanitize_metadata(metadata or {}),
    }
    append_jsonl(files["records"], record)
    return record


def add_journal_entry(*, vault_path, session_id="", entry_type="checkpoint", note="", metadata=None):
    files = get_vault_files(vault_path)
    entry = {
        "id": str(uuid.uuid4()),
        "sessionId": sanitize_text(session_id, allow_empty=True),
        "entryType": sanitize_text(entry_type, allow_empty=False),
        "note": sanitize_text(note, allow_empty=False),
        "metadata": sanitize_metadata(metadata or {}),
        "createdAt": now_iso(),
    }
    append_jsonl(files["journal"], entry)
    return entry


def add_fact(*, vault_path, subject, predicate, object_value, valid_from=None, valid_to=None, confidence=1, source_record_id=None):
    files = get_vault_files(vault_path)
    fact = {
        "id": str(uuid.uuid4()),
        "subject": sanitize_text(subject, allow_empty=False),
        "predicate": sanitize_text(predicate, allow_empty=False),
        "object": sanitize_text(object_value, allow_empty=False),
        "validFrom": str(valid_from).strip() if valid_from else None,
        "validTo": str(valid_to).strip() if valid_to else None,
        "confidence": float(confidence if confidence is not None else 1),
        "sourceRecordId": str(source_record_id).strip() if source_record_id else None,
        "createdAt": now_iso(),
    }
    append_jsonl(files["facts"], fact)
    return fact


def add_link(*, vault_path, from_record_id, to_record_id, label="", source_record_id=None):
    files = get_vault_files(vault_path)
    link = {
        "id": str(uuid.uuid4()),
        "fromRecordId": str(from_record_id).strip(),
        "toRecordId": str(to_record_id).strip(),
        "label": sanitize_text(label, allow_empty=True),
        "sourceRecordId": str(source_record_id).strip() if source_record_id else None,
        "createdAt": now_iso(),
    }
    append_jsonl(files["links"], link)
    return link


def record_snippet(record, max_length=220):
    text = re.sub(r"\s+", " ", str(record.get("content", ""))).strip()
    if not text:
        return ""
    return text if len(text) <= max_length else f"{text[: max_length - 3]}..."


def score_record(query_tokens, record):
    haystack = sanitize_text(
        " ".join([record.get("title", ""), record.get("content", ""), *record.get("tags", []), record.get("source", "")])
    ).lower()
    score = 0.0
    for token in query_tokens:
        if token in haystack:
            score += 2
    if query_tokens and all(token in haystack for token in query_tokens):
        score += 3
    title = sanitize_text(record.get("title", ""))
    if title and any(token in title.lower() for token in query_tokens):
        score += 2
    tags = [sanitize_text(tag).lower() for tag in record.get("tags", [])]
    if tags and any(token in tag for tag in tags for token in query_tokens):
        score += 1
    try:
        created = datetime.fromisoformat(str(record["createdAt"]).replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - created).total_seconds() / 86400
        score += max(0, 1 - age_days / 365)
    except Exception:
        pass
    return score


def search_records(*, vault_path, query="", limit=5, kind=None, tag=None):
    records = load_records(vault_path)
    query_tokens = tokenize(query)
    filtered = []
    for record in records:
        if kind and record.get("kind") != kind:
            continue
        if tag and sanitize_text(tag).lower() not in [sanitize_text(item).lower() for item in record.get("tags", [])]:
            continue
        filtered.append(record)

    results = []
    for record in filtered:
        candidate = dict(record)
        candidate["score"] = score_record(query_tokens, record) if query_tokens else 0
        candidate["preview"] = record_snippet(record)
        results.append(candidate)

    results.sort(
        key=lambda item: (
            -(item["score"] if query_tokens else 0),
            -datetime.fromisoformat(str(item["createdAt"]).replace("Z", "+00:00")).timestamp(),
        )
    )
    return results[: max(1, int(limit or 5))]


def query_facts(*, vault_path, subject, as_of=None, direction="both"):
    facts = load_facts(vault_path)
    needle = sanitize_text(subject).lower()
    out = []
    for fact in facts:
        subject_hit = needle in sanitize_text(fact.get("subject", "")).lower()
        object_hit = needle in sanitize_text(fact.get("object", "")).lower()
        matches_direction = (
            direction == "both"
            or (direction == "outgoing" and subject_hit)
            or (direction == "incoming" and object_hit)
        )
        if not matches_direction:
            continue
        if as_of:
            try:
                as_of_time = datetime.fromisoformat(str(as_of).replace("Z", "+00:00"))
                from_ok = not fact.get("validFrom") or datetime.fromisoformat(str(fact["validFrom"]).replace("Z", "+00:00")) <= as_of_time
                to_ok = not fact.get("validTo") or datetime.fromisoformat(str(fact["validTo"]).replace("Z", "+00:00")) >= as_of_time
                if not (from_ok and to_ok):
                    continue
            except Exception:
                continue
        out.append(fact)
    return out


def timeline(*, vault_path, subject=None):
    facts = load_facts(vault_path)
    if subject:
        needle = sanitize_text(subject).lower()
        items = [
            fact
            for fact in facts
            if needle in sanitize_text(fact.get("subject", "")).lower()
            or needle in sanitize_text(fact.get("object", "")).lower()
        ]
    else:
        items = facts
    return sorted(
        items,
        key=lambda item: datetime.fromisoformat(str(item.get("validFrom") or item.get("createdAt")).replace("Z", "+00:00")).timestamp(),
    )


def rebuild_index(*, vault_path):
    files = get_vault_files(vault_path)
    records = load_records(vault_path)
    index = {
        "rebuiltAt": now_iso(),
        "recordCount": len(records),
        "entries": [
            {
                "id": record.get("id"),
                "title": record.get("title"),
                "tags": record.get("tags"),
                "tokens": tokenize(" ".join([record.get("title", ""), record.get("content", ""), *record.get("tags", [])]))[:80],
            }
            for record in records
        ],
    }
    write_json(files["index"], index)
    return index


def dedup_records(*, vault_path, threshold=0.9, dry_run=True):
    files = get_vault_files(vault_path)
    records = load_records(vault_path)
    groups = {}
    for record in records:
        key = record.get("source") or "global"
        groups.setdefault(key, []).append(record)

    kept = []
    removed = []

    def jaccard(a, b):
        set_a = set(tokenize(a))
        set_b = set(tokenize(b))
        if not set_a or not set_b:
            return 0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return (intersection / union) if union else 0

    for items in groups.values():
        bucket = []
        for record in sorted(items, key=lambda item: len(str(item.get("content", ""))), reverse=True):
            duplicate = next(
                (candidate for candidate in bucket if jaccard(candidate.get("content", ""), record.get("content", "")) >= threshold),
                None,
            )
            if duplicate:
                removed.append(record)
            else:
                bucket.append(record)
        kept.extend(bucket)

    if not dry_run:
        with open(files["records"], "w", encoding="utf-8") as handle:
            for record in kept:
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    return {
        "kept": len(kept),
        "removed": len(removed),
        "removedRecords": [
            {
                "id": record.get("id"),
                "title": record.get("title"),
                "source": record.get("source"),
                "preview": record_snippet(record),
            }
            for record in removed
        ],
    }


def vault_status(home_dir=DEFAULT_HOME):
    state = load_state(home_dir)
    vaults = list_vaults(home_dir)
    active = next(
        (vault for vault in vaults if str(Path(vault["path"]).resolve()) == str(Path(state.get("activeVaultPath") or "").resolve())),
        None,
    )
    if not active:
        return {
            "needsSetup": True,
            "message": "No active Vault is configured. Ask the user for a vault location or create one.",
            "homeDir": resolve_global_home(home_dir),
            "vaults": vaults,
        }

    return {
        "needsSetup": False,
        "homeDir": resolve_global_home(home_dir),
        "activeVault": active,
        "vaults": vaults,
        "counts": {
            "records": len(load_records(active["path"])),
            "facts": len(load_facts(active["path"])),
            "links": len(load_links(active["path"])),
            "journalEntries": len(load_journal(active["path"])),
        },
    }


def export_vault_snapshot(vault_path):
    files = get_vault_files(vault_path)
    return {
        "metadata": read_json(files["metadata"], {}),
        "records": load_records(vault_path),
        "facts": load_facts(vault_path),
        "links": load_links(vault_path),
        "journal": load_journal(vault_path),
    }
