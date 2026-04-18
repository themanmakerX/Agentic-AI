from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, Sequence

from .languages import LanguageDefinition


@dataclass(frozen=True, slots=True)
class Position:
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class Span:
    start: Position
    end: Position


@dataclass(frozen=True, slots=True)
class SymbolRecord:
    kind: str
    name: str
    qualified_name: str
    span: Span | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EdgeRecord:
    kind: str
    target_ref: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParseDiagnostic:
    level: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ParseResult:
    path: Path
    language_id: str
    content_hash: str
    symbols: tuple[SymbolRecord, ...]
    edges: tuple[EdgeRecord, ...]
    diagnostics: tuple[ParseDiagnostic, ...] = ()


class SyntaxNodeLike(Protocol):
    type: str
    start_point: tuple[int, int]
    end_point: tuple[int, int]
    children: Sequence["SyntaxNodeLike"]
    named_children: Sequence["SyntaxNodeLike"]
    has_error: bool

    def child_by_field_name(self, name: str) -> "SyntaxNodeLike | None":
        ...

    @property
    def text(self) -> bytes:
        ...


class ParserBackend(Protocol):
    def parse(self, *, path: Path, source: bytes, language: LanguageDefinition) -> SyntaxNodeLike | None:
        ...


class TreeSitterBackend:
    """Parse source using Tree-sitter and return a syntax node wrapper."""

    def __init__(self) -> None:
        self._parser_cache: dict[str, Any] = {}

    def parse(self, *, path: Path, source: bytes, language: LanguageDefinition) -> SyntaxNodeLike | None:
        if language.loader is None:
            return None
        try:
            from tree_sitter import Parser  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency path
            raise RuntimeError("tree-sitter is not installed") from exc

        parser = self._parser_cache.get(language.language_id)
        if parser is None:
            parser = Parser()
            parser.language = language.loader()
            self._parser_cache[language.language_id] = parser

        tree = parser.parse(source)
        if tree is None:
            return None
        return TreeSitterNode(tree.root_node, source)


class TreeSitterNode:
    def __init__(self, node: Any, source: bytes) -> None:
        self._node = node
        self._source = source

    @property
    def type(self) -> str:
        return self._node.type

    @property
    def start_point(self) -> tuple[int, int]:
        return self._node.start_point

    @property
    def end_point(self) -> tuple[int, int]:
        return self._node.end_point

    @property
    def children(self) -> Sequence["TreeSitterNode"]:
        return [TreeSitterNode(child, self._source) for child in self._node.children]

    @property
    def named_children(self) -> Sequence["TreeSitterNode"]:
        return [TreeSitterNode(child, self._source) for child in self._node.named_children]

    @property
    def has_error(self) -> bool:
        return bool(getattr(self._node, "has_error", False))

    def child_by_field_name(self, name: str) -> "TreeSitterNode | None":
        child = self._node.child_by_field_name(name)
        if child is None:
            return None
        return TreeSitterNode(child, self._source)

    @property
    def text(self) -> bytes:
        return self._source[self._node.start_byte : self._node.end_byte]


