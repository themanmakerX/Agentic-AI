from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from ..incremental import IncrementalIndexer
from ..languages import LanguageDefinition, build_default_registry
from ..parser import EdgeRecord, GraphParser, ParseDiagnostic, ParseResult, ParserBackend, SymbolRecord
from ..storage import SQLiteGraphStore


@dataclass(frozen=True, slots=True)
class BuildSummary:
    files_scanned: int
    nodes_indexed: int
    edges_indexed: int
    diagnostics: tuple[ParseDiagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class UpdateSummary:
    files_changed: int
    files_added: int
    files_modified: int
    files_deleted: int
    files_skipped: int
    diagnostics: tuple[ParseDiagnostic, ...] = ()


class HeuristicBackend(ParserBackend):
    """Fallback backend for environments without Tree-sitter grammars installed."""

    def parse(self, *, path: Path, source: bytes, language: LanguageDefinition):
        return _HeuristicSyntaxTree(source=source, path=path, language_id=language.language_id)


class _HeuristicSyntaxTree:
    def __init__(self, *, source: bytes, path: Path, language_id: str) -> None:
        self.source = source
        self.path = path
        self.language_id = language_id


class _HeuristicExtractor:
    def extract(self, *, path: Path, language: LanguageDefinition, root, source: bytes):
        text = source.decode("utf-8", errors="ignore")
        symbols, edges = _extract_language_aware_symbols_and_edges(language.language_id, text)
        return tuple(symbols), tuple(edges), ()


def build_graph(root: Path, db_path: Path, progress_callback=None) -> BuildSummary:
    store = SQLiteGraphStore(db_path)
    parser = GraphParser(backend=HeuristicBackend(), extractor=_HeuristicExtractor())
    indexer = IncrementalIndexer(registry=build_default_registry(), parser=parser, store=store)
    result = indexer.update(root, progress_callback=progress_callback)
    stats = store.stats()
    store.close()
    return BuildSummary(
        files_scanned=result.scanned_files,
        nodes_indexed=stats["symbols"],
        edges_indexed=stats["edges"],
        diagnostics=result.diagnostics,
    )


def update_graph(root: Path, db_path: Path, progress_callback=None) -> UpdateSummary:
    store = SQLiteGraphStore(db_path)
    parser = GraphParser(backend=HeuristicBackend(), extractor=_HeuristicExtractor())
    indexer = IncrementalIndexer(registry=build_default_registry(), parser=parser, store=store)
    result = indexer.update(root, progress_callback=progress_callback)
    store.close()
    return UpdateSummary(
        files_changed=result.added_files + result.modified_files + result.deleted_files,
        files_added=result.added_files,
        files_modified=result.modified_files,
        files_deleted=result.deleted_files,
        files_skipped=result.skipped_files,
        diagnostics=result.diagnostics,
    )


def _extract_python_symbols(text: str) -> list[SymbolRecord]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _extract_python_symbols_from_lines(text)

    symbols: list[SymbolRecord] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(
                SymbolRecord(
                    kind="function" if isinstance(node, ast.FunctionDef) else "async_function",
                    name=node.name,
                    qualified_name=node.name,
                    span=None,
                    metadata={"line": getattr(node, "lineno", None), "language": "python"},
                )
            )
        elif isinstance(node, ast.ClassDef):
            symbols.append(
                SymbolRecord(
                    kind="class",
                    name=node.name,
                    qualified_name=node.name,
                    span=None,
                    metadata={"line": getattr(node, "lineno", None), "language": "python"},
                )
            )
        elif isinstance(node, ast.Import):
            continue
        elif isinstance(node, ast.ImportFrom):
            continue
    return symbols


def _extract_python_symbols_from_lines(text: str) -> list[SymbolRecord]:
    symbols: list[SymbolRecord] = []
    lines = text.splitlines()
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("class ") or stripped.startswith("def ") or stripped.startswith("async def "):
            head = stripped.split("(", 1)[0]
            kind = "class" if head.startswith("class ") else "async_function" if head.startswith("async def ") else "function"
            name = head.split()[1].rstrip(":")
            symbols.append(
                SymbolRecord(
                    kind=kind,
                    name=name,
                    qualified_name=name,
                    span=None,
                    metadata={"line": line_no, "language": "python"},
                )
            )
    return symbols


def _extract_python_imports(text: str) -> list[EdgeRecord]:
    edges: list[EdgeRecord] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("import "):
            modules = [module.strip() for module in stripped[len("import ") :].split(",")]
            for module in modules:
                if module:
                    edges.append(EdgeRecord(kind="imports", target_ref=module, metadata={"syntax": "import"}))
        elif stripped.startswith("from ") and " import " in stripped:
            module = stripped.split(" import ", 1)[0].removeprefix("from ").strip()
            if module:
                edges.append(EdgeRecord(kind="imports", target_ref=module, metadata={"syntax": "from_import"}))
    return edges


def _extract_language_aware_symbols_and_edges(language_id: str, text: str) -> tuple[list[SymbolRecord], list[EdgeRecord]]:
    symbols: list[SymbolRecord] = []
    edges: list[EdgeRecord] = []

    if language_id == "python":
        symbols.extend(_extract_python_symbols(text))
        edges.extend(_extract_python_imports(text))
        return symbols, edges

    lines = text.splitlines()
    if language_id in {"javascript", "typescript", "tsx", "jsx"}:
        symbols.extend(_extract_js_like_symbols(lines, language_id))
        edges.extend(_extract_js_like_imports(lines))
        return symbols, edges

    if language_id == "go":
        symbols.extend(_extract_go_symbols(lines))
        edges.extend(_extract_go_imports(lines))
        return symbols, edges

    if language_id == "java":
        symbols.extend(_extract_java_symbols(lines))
        edges.extend(_extract_java_imports(lines))
        return symbols, edges

    if language_id == "rust":
        symbols.extend(_extract_rust_symbols(lines))
        edges.extend(_extract_rust_imports(lines))
        return symbols, edges

    if language_id in {"c", "cpp"}:
        symbols.extend(_extract_c_family_symbols(lines, language_id))
        edges.extend(_extract_c_family_imports(lines, language_id))
        return symbols, edges

    if language_id == "systemverilog":
        symbols.extend(_extract_systemverilog_symbols(lines))
        edges.extend(_extract_systemverilog_imports(lines))
        return symbols, edges

    if language_id == "html":
        symbols.extend(_extract_html_symbols(lines))
        edges.extend(_extract_html_imports(lines))
        return symbols, edges

    if language_id == "css":
        symbols.extend(_extract_css_symbols(lines))
        edges.extend(_extract_css_imports(lines))
        return symbols, edges

    if language_id == "sql":
        symbols.extend(_extract_sql_symbols(lines))
        edges.extend(_extract_sql_imports(lines))
        return symbols, edges

    if language_id == "ruby":
        symbols.extend(_extract_ruby_symbols(lines))
        edges.extend(_extract_ruby_imports(lines))
        return symbols, edges

    symbols.extend(_extract_generic_symbols(lines))
    edges.extend(_extract_generic_imports(lines))
    return symbols, edges


def _extract_generic_symbols(lines: list[str]) -> list[SymbolRecord]:
    symbols: list[SymbolRecord] = []
    patterns = [
        re.compile(r"^\s*(?:export\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
        re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*(?:export\s+)?module\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*(?:export\s+)?struct\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*(?:export\s+)?namespace\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?(?:function\s*)?\("),
        re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?[A-Za-z_][A-Za-z0-9_]*\s*=>"),
        re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
        re.compile(r"^\s*(?:export\s+)?enum\s+([A-Za-z_][A-Za-z0-9_]*)\b"),
    ]
    for line_no, line in enumerate(lines, start=1):
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                symbols.append(
                    SymbolRecord(
                        kind="symbol",
                        name=match.group(1),
                        qualified_name=match.group(1),
                        span=None,
                        metadata={"line": line_no},
                    )
                )
                break
    return symbols


def _extract_generic_imports(lines: list[str]) -> list[EdgeRecord]:
    edges: list[EdgeRecord] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import "):
            for part in stripped[len("import ") :].split(","):
                module = part.strip().split(" as ", 1)[0]
                if module:
                    edges.append(EdgeRecord(kind="imports", target_ref=module))
        elif stripped.startswith("from ") and " import " in stripped:
            module = stripped.split(" import ", 1)[0].removeprefix("from ").strip()
            if module:
                edges.append(EdgeRecord(kind="imports", target_ref=module))
        elif stripped.startswith("#include"):
            match = re.search(r'["<]([^">]+)[">]', stripped)
            if match:
                edges.append(EdgeRecord(kind="imports", target_ref=match.group(1)))
        elif stripped.startswith("require ") or stripped.startswith("require_relative ") or stripped.startswith("load "):
            match = re.search(r'["\']([^"\']+)["\']', stripped)
            if match:
                edges.append(EdgeRecord(kind="imports", target_ref=match.group(1)))
    return edges


def _extract_js_like_symbols(lines: list[str], language_id: str) -> list[SymbolRecord]:
    symbols: list[SymbolRecord] = []
    patterns = [
        (re.compile(r"^\s*(?:export\s+(?:default\s+)?)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\("), "function"),
        (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][A-Za-z0-9_$]*)\b"), "class"),
        (re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?(?:function\s*)?\("), "function"),
        (re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?[A-Za-z_$][A-Za-z0-9_$]*\s*=>"), "function"),
        (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?interface\s+([A-Za-z_$][A-Za-z0-9_$]*)\b"), "interface"),
        (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?type\s+([A-Za-z_$][A-Za-z0-9_$]*)\b"), "type"),
        (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?enum\s+([A-Za-z_$][A-Za-z0-9_$]*)\b"), "enum"),
    ]
    for line_no, line in enumerate(lines, start=1):
        for pattern, kind in patterns:
            match = pattern.search(line)
            if match:
                symbols.append(
                    SymbolRecord(
                        kind=kind,
                        name=match.group(1),
                        qualified_name=match.group(1),
                        span=None,
                        metadata={"line": line_no, "language": language_id},
                    )
                )
                break
    return symbols


def _extract_js_like_imports(lines: list[str]) -> list[EdgeRecord]:
    edges: list[EdgeRecord] = []
    import_patterns = [
        re.compile(r"^\s*import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]"),
        re.compile(r"^\s*import\s+['\"]([^'\"]+)['\"]"),
        re.compile(r"^\s*export\s+\*\s+from\s+['\"]([^'\"]+)['\"]"),
    ]
    for line in lines:
        for pattern in import_patterns:
            match = pattern.search(line)
            if match:
                edges.append(EdgeRecord(kind="imports", target_ref=match.group(1), metadata={"syntax": "ecmascript"}))
                break
    return edges


def _extract_go_symbols(lines: list[str]) -> list[SymbolRecord]:
    symbols: list[SymbolRecord] = []
    patterns = [
        (re.compile(r"^\s*func\s+(?:\([^)]+\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\("), "function"),
        (re.compile(r"^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\s+(?:struct|interface|type)\b"), "type"),
        (re.compile(r"^\s*const\s+([A-Za-z_][A-Za-z0-9_]*)\b"), "const"),
        (re.compile(r"^\s*var\s+([A-Za-z_][A-Za-z0-9_]*)\b"), "var"),
    ]
    for line_no, line in enumerate(lines, start=1):
        for pattern, kind in patterns:
            match = pattern.search(line)
            if match:
                symbols.append(
                    SymbolRecord(
                        kind=kind,
                        name=match.group(1),
                        qualified_name=match.group(1),
                        span=None,
                        metadata={"line": line_no, "language": "go"},
                    )
                )
                break
    return symbols


def _extract_go_imports(lines: list[str]) -> list[EdgeRecord]:
    edges: list[EdgeRecord] = []
    import_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import ("):
            import_block = True
            continue
        if import_block and stripped == ")":
            import_block = False
            continue
        if import_block:
            match = re.search(r'["`]([^"`]+)["`]', stripped)
            if match:
                edges.append(EdgeRecord(kind="imports", target_ref=match.group(1), metadata={"syntax": "go_block"}))
            continue
        if stripped.startswith("import "):
            match = re.search(r'["`]([^"`]+)["`]', stripped)
            if match:
                edges.append(EdgeRecord(kind="imports", target_ref=match.group(1), metadata={"syntax": "go_single"}))
    return edges


def _extract_java_symbols(lines: list[str]) -> list[SymbolRecord]:
    symbols: list[SymbolRecord] = []
    class_pattern = re.compile(r"^\s*(?:public\s+|protected\s+|private\s+)?(?:final\s+|abstract\s+)?(?:class|interface|enum|record)\s+([A-Za-z_][A-Za-z0-9_]*)\b")
    method_pattern = re.compile(
        r"^\s*(?:public|protected|private|static|final|abstract|synchronized|native|strictfp|\s)+[A-Za-z0-9_<>\[\], ?]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("
    )
    for line_no, line in enumerate(lines, start=1):
        match = class_pattern.search(line)
        if match:
            symbols.append(
                SymbolRecord(
                    kind="type",
                    name=match.group(1),
                    qualified_name=match.group(1),
                    span=None,
                    metadata={"line": line_no, "language": "java"},
                )
            )
            continue
        match = method_pattern.search(line)
        if match and match.group(1) not in {"if", "for", "while", "switch", "catch"}:
            symbols.append(
                SymbolRecord(
                    kind="method",
                    name=match.group(1),
                    qualified_name=match.group(1),
                    span=None,
                    metadata={"line": line_no, "language": "java"},
                )
            )
    return symbols


def _extract_java_imports(lines: list[str]) -> list[EdgeRecord]:
    edges: list[EdgeRecord] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import "):
            module = stripped[len("import ") :].rstrip(";").strip()
            if module:
                edges.append(EdgeRecord(kind="imports", target_ref=module, metadata={"syntax": "java"}))
    return edges


def _extract_rust_symbols(lines: list[str]) -> list[SymbolRecord]:
    symbols: list[SymbolRecord] = []
    patterns = [
        (re.compile(r"^\s*(?:pub\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("), "function"),
        (re.compile(r"^\s*(?:pub\s+)?(?:struct|enum|trait|type)\s+([A-Za-z_][A-Za-z0-9_]*)\b"), "type"),
        (re.compile(r"^\s*impl(?:<[^>]+>)?\s+([A-Za-z_][A-Za-z0-9_]*)"), "impl"),
    ]
    for line_no, line in enumerate(lines, start=1):
        for pattern, kind in patterns:
            match = pattern.search(line)
            if match:
                symbols.append(
                    SymbolRecord(
                        kind=kind,
                        name=match.group(1),
                        qualified_name=match.group(1),
                        span=None,
                        metadata={"line": line_no, "language": "rust"},
                    )
                )
                break
    return symbols


def _extract_rust_imports(lines: list[str]) -> list[EdgeRecord]:
    edges: list[EdgeRecord] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("use "):
            target = stripped[len("use ") :].rstrip(";").strip()
            if target:
                edges.append(EdgeRecord(kind="imports", target_ref=target, metadata={"syntax": "rust_use"}))
        elif stripped.startswith("mod "):
            target = stripped[len("mod ") :].rstrip(";").strip()
            if target:
                edges.append(EdgeRecord(kind="imports", target_ref=target, metadata={"syntax": "rust_mod"}))
    return edges


def _extract_c_family_symbols(lines: list[str], language_id: str) -> list[SymbolRecord]:
    symbols: list[SymbolRecord] = []
    patterns = [
        (re.compile(r"^\s*(?:template\s*<[^>]+>\s*)?(?:class|struct|enum(?:\s+class|\s+struct)?|namespace)\s+([A-Za-z_][A-Za-z0-9_]*)\b"), "type"),
        (re.compile(r"^\s*(?:static\s+|inline\s+|virtual\s+|constexpr\s+|extern\s+|friend\s+|typename\s+|unsigned\s+|signed\s+|const\s+|volatile\s+|mutable\s+)*[A-Za-z_][A-Za-z0-9_:\s<>\*&,\[\]]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)"), "function"),
        (re.compile(r"^\s*typedef\b.*?\b([A-Za-z_][A-Za-z0-9_]*)\s*;"), "type"),
        (re.compile(r"^\s*using\s+([A-Za-z_][A-Za-z0-9_]*)\s*="), "type"),
        (re.compile(r"^\s*#define\s+([A-Za-z_][A-Za-z0-9_]*)\b"), "macro"),
    ]
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue
        for pattern, kind in patterns:
            match = pattern.search(line)
            if match:
                symbols.append(
                    SymbolRecord(
                        kind=kind,
                        name=match.group(1),
                        qualified_name=match.group(1),
                        span=None,
                        metadata={"line": line_no, "language": language_id},
                    )
                )
                break
    return symbols


def _extract_c_family_imports(lines: list[str], language_id: str) -> list[EdgeRecord]:
    edges: list[EdgeRecord] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#include"):
            match = re.search(r'["<]([^">]+)[">]', stripped)
            if match:
                edges.append(EdgeRecord(kind="imports", target_ref=match.group(1), metadata={"syntax": language_id}))
    return edges


def _extract_systemverilog_symbols(lines: list[str]) -> list[SymbolRecord]:
    symbols: list[SymbolRecord] = []
    class_pattern = re.compile(r"^\s*(?:virtual\s+)?class\s+([A-Za-z_][A-Za-z0-9_$]*)\b(?:\s+extends\s+([A-Za-z_][A-Za-z0-9_$#\(\),\s]*))?")
    block_patterns = [
        (re.compile(r"^\s*(?:module|interface|program|package|covergroup|sequence|property|checker|program)\s+([A-Za-z_][A-Za-z0-9_$]*)\b"), "type"),
        (re.compile(r"^\s*(?:virtual\s+)?class\s+([A-Za-z_][A-Za-z0-9_$]*)\b"), "class"),
        (re.compile(r"^\s*(?:virtual\s+)?(?:function|task)\b(?:[^;]*?\b)?([A-Za-z_][A-Za-z0-9_$]*)\s*\("), "function"),
        (re.compile(r"^\s*typedef\b.*?\b([A-Za-z_][A-Za-z0-9_$]*)\s*;"), "type"),
        (re.compile(r"^\s*constraint\s+([A-Za-z_][A-Za-z0-9_$]*)\b"), "constraint"),
    ]
    for line_no, line in enumerate(lines, start=1):
        if line.lstrip().startswith("//") or line.lstrip().startswith("/*"):
            continue
        match = class_pattern.search(line)
        if match:
            base = (match.group(2) or "").strip()
            metadata = {"line": line_no, "language": "systemverilog"}
            if base:
                metadata["base_class"] = base.split(",", 1)[0].strip()
                if "uvm_" in base:
                    metadata["uvm_base"] = True
            symbols.append(
                SymbolRecord(
                    kind="class",
                    name=match.group(1),
                    qualified_name=match.group(1),
                    span=None,
                    metadata=metadata,
                )
            )
            continue
        for pattern, kind in block_patterns:
            match = pattern.search(line)
            if match:
                symbols.append(
                    SymbolRecord(
                        kind=kind,
                        name=match.group(1),
                        qualified_name=match.group(1),
                        span=None,
                        metadata={"line": line_no, "language": "systemverilog"},
                    )
                )
                break
    return symbols


def _extract_systemverilog_imports(lines: list[str]) -> list[EdgeRecord]:
    edges: list[EdgeRecord] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import ") and stripped.endswith(";"):
            target = stripped[len("import ") :].rstrip(";").strip()
            if target:
                edges.append(EdgeRecord(kind="imports", target_ref=target, metadata={"syntax": "systemverilog"}))
        elif stripped.startswith("`include"):
            match = re.search(r'`include\s+["<]([^">]+)[">]', stripped)
            if match:
                edges.append(EdgeRecord(kind="imports", target_ref=match.group(1), metadata={"syntax": "systemverilog"}))
    return edges


def _extract_html_symbols(lines: list[str]) -> list[SymbolRecord]:
    symbols: list[SymbolRecord] = []
    tag_pattern = re.compile(r"<\s*(script|style|template|section|article|nav|main|header|footer|aside|form)\b", re.IGNORECASE)
    id_pattern = re.compile(r'\bid\s*=\s*["\']([A-Za-z_][A-Za-z0-9_\-:]*)["\']')
    for line_no, line in enumerate(lines, start=1):
        tag_match = tag_pattern.search(line)
        if tag_match:
            symbols.append(
                SymbolRecord(
                    kind="element",
                    name=tag_match.group(1).lower(),
                    qualified_name=tag_match.group(1).lower(),
                    span=None,
                    metadata={"line": line_no, "language": "html"},
                )
            )
        for match in id_pattern.finditer(line):
            symbols.append(
                SymbolRecord(
                    kind="identifier",
                    name=match.group(1),
                    qualified_name=match.group(1),
                    span=None,
                    metadata={"line": line_no, "language": "html"},
                )
            )
    return symbols


def _extract_html_imports(lines: list[str]) -> list[EdgeRecord]:
    edges: list[EdgeRecord] = []
    patterns = [
        re.compile(r'\b(?:src|href|action)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE),
    ]
    for line in lines:
        for pattern in patterns:
            for match in pattern.finditer(line):
                edges.append(EdgeRecord(kind="imports", target_ref=match.group(1), metadata={"syntax": "html"}))
    return edges


def _extract_css_symbols(lines: list[str]) -> list[SymbolRecord]:
    symbols: list[SymbolRecord] = []
    patterns = [
        (re.compile(r"^\s*@keyframes\s+([A-Za-z_][A-Za-z0-9_-]*)\b", re.IGNORECASE), "animation"),
        (re.compile(r"^\s*@(?:media|supports|container)\s+(.+?)\s*\{?$", re.IGNORECASE), "rule"),
        (re.compile(r"^\s*([.#])([A-Za-z_][A-Za-z0-9_-]*)\s*\{"), "selector"),
        (re.compile(r"^\s*--([A-Za-z_][A-Za-z0-9_-]*)\s*:", re.IGNORECASE), "variable"),
    ]
    for line_no, line in enumerate(lines, start=1):
        for pattern, kind in patterns:
            match = pattern.search(line)
            if match:
                name = match.group(2) if pattern.pattern.startswith("^\\s*([.#])") else match.group(1)
                if not name:
                    continue
                symbols.append(
                    SymbolRecord(
                        kind=kind,
                        name=name,
                        qualified_name=name,
                        span=None,
                        metadata={"line": line_no, "language": "css"},
                    )
                )
                break
    return symbols


def _extract_css_imports(lines: list[str]) -> list[EdgeRecord]:
    edges: list[EdgeRecord] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("@import"):
            match = re.search(r'@import\s+["\']([^"\']+)["\']', stripped, re.IGNORECASE)
            if match:
                edges.append(EdgeRecord(kind="imports", target_ref=match.group(1), metadata={"syntax": "css"}))
        for match in re.finditer(r'url\(\s*["\']?([^)\"\'\s]+)["\']?\s*\)', line, re.IGNORECASE):
            edges.append(EdgeRecord(kind="imports", target_ref=match.group(1), metadata={"syntax": "css_url"}))
    return edges


def _extract_sql_symbols(lines: list[str]) -> list[SymbolRecord]:
    symbols: list[SymbolRecord] = []
    patterns = [
        (re.compile(r"^\s*CREATE\s+TABLE\s+([A-Za-z_][A-Za-z0-9_.$]*)\b", re.IGNORECASE), "table"),
        (re.compile(r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+([A-Za-z_][A-Za-z0-9_.$]*)\b", re.IGNORECASE), "view"),
        (re.compile(r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|PROCEDURE)\s+([A-Za-z_][A-Za-z0-9_.$]*)\b", re.IGNORECASE), "routine"),
        (re.compile(r"^\s*CREATE\s+TRIGGER\s+([A-Za-z_][A-Za-z0-9_.$]*)\b", re.IGNORECASE), "trigger"),
        (re.compile(r"^\s*CREATE\s+INDEX\s+([A-Za-z_][A-Za-z0-9_.$]*)\b", re.IGNORECASE), "index"),
        (re.compile(r"^\s*CREATE\s+SCHEMA\s+([A-Za-z_][A-Za-z0-9_.$]*)\b", re.IGNORECASE), "schema"),
    ]
    for line_no, line in enumerate(lines, start=1):
        for pattern, kind in patterns:
            match = pattern.search(line)
            if match:
                symbols.append(
                    SymbolRecord(
                        kind=kind,
                        name=match.group(1),
                        qualified_name=match.group(1),
                        span=None,
                        metadata={"line": line_no, "language": "sql"},
                    )
                )
                break
    return symbols


def _extract_sql_imports(lines: list[str]) -> list[EdgeRecord]:
    edges: list[EdgeRecord] = []
    for line in lines:
        for match in re.finditer(r"\bREFERENCES\s+([A-Za-z_][A-Za-z0-9_.$]*)\b", line, re.IGNORECASE):
            edges.append(EdgeRecord(kind="imports", target_ref=match.group(1), metadata={"syntax": "sql"}))
    return edges


def _extract_ruby_symbols(lines: list[str]) -> list[SymbolRecord]:
    symbols: list[SymbolRecord] = []
    patterns = [
        (re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_:]*)\b"), "class"),
        (re.compile(r"^\s*module\s+([A-Za-z_][A-Za-z0-9_:]*)\b"), "module"),
        (re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_!?=]*)\b"), "method"),
    ]
    for line_no, line in enumerate(lines, start=1):
        for pattern, kind in patterns:
            match = pattern.search(line)
            if match:
                symbols.append(
                    SymbolRecord(
                        kind=kind,
                        name=match.group(1),
                        qualified_name=match.group(1),
                        span=None,
                        metadata={"line": line_no, "language": "ruby"},
                    )
                )
                break
    return symbols


def _extract_ruby_imports(lines: list[str]) -> list[EdgeRecord]:
    edges: list[EdgeRecord] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("require ") or stripped.startswith("load "):
            match = re.search(r'["\']([^"\']+)["\']', stripped)
            if match:
                edges.append(EdgeRecord(kind="imports", target_ref=match.group(1), metadata={"syntax": "ruby"}))
        elif stripped.startswith("require_relative "):
            match = re.search(r'["\']([^"\']+)["\']', stripped)
            if match:
                edges.append(EdgeRecord(kind="imports", target_ref=match.group(1), metadata={"syntax": "ruby_relative"}))
    return edges

