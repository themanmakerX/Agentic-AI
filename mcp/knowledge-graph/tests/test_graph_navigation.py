from __future__ import annotations

from pathlib import Path

from knowledge_graph.backend import create_service


def test_autocomplete_entities_and_ask_graph(sample_repo_path) -> None:
    root = sample_repo_path
    db_path = Path(r"C:\Users\acer\.codex\memories\knowledge-graph-navigation.sqlite")
    db_path.unlink(missing_ok=True)

    service = create_service(root, db_path)
    service.build()

    autocomplete = service.autocomplete_entities("app", limit=10)
    assert autocomplete["results"]
    assert any("app" in str(item.get("label", "")).lower() for item in autocomplete["results"])

    answer = service.ask_graph("what relates to app.py and helpers.py?", limit=5, depth=1)
    assert answer["answer"]
    assert "evidence" in answer
    assert "semantic_matches" in answer["evidence"]

