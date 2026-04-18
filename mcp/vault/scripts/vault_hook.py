import json
import os
import re
import sys
from pathlib import Path

from vault_core import (
    DEFAULT_HOME,
    add_journal_entry,
    add_record,
    ensure_active_vault,
    vault_status,
)


HOME = str(Path(os.environ.get("VAULT_HOME", DEFAULT_HOME)).expanduser().resolve())


def read_stdin():
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def session_id(input_data):
    value = str(
        input_data.get("session_id")
        or input_data.get("sessionId")
        or input_data.get("session")
        or "unknown"
    )
    return re.sub(r"[^a-zA-Z0-9_-]", "", value)


def transcript_to_text(transcript_path):
    if not transcript_path:
        return ""
    file_path = Path(transcript_path).expanduser().resolve()
    if not file_path.exists():
        return ""
    raw = file_path.read_text(encoding="utf-8")
    if file_path.suffix.lower() in {".jsonl", ".json"}:
        snippets = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = (
                entry.get("message", {}).get("content")
                or entry.get("payload", {}).get("message")
                or entry.get("text")
            )
            if isinstance(text, str) and text.strip():
                snippets.append(text.strip())
        return "\n".join(snippets[-40:])
    return raw


def emit(payload):
    sys.stdout.write(json.dumps(payload) + "\n")


def run():
    command = sys.argv[1] if len(sys.argv) > 1 else "session-start"
    input_data = read_stdin()
    active = ensure_active_vault(HOME)

    if not active["active"]:
        emit(vault_status(HOME))
        return

    sid = session_id(input_data)
    transcript_path = input_data.get("transcript_path") or input_data.get("transcriptPath") or ""
    transcript = transcript_to_text(transcript_path)
    title = input_data.get("title") or input_data.get("session_title") or f"{command} checkpoint"
    note = input_data.get("note") or f"{command} for {sid}"

    if transcript:
        add_record(
            vault_path=active["active"]["path"],
            title=title,
            content=transcript,
            tags=["hook", command],
            source=transcript_path,
            kind="hook-transcript",
            metadata={"sessionId": sid, "hook": command},
        )

    add_journal_entry(
        vault_path=active["active"]["path"],
        session_id=sid,
        entry_type=command,
        note=note,
        metadata={"transcriptPath": transcript_path},
    )

    emit(
        {
            "ok": True,
            "command": command,
            "sessionId": sid,
            "wroteTranscript": bool(transcript),
            "vault": active["active"]["name"],
        }
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        emit({"ok": False, "error": str(error)})
        sys.exit(1)
