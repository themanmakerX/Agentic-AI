"""Language-aware source parsing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import re


EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
}


@dataclass(slots=True)
class ParsedFile:
    path: Path
    language: str
    sha256: str
    symbols: list[tuple[str, str, int, int]]
    edges: list[tuple[str, str, str]]


def detect_language(path: Path) -> str:
    return EXTENSION_TO_LANGUAGE.get(path.suffix.lower(), "text")


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_file(root: Path, path: Path) -> ParsedFile:
    text = path.read_text(encoding="utf-8", errors="ignore")
    language = detect_language(path)
    file_id = path.relative_to(root).as_posix()
    symbols: list[tuple[str, str, int, int]] = []
    edges: list[tuple[str, str, str]] = []

    if language == "python":
        symbols.extend(_parse_python_symbols(text))
        edges.extend(_parse_python_import_edges(text, file_id))
    else:
        symbols.extend(_parse_generic_symbols(text))
        edges.extend(_parse_generic_import_edges(text, file_id))

    return ParsedFile(
        path=path,
        language=language,
        sha256=sha256_text(text),
        symbols=symbols,
        edges=edges,
    )


def _parse_python_symbols(text: str) -> list[tuple[str, str, int, int]]:
    symbols: list[tuple[str, str, int, int]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        if match := re.match(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)", line):
            symbols.append((match.group(1), "class", index, index))
        if match := re.match(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)", line):
            symbols.append((match.group(1), "function", index, index))
    return symbols


def _parse_python_import_edges(text: str, file_id: str) -> list[tuple[str, str, str]]:
    edges: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        if match := re.match(r"^\s*import\s+([A-Za-z0-9_\.]+)", line):
            edges.append((file_id, match.group(1), "import"))
        if match := re.match(r"^\s*from\s+([A-Za-z0-9_\.]+)\s+import\s+", line):
            edges.append((file_id, match.group(1), "import"))
    return edges


def _parse_generic_symbols(text: str) -> list[tuple[str, str, int, int]]:
    symbols: list[tuple[str, str, int, int]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        if match := re.match(r"^\s*(class|function|def)\s+([A-Za-z_][A-Za-z0-9_]*)", line):
            kind = "class" if match.group(1) == "class" else "function"
            symbols.append((match.group(2), kind, index, index))
    return symbols


def _parse_generic_import_edges(text: str, file_id: str) -> list[tuple[str, str, str]]:
    edges: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        if match := re.search(r"from\s+['\"]([^'\"]+)['\"]", line):
            edges.append((file_id, match.group(1), "import"))
        if match := re.search(r"import\s+['\"]([^'\"]+)['\"]", line):
            edges.append((file_id, match.group(1), "import"))
    return edges

