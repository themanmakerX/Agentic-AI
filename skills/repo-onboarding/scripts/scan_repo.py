from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

DEFAULT_INSTRUCTION_NAMES = {"AGENTS.md", "CLAUDE.md"}
DEFAULT_TASK_FILES = {"Taskfile.yml", "Taskfile.yaml"}
DEFAULT_BUILD_FILES = {
    "Makefile",
    "makefile",
    "package.json",
    "pyproject.toml",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "tsconfig.json",
}
DEFAULT_EXCLUDES = {
    ".git",
    "node_modules",
    "vendor",
    "__pycache__",
    ".venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".next",
    ".turbo",
    ".cache",
}

@dataclass
class ScopeCandidate:
    path: str
    reason: str
    signals: list[str] = field(default_factory=list)

@dataclass
class ScanResult:
    root: str
    repo_name: str
    top_level_dirs: list[str]
    instruction_files: list[str]
    task_files: list[str]
    build_files: list[str]
    excluded_dirs: list[str]
    scope_candidates: list[ScopeCandidate]
    unknowns: list[str]

def parse_csv(raw: str, defaults: set[str]) -> set[str]:
    items = {item.strip() for item in raw.split(",") if item.strip()}
    return items or set(defaults)

def iter_paths(root: Path, max_depth: int) -> Iterable[Path]:
    for path in root.rglob("*"):
        if len(path.relative_to(root).parts) > max_depth:
            continue
        yield path

def is_excluded(path: Path, excludes: set[str]) -> bool:
    return any(part in excludes for part in path.parts)

def scan_repo(root: Path, max_depth: int, instruction_names: set[str], task_files: set[str], build_files: set[str], excludes: set[str]) -> ScanResult:
    instruction_hits: list[str] = []
    task_hits: list[str] = []
    build_hits: list[str] = []
    excluded_dirs: set[str] = set()
    top_level_dirs: set[str] = set()
    candidate_map: dict[str, ScopeCandidate] = {}
    unknowns: list[str] = []

    for path in iter_paths(root, max_depth):
        if is_excluded(path, excludes):
            excluded_dirs.update(part for part in path.parts if part in excludes)
            continue
        rel = path.relative_to(root)
        if path.is_dir() and rel.parts:
            top_level_dirs.add(rel.parts[0])
        if not path.is_file():
            continue
        rel_text = rel.as_posix()
        name = path.name
        if name in instruction_names:
            instruction_hits.append(rel_text)
            scope = rel.parts[0] if len(rel.parts) > 1 else "."
            candidate_map.setdefault(scope, ScopeCandidate(path=scope, reason="existing instruction file")).signals.append(rel_text)
        if name in task_files:
            task_hits.append(rel_text)
            scope = rel.parts[0] if len(rel.parts) > 1 else "."
            candidate_map.setdefault(scope, ScopeCandidate(path=scope, reason="task entrypoint")).signals.append(name)
        if name in build_files:
            build_hits.append(rel_text)
            scope = rel.parts[0] if len(rel.parts) > 1 else "."
            candidate_map.setdefault(scope, ScopeCandidate(path=scope, reason="build entrypoint")).signals.append(name)

    if not instruction_hits:
        unknowns.append("No existing AGENTS.md or CLAUDE.md files found")
    if not task_hits:
        unknowns.append("No task entrypoint file discovered")
    if not build_hits:
        unknowns.append("No obvious build manifest discovered")

    for top_level_dir in top_level_dirs:
        if top_level_dir not in candidate_map and top_level_dir not in excluded_dirs:
            candidate_map[top_level_dir] = ScopeCandidate(path=top_level_dir, reason="uncovered top-level directory")

    scope_candidates = sorted(candidate_map.values(), key=lambda candidate: candidate.path)
    return ScanResult(root=str(root), repo_name=root.name, top_level_dirs=sorted(top_level_dirs), instruction_files=sorted(instruction_hits), task_files=sorted(task_hits), build_files=sorted(build_hits), excluded_dirs=sorted(excluded_dirs), scope_candidates=scope_candidates, unknowns=unknowns)

def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a repository for onboarding and instruction-tree generation.")
    parser.add_argument("--root", required=True, help="Repository root to scan")
    parser.add_argument("--max-depth", type=int, default=4, help="Maximum directory depth to inspect")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--instruction-names", default=",".join(sorted(DEFAULT_INSTRUCTION_NAMES)), help="Comma-separated instruction file names")
    parser.add_argument("--task-files", default=",".join(sorted(DEFAULT_TASK_FILES)), help="Comma-separated task entrypoint file names")
    parser.add_argument("--build-files", default=",".join(sorted(DEFAULT_BUILD_FILES)), help="Comma-separated build entrypoint file names")
    parser.add_argument("--exclude-dirs", default=",".join(sorted(DEFAULT_EXCLUDES)), help="Comma-separated directory names to exclude")
    args = parser.parse_args()

    instruction_names = parse_csv(args.instruction_names, DEFAULT_INSTRUCTION_NAMES)
    task_files = parse_csv(args.task_files, DEFAULT_TASK_FILES)
    build_files = parse_csv(args.build_files, DEFAULT_BUILD_FILES)
    excludes = parse_csv(args.exclude_dirs, DEFAULT_EXCLUDES)

    result = scan_repo(Path(args.root).resolve(), args.max_depth, instruction_names, task_files, build_files, excludes)
    payload = asdict(result)
    payload["scope_candidates"] = [asdict(candidate) for candidate in result.scope_candidates]

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Repository: {result.repo_name}")
        print(f"Top-level dirs: {', '.join(result.top_level_dirs) or '(none)'}")
        print(f"Instruction files: {', '.join(result.instruction_files) or '(none)'}")
        print(f"Task files: {', '.join(result.task_files) or '(none)'}")
        print(f"Build files: {', '.join(result.build_files) or '(none)'}")
        print(f"Excluded dirs: {', '.join(result.excluded_dirs) or '(none)'}")
        print("Scope candidates:")
        for candidate in result.scope_candidates:
            signals = ', '.join(candidate.signals) if candidate.signals else 'none'
            print(f"- {candidate.path}: {candidate.reason} [{signals}]")
        if result.unknowns:
            print("Unknowns:")
            for item in result.unknowns:
                print(f"- {item}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