class StructuralGraphExtractor:
    """Extract structural symbols and dependency edges from a syntax tree."""

    _definition_node_types = {
        "python": {
            "function_definition": "function",
            "class_definition": "class",
        },
        "javascript": {
            "function_declaration": "function",
            "class_declaration": "class",
            "method_definition": "method",
            "arrow_function": "function",
        },
        "typescript": {
            "function_declaration": "function",
            "class_declaration": "class",
            "method_definition": "method",
            "arrow_function": "function",
        },
        "tsx": {
            "function_declaration": "function",
            "class_declaration": "class",
            "method_definition": "method",
            "arrow_function": "function",
        },
        "go": {
            "function_declaration": "function",
            "method_declaration": "method",
            "type_spec": "type",
        },
        "java": {
            "class_declaration": "class",
            "method_declaration": "method",
        },
        "rust": {
            "function_item": "function",
            "struct_item": "struct",
            "enum_item": "enum",
            "impl_item": "impl",
        },
    }

    _import_node_types = {
        "python": {"import_statement", "import_from_statement"},
        "javascript": {"import_statement"},
        "typescript": {"import_statement"},
        "tsx": {"import_statement"},
        "go": {"import_declaration"},
        "java": {"import_declaration"},
        "rust": {"use_declaration"},
    }

    _call_node_types = {
        "python": {"call"},
        "javascript": {"call_expression", "new_expression"},
        "typescript": {"call_expression", "new_expression"},
        "tsx": {"call_expression", "new_expression"},
        "go": {"call_expression"},
        "java": {"method_invocation", "object_creation_expression"},
        "rust": {"call_expression"},
    }

    def extract(
        self,
        *,
        path: Path,
        language: LanguageDefinition,
        root: SyntaxNodeLike | None,
        source: bytes,
    ) -> tuple[tuple[SymbolRecord, ...], tuple[EdgeRecord, ...], tuple[ParseDiagnostic, ...]]:
        if root is None:
            return (), (), (
                ParseDiagnostic(level="warning", message="No syntax tree available", metadata={"path": str(path)}),
            )

        symbols: list[SymbolRecord] = []
        edges: list[EdgeRecord] = []
        seen_symbol_names: set[str] = set()
        definition_node_types = self._definition_node_types.get(language.language_id, {})
        import_node_types = self._import_node_types.get(language.language_id, set())
        call_node_types = self._call_node_types.get(language.language_id, set())

        for node in self._walk(root):
            if node.type in definition_node_types:
                symbol = self._extract_symbol(language.language_id, node, definition_node_types[node.type], source)
                if symbol is not None:
                    symbols.append(symbol)
                    seen_symbol_names.add(symbol.name)
                    continue

            if node.type in import_node_types:
                import_target = self._extract_import_target(language.language_id, node)
                if import_target:
                    edges.append(EdgeRecord(kind="imports", target_ref=import_target, metadata={"node_type": node.type}))
                continue

            if node.type in call_node_types:
                call_target = self._extract_call_target(node)
                if call_target and call_target not in seen_symbol_names:
                    edges.append(EdgeRecord(kind="references", target_ref=call_target, metadata={"node_type": node.type}))

        diagnostics = ()
        if getattr(root, "has_error", False):
            diagnostics = (
                ParseDiagnostic(
                    level="warning",
                    message="Tree contains parse errors",
                    metadata={"path": str(path)},
                ),
            )
        return tuple(symbols), tuple(edges), diagnostics

    def _walk(self, node: SyntaxNodeLike) -> Sequence[SyntaxNodeLike]:
        stack = [node]
        ordered: list[SyntaxNodeLike] = []
        while stack:
            current = stack.pop()
            ordered.append(current)
            children = list(getattr(current, "named_children", ()) or current.children)
            stack.extend(reversed(children))
        return ordered

    def _extract_symbol(
        self,
        language_id: str,
        node: SyntaxNodeLike,
        symbol_kind: str,
        source: bytes,
    ) -> SymbolRecord | None:
        name = self._extract_name(node)
        if name is None:
            return None
        qualified_name = name
        span = Span(
            start=Position(line=node.start_point[0] + 1, column=node.start_point[1] + 1),
            end=Position(line=node.end_point[0] + 1, column=node.end_point[1] + 1),
        )
        metadata = {"language_id": language_id, "node_type": node.type}
        return SymbolRecord(kind=symbol_kind, name=name, qualified_name=qualified_name, span=span, metadata=metadata)

    def _extract_name(self, node: SyntaxNodeLike) -> str | None:
        for field_name in ("name", "declarator", "identifier", "value"):
            child = node.child_by_field_name(field_name)
            if child is not None:
                text = child.text.decode("utf-8", errors="ignore").strip()
                if text:
                    return self._clean_identifier(text)

        for child in node.named_children:
            text = child.text.decode("utf-8", errors="ignore").strip()
            if not text:
                continue
            cleaned = self._clean_identifier(text)
            if cleaned:
                return cleaned
        return None

    def _extract_import_target(self, language_id: str, node: SyntaxNodeLike) -> str | None:
        text = node.text.decode("utf-8", errors="ignore").strip()
        if not text:
            return None
        text = " ".join(text.split())
        if language_id == "python":
            return text.replace("import ", "").replace("from ", "from:")
        return text

    def _extract_call_target(self, node: SyntaxNodeLike) -> str | None:
        child = node.child_by_field_name("function")
        if child is not None:
            return self._clean_identifier(child.text.decode("utf-8", errors="ignore"))
        child = node.child_by_field_name("name")
        if child is not None:
            return self._clean_identifier(child.text.decode("utf-8", errors="ignore"))
        for candidate in node.named_children:
            text = candidate.text.decode("utf-8", errors="ignore").strip()
            cleaned = self._clean_identifier(text)
            if cleaned:
                return cleaned
        return None

    def _clean_identifier(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ""
        for token in ("(", ")", "{", "}", "[", "]", ";", ",", ":", "="):
            if token in text:
                text = text.split(token, 1)[0]
        text = text.strip().strip("'\"")
        return text


class GraphParser:
    """High-level parser that combines a backend and structural extraction."""

    def __init__(self, backend: ParserBackend, extractor: StructuralGraphExtractor | None = None) -> None:
        self._backend = backend
        self._extractor = extractor or StructuralGraphExtractor()

    def parse(
        self,
        *,
        path: Path,
        source: bytes,
        language: LanguageDefinition,
        content_hash: str,
    ) -> ParseResult:
        root = self._backend.parse(path=path, source=source, language=language)
        symbols, edges, diagnostics = self._extractor.extract(path=path, language=language, root=root, source=source)
        return ParseResult(
            path=Path(path),
            language_id=language.language_id,
            content_hash=content_hash,
            symbols=symbols,
            edges=edges,
            diagnostics=diagnostics,
        )


