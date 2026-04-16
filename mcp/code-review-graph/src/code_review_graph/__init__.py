"""Core graph and incremental indexing primitives."""

__version__ = "0.1.0"

from .incremental import FileChange, IncrementalIndexer, WorkspaceScanResult
from .languages import LanguageDefinition, LanguageRegistry, build_default_registry
from .parser import (
    EdgeRecord,
    ParseDiagnostic,
    ParseResult,
    ParserBackend,
    Position,
    Span,
    SymbolRecord,
    TreeSitterBackend,
)
from .storage import SQLiteGraphStore, WorkspaceFileSnapshot
