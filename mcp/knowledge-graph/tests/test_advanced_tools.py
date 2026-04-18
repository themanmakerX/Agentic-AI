from pathlib import Path

from knowledge_graph.backend import GraphService
from knowledge_graph.backend import create_service


def _write_sample_repo(root) -> None:
    (root / "app.py").write_text(
        "from helpers import format_name\n\n\ndef compute(value):\n    return format_name(value)\n",
        encoding="utf-8",
    )
    (root / "helpers.py").write_text(
        "def format_name(value):\n    return str(value).strip().title()\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_app.py").write_text(
        "from app import compute\n\n\ndef test_compute():\n    assert compute('x') == 'X'\n",
        encoding="utf-8",
    )


def test_advanced_analysis_tools(sample_repo_path, monkeypatch) -> None:
    root = sample_repo_path
    _write_sample_repo(root)
    (root / "app.py").write_text(
        "from helpers import format_name\n\n\ndef compute(value):\n    return format_name(value).lower()\n",
        encoding="utf-8",
    )
    db_path = Path(r"C:\Users\acer\.codex\memories\knowledge-graph-advanced.sqlite")
    db_path.unlink(missing_ok=True)
    service = create_service(root, db_path)
    service.build()
    monkeypatch.setattr(GraphService, "_git_diff_names", lambda self, *_args, **_kwargs: ["app.py", "tests/test_app.py"])

    semantic = service.semantic_search("format name")
    assert semantic["matches"]
    assert semantic["strategy"] in {"token-overlap-ranking", "hybrid-embedding-ranking"}

    changes = service.detect_changes("HEAD~1", "HEAD")
    assert "risk_score" in changes
    assert "risk_level" in changes

    radius = service.trace_dataflow("compute", "format_name")
    assert "found" in radius

    communities = service.list_communities(min_size=1)
    assert communities["count"] >= 1

    overview = service.get_architecture_overview()
    assert "community_count" in overview

    refactor = service.refactor_workspace()
    assert "summary" in refactor

    wiki = service.generate_wiki(write_to_disk=False)
    assert "pages" in wiki


