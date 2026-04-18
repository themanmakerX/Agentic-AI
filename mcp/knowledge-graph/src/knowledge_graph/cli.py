from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence
import sys

from . import __version__
from .backend import create_service
from .config import (
    ConfigError,
    build_install_spec,
    format_section_path,
    install_to_file,
    parse_env_pairs,
    resolve_config_path,
    resolve_cwd,
)
from .serve import main as serve_main
from .web import run as run_web


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crg", description="Code review graph utilities")
    parser.add_argument("--version", action="version", version=__version__)

    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser(
        "install",
        help="Merge an MCP server entry into a TOML config file",
    )
    install.add_argument("--config", help="Path to config.toml", default="config.toml")
    install.add_argument("--section", help="TOML section path", default="mcp.servers")
    install.add_argument("--name", help="Server name", default="knowledge_graph")
    install.add_argument("--launcher", help="Launch command", default="knowledge-graph")
    install.add_argument(
        "--arg",
        dest="args",
        action="append",
        default=[],
        help="Additional command argument; can be repeated",
    )
    install.add_argument(
        "--env",
        dest="env",
        action="append",
        default=[],
        help="Environment variable assignment in KEY=VALUE form; can be repeated",
    )
    install.add_argument("--cwd", help="Working directory stored in the config")
    install.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip writing a .bak backup before replacing the file",
    )
    install.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Fail if the server entry already exists",
    )
    install.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the merged TOML document instead of writing it",
    )

    build = subparsers.add_parser("build", help="Build the code graph")
    build.add_argument("--root", help="Workspace root path", default=None)

    update = subparsers.add_parser("update", help="Incrementally update the code graph")
    update.add_argument("--root", help="Workspace root path", default=None)

    status = subparsers.add_parser("status", help="Print graph statistics")
    status.add_argument("--root", help="Workspace root path", default=None)

    subparsers.add_parser("serve", help="Run the MCP server entry point")
    web = subparsers.add_parser("web", help="Run the persistent web app")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=5000)
    return parser


def cmd_install(namespace: argparse.Namespace) -> int:
    try:
        config_path = resolve_config_path(namespace.config)
        section_path = format_section_path(namespace.section)
        env = parse_env_pairs(namespace.env)
        spec = build_install_spec(
            name=namespace.name,
            command=namespace.launcher,
            args=list(namespace.args) or ["serve"],
            cwd=resolve_cwd(namespace.cwd) if namespace.cwd else None,
            env=env,
        )

        if namespace.dry_run:
            from .config import merge_install_spec, read_toml
            from tomli_w import dumps

            current = read_toml(config_path)
            merged = merge_install_spec(
                current,
                section_path=section_path,
                spec=spec,
                overwrite=not namespace.no_overwrite,
            )
            print(dumps(merged), end="")
            return 0

        install_to_file(
            config_path=config_path,
            section_path=section_path,
            spec=spec,
            overwrite=not namespace.no_overwrite,
            create_backup=not namespace.no_backup,
        )
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Updated {config_path} with {'.'.join(section_path)}.{spec.name}")
    return 0


def cmd_serve(_: argparse.Namespace) -> int:
    from .serve import main as serve_main

    return serve_main()


def cmd_build(namespace: argparse.Namespace) -> int:
    root = _workspace_root(namespace)
    service = create_service(root)

    def progress_callback(payload: dict[str, object]) -> None:
        message = str(payload.get("message", "")).strip()
        stage = str(payload.get("stage", "build"))
        current = int(payload.get("current", 0) or 0)
        total = int(payload.get("total", 0) or 0)
        if total > 0:
            print(f"[{stage}] {current}/{total} {message}")
        else:
            print(f"[{stage}] {message}")

    summary = service.build(progress_callback=progress_callback)
    print(summary)
    print(f"Database: {service.db_path}")
    return 0


def cmd_update(namespace: argparse.Namespace) -> int:
    root = _workspace_root(namespace)
    service = create_service(root)
    summary = service.update()
    print(summary)
    return 0


def cmd_status(namespace: argparse.Namespace) -> int:
    root = _workspace_root(namespace)
    service = create_service(root)
    print(service.stats())
    return 0


def cmd_web(namespace: argparse.Namespace) -> int:
    return run_web(host=namespace.host, port=namespace.port)


def _workspace_root(namespace: argparse.Namespace) -> Path:
    root = getattr(namespace, "root", None)
    return Path(root).resolve() if root else Path.cwd().resolve()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    namespace = parser.parse_args(list(argv) if argv is not None else None)

    if namespace.command == "install":
        return cmd_install(namespace)
    if namespace.command == "build":
        return cmd_build(namespace)
    if namespace.command == "update":
        return cmd_update(namespace)
    if namespace.command == "status":
        return cmd_status(namespace)
    if namespace.command == "serve":
        return cmd_serve(namespace)
    if namespace.command == "web":
        return cmd_web(namespace)

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())


