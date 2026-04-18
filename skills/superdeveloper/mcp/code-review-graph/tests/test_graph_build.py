from pathlib import Path

from code_review_graph.graph.builder import build_graph, update_graph
from code_review_graph.graph.storage import GraphStore


def test_build_and_update_graph(sample_repo_path) -> None:
    root = sample_repo_path
    (root / "app.py").write_text(
        "import os\n\nclass Demo:\n    pass\n\ndef run():\n    return 1\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_app.py").write_text("def test_run():\n    assert True\n", encoding="utf-8")

    db_path = Path(r"C:\Users\acer\.codex\memories\code-review-graph-graph-build.sqlite")
    db_path.unlink(missing_ok=True)
    summary = build_graph(root, db_path)
    assert summary.files_scanned >= 2
    assert summary.nodes_indexed >= 3

    store = GraphStore(db_path)
    status = store.status()
    initial_files = status["counts"]["files"]
    assert initial_files >= 2

    noop = update_graph(root, db_path)
    assert noop.files_changed == 0

    (root / "app.py").write_text(
        "import os\n\nclass Demo:\n    pass\n\n\ndef run():\n    return 2\n",
        encoding="utf-8",
    )
    after_delete = update_graph(root, db_path)
    assert after_delete.files_changed >= 1
    status_after = store.status()
    assert status_after["counts"]["files"] == initial_files
