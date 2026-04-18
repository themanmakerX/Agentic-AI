from knowledge_graph.config import build_install_spec, format_section_path, install_to_file, read_toml


def test_install_to_file_writes_mcp_block(sample_repo_path) -> None:
    config_path = sample_repo_path / "config.toml"
    spec = build_install_spec(
        name="knowledge-graph",
        command="python",
        args=["-m", "knowledge_graph.server"],
        cwd=".",
    )

    merged = install_to_file(
        config_path=config_path,
        section_path=format_section_path("mcp.servers"),
        spec=spec,
        overwrite=True,
        create_backup=False,
    )

    assert merged["mcp"]["servers"]["knowledge-graph"]["command"] == "python"
    assert merged["mcp"]["servers"]["knowledge-graph"]["args"] == ["-m", "knowledge_graph.server"]
    loaded = read_toml(config_path)
    assert loaded["mcp"]["servers"]["knowledge-graph"]["cwd"]


