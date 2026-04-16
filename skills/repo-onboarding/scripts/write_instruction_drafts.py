from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from shutil import copy2

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from scan_repo import ScanResult, ScopeCandidate, scan_repo  # noqa: E402

def doc_name_for_mode(mode: str) -> str:
    return "AGENTS.md" if mode == "codex" else "CLAUDE.md"

def root_doc_name(result: ScanResult, mode: str) -> str:
    if mode == "auto":
        if any(path == "CLAUDE.md" or path.endswith("/CLAUDE.md") for path in result.instruction_files):
            return "CLAUDE.md"
        if any(path == "AGENTS.md" or path.endswith("/AGENTS.md") for path in result.instruction_files):
            return "AGENTS.md"
        return "CLAUDE.md"
    return doc_name_for_mode(mode)

def scope_doc_name(result: ScanResult, scope: str, mode: str) -> str:
    preferred = root_doc_name(result, mode)
    for instruction in result.instruction_files:
        if scope == "." and "/" not in instruction:
            return Path(instruction).name if mode == "auto" else preferred
        if scope != "." and instruction.startswith(f"{scope}/"):
            return Path(instruction).name if mode == "auto" else preferred
    return preferred

def render_scope(result: ScanResult, candidate: ScopeCandidate) -> str:
    lines = [
        f"# {result.repo_name if candidate.path == '.' else candidate.path}",
        "",
        f"This file covers `{candidate.path}` and should stay local to that scope.",
        "",
        "## Scope",
        "",
        f"- reason: {candidate.reason}",
        f"- evidence: {', '.join(candidate.signals) if candidate.signals else 'none'}",
        "",
        "## Guidance",
        "",
        "- Keep guidance local to this scope.",
        "- Record uncertainties instead of inventing rules.",
        "- Refer upward for repo-wide conventions.",
        "- Derive commands from evidence files only; do not guess tool syntax.",
    ]
    if candidate.path != ".":
        lines.extend([
            "",
            "## Parent",
            "",
            "- follow the root instruction file for repo-wide rules",
            "",
            "## Children",
            "",
            f"- inspect nested paths under `{candidate.path}/` for additional guidance",
        ])
    return "\n".join(lines).rstrip() + "\n"

def backup_target(target: Path, backup_root: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    relative = target.relative_to(target.anchor) if target.is_absolute() else target
    backup_path = backup_root / f"{relative.as_posix().replace('/', '_')}.{stamp}.bak"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    copy2(target, backup_path)
    return backup_path

def main() -> int:
    parser = argparse.ArgumentParser(description="Write draft AGENTS/CLAUDE instruction files from a repository scan.")
    parser.add_argument("--root", required=True, help="Repository root to scan")
    parser.add_argument("--output-dir", required=True, help="Directory to write draft files into")
    parser.add_argument("--max-depth", type=int, default=4, help="Maximum directory depth to inspect")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing draft files")
    parser.add_argument("--backup-dir", default=".repo-onboarding-backups", help="Directory to store backups before overwrite")
    parser.add_argument("--mode", choices=["auto", "claude", "codex"], default="auto", help="Instruction-file convention to generate")
    parser.add_argument("--json", action="store_true", help="Emit a JSON summary of generated drafts")
    parser.add_argument("--instruction-names", default="AGENTS.md,CLAUDE.md", help="Comma-separated instruction file names")
    parser.add_argument("--task-files", default="Taskfile.yml,Taskfile.yaml", help="Comma-separated task entrypoint file names")
    parser.add_argument("--build-files", default="Makefile,makefile,package.json,pyproject.toml,go.mod,Cargo.toml,pom.xml,build.gradle,build.gradle.kts,tsconfig.json", help="Comma-separated build entrypoint file names")
    parser.add_argument("--exclude-dirs", default=".git,node_modules,vendor,__pycache__,.venv,.tox,.mypy_cache,.pytest_cache,dist,build,.next,.turbo,.cache", help="Comma-separated directory names to exclude")
    args = parser.parse_args()

    instruction_names = {item.strip() for item in args.instruction_names.split(",") if item.strip()}
    task_files = {item.strip() for item in args.task_files.split(",") if item.strip()}
    build_files = {item.strip() for item in args.build_files.split(",") if item.strip()}
    excludes = {item.strip() for item in args.exclude_dirs.split(",") if item.strip()}

    result = scan_repo(Path(args.root).resolve(), args.max_depth, instruction_names, task_files, build_files, excludes)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = output_dir / args.backup_dir

    generated: list[str] = []
    for candidate in result.scope_candidates:
        doc_name = scope_doc_name(result, candidate.path, args.mode)
        target_dir = output_dir if candidate.path == "." else output_dir / candidate.path
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / doc_name
        if target.exists() and not args.overwrite:
            continue
        if target.exists() and args.overwrite:
            backup_target(target, backup_dir)
        target.write_text(render_scope(result, candidate), encoding="utf-8")
        generated.append(str(target.relative_to(output_dir)))

    summary = {
        "root": str(Path(args.root).resolve()),
        "output_dir": str(output_dir),
        "generated": generated,
        "source_of_truth": root_doc_name(result, args.mode),
        "mode": args.mode,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Generated {len(generated)} draft files into {output_dir}")
        for item in generated:
            print(f"- {item}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
