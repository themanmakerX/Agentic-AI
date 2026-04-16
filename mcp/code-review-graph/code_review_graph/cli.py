"""CLI entrypoint for code-review-graph."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import (
    ServerConfig,
    install_server_entry,
    parse_env_pairs,
    parse_section_path,
)
from .server import run_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crg")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install", help="Install MCP config entry")
    install.add_argument("--config", type=Path, default=Path("config.toml"), help="Path to config.toml")
    install.add_argument("--name", default="code_review_graph", help="MCP server name")
    install.add_argument(
        "--launcher",
        "--command",
        dest="launcher",
        default=sys.executable,
        help="Executable used to launch the server",
    )
    install.add_argument("--cwd", default=None, help="Working directory for the server")
    install.add_argument("--section", default="mcp", help="Top-level TOML section used for server settings")
    install.add_argument(
        "--arg",
        action="append",
        dest="args",
        default=[],
        help="Additional server args; may be repeated",
    )
    install.add_argument("--db", type=Path, default=None, help="Database path passed to the server launcher")
    install.add_argument(
        "--env",
        action="append",
        dest="env",
        default=[],
        help="Environment variable assignment in KEY=VALUE form; may be repeated",
    )
    install.add_argument("--no-backup", action="store_true", help="Do not create a .bak backup file")
    install.add_argument("--no-overwrite", action="store_true", help="Fail if the server entry already exists")
    install.add_argument("--dry-run", action="store_true", help="Print the merged TOML without writing it")

    build = subparsers.add_parser("build", help="Build the code graph")
    build.add_argument("--root", type=Path, default=Path.cwd())
    build.add_argument("--db", type=Path, default=None)

    update = subparsers.add_parser("update", help="Incrementally update the graph")
    update.add_argument("--root", type=Path, default=Path.cwd())
    update.add_argument("--db", type=Path, default=None)

    status = subparsers.add_parser("status", help="Show graph status")
    status.add_argument("--root", type=Path, default=Path.cwd())
    status.add_argument("--db", type=Path, default=None)

    serve = subparsers.add_parser("serve", help="Run the MCP server")
    serve.add_argument("--root", type=Path, default=Path.cwd())
    serve.add_argument("--db", type=Path, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "install":
        server_args = args.args or ["-m", "code_review_graph.server"]
        if server_args == ["-m", "code_review_graph.server"] and args.db is not None:
            server_args += ["--db", str(args.db)]
        try:
            section_path = parse_section_path(args.section)
            env = parse_env_pairs(args.env)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        server = ServerConfig(name=args.name, command=args.launcher, args=server_args, cwd=args.cwd, env=env or None)

        if args.dry_run:
            from tomli_w import dumps
            from .config import load_toml, merge_server_config_at_path

            try:
                merged = merge_server_config_at_path(
                    load_toml(args.config),
                    server,
                    section_path=section_path,
                    overwrite=not args.no_overwrite,
                )
            except ValueError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
            print(dumps(merged), end="")
            return 0

        try:
            backup, _merged = install_server_entry(
                args.config,
                server,
                section_path=section_path,
                overwrite=not args.no_overwrite,
                backup_before_write=not args.no_backup,
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        if backup:
            print(f"Updated {args.config} (backup: {backup})")
        else:
            print(f"Created {args.config}")
        return 0

    if args.command == "build":
        from .graph.builder import build_graph

        db_path = args.db or args.root / ".code-review-graph" / "graph.sqlite3"
        summary = build_graph(args.root, db_path)
        print(summary.to_json())
        return 0

    if args.command == "update":
        from .graph.builder import update_graph

        db_path = args.db or args.root / ".code-review-graph" / "graph.sqlite3"
        summary = update_graph(args.root, db_path)
        print(summary.to_json())
        return 0

    if args.command == "status":
        from .graph.storage import GraphStore

        db_path = args.db or args.root / ".code-review-graph" / "graph.sqlite3"
        store = GraphStore(db_path)
        print(store.status_json())
        return 0

    if args.command == "serve":
        db_path = args.db or args.root / ".code-review-graph" / "graph.sqlite3"
        run_server(root=args.root, db_path=db_path)
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
