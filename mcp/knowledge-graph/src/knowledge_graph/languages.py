from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


@dataclass(frozen=True, slots=True)
class LanguageDefinition:
    language_id: str
    file_extensions: tuple[str, ...]
    tree_sitter_name: str | None = None
    loader: Callable[[], object] | None = None

    def matches_path(self, path: Path) -> bool:
        name = path.name.lower()
        return any(name.endswith(extension) for extension in self.file_extensions)


class LanguageRegistry:
    def __init__(self, languages: Iterable[LanguageDefinition]):
        self._languages = tuple(languages)

    def all(self) -> tuple[LanguageDefinition, ...]:
        return self._languages

    def detect(self, path: Path) -> LanguageDefinition | None:
        path = Path(path)
        for language in self._languages:
            if language.matches_path(path):
                return language
        return None

    def get(self, language_id: str) -> LanguageDefinition:
        for language in self._languages:
            if language.language_id == language_id:
                return language
        raise KeyError(language_id)


def build_default_registry() -> LanguageRegistry:
    return LanguageRegistry(
        [
            LanguageDefinition(
                language_id="python",
                file_extensions=(".py", ".pyi"),
                tree_sitter_name="python",
            ),
            LanguageDefinition(
                language_id="generic",
                file_extensions=(),
                tree_sitter_name=None,
            ),
            LanguageDefinition(
                language_id="javascript",
                file_extensions=(".js", ".mjs", ".cjs"),
                tree_sitter_name="javascript",
            ),
            LanguageDefinition(
                language_id="typescript",
                file_extensions=(".ts",),
                tree_sitter_name="typescript",
            ),
            LanguageDefinition(
                language_id="tsx",
                file_extensions=(".tsx",),
                tree_sitter_name="tsx",
            ),
            LanguageDefinition(
                language_id="jsx",
                file_extensions=(".jsx",),
                tree_sitter_name="javascript",
            ),
            LanguageDefinition(
                language_id="go",
                file_extensions=(".go",),
                tree_sitter_name="go",
            ),
            LanguageDefinition(
                language_id="java",
                file_extensions=(".java",),
                tree_sitter_name="java",
            ),
            LanguageDefinition(
                language_id="rust",
                file_extensions=(".rs",),
                tree_sitter_name="rust",
            ),
            LanguageDefinition(
                language_id="c",
                file_extensions=(".c", ".h"),
                tree_sitter_name="c",
            ),
            LanguageDefinition(
                language_id="cpp",
                file_extensions=(".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"),
                tree_sitter_name="cpp",
            ),
            LanguageDefinition(
                language_id="html",
                file_extensions=(".html", ".htm"),
                tree_sitter_name="html",
            ),
            LanguageDefinition(
                language_id="css",
                file_extensions=(".css",),
                tree_sitter_name="css",
            ),
            LanguageDefinition(
                language_id="sql",
                file_extensions=(".sql",),
                tree_sitter_name="sql",
            ),
            LanguageDefinition(
                language_id="ruby",
                file_extensions=(".rb", ".rake", ".gemspec"),
                tree_sitter_name="ruby",
            ),
            LanguageDefinition(
                language_id="systemverilog",
                file_extensions=(".sv", ".svh", ".v", ".vh"),
                tree_sitter_name="systemverilog",
            ),
        ]
    )

