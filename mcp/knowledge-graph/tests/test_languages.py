from pathlib import Path

from knowledge_graph.languages import build_default_registry


def test_language_registry_detects_common_extensions() -> None:
    registry = build_default_registry()

    assert registry.detect(Path("app.py")).language_id == "python"
    assert registry.detect(Path("index.ts")).language_id == "typescript"
    assert registry.detect(Path("view.tsx")).language_id == "tsx"
    assert registry.detect(Path("main.go")).language_id == "go"
    assert registry.detect(Path("unknown.txt")) is None


