"""Configuration helpers for config.toml installation and server settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import shutil

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

import tomli_w


@dataclass(slots=True)
class ServerConfig:
    name: str
    command: str
    args: list[str]
    cwd: str | None = None
    env: dict[str, str] | None = None


def load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def write_toml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(data), encoding="utf-8")


def backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    return backup


def merge_server_config(data: dict[str, Any], server: ServerConfig) -> dict[str, Any]:
    config = dict(data)
    mcp = dict(config.get("mcp", {}))
    servers = dict(mcp.get("servers", {}))
    servers[server.name] = {
        "command": server.command,
        "args": server.args,
    }
    if server.cwd:
        servers[server.name]["cwd"] = server.cwd
    if server.env:
        servers[server.name]["env"] = server.env
    mcp["servers"] = servers
    config["mcp"] = mcp
    return config


def merge_server_config_at_path(
    data: dict[str, Any],
    server: ServerConfig,
    section_path: list[str],
    *,
    overwrite: bool = True,
) -> dict[str, Any]:
    if not section_path:
        raise ValueError("section_path must not be empty")

    config = dict(data)
    cursor: dict[str, Any] = config

    for key in section_path[:-1]:
        next_value = cursor.get(key)
        if next_value is None:
            next_value = {}
            cursor[key] = next_value
        if not isinstance(next_value, dict):
            raise ValueError(f"Cannot merge into non-table section: {'.'.join(section_path)}")
        cursor = next_value

    table_name = section_path[-1]
    table_value = cursor.get(table_name)
    if table_value is None:
        table_value = {}
        cursor[table_name] = table_value
    if not isinstance(table_value, dict):
        raise ValueError(f"Cannot merge into non-table section: {'.'.join(section_path)}")

    section = dict(table_value)
    servers = dict(section.get("servers", {}))
    if not overwrite and server.name in servers:
        raise ValueError(f"Server entry already exists: {server.name}")

    servers[server.name] = {
        "command": server.command,
        "args": server.args,
    }
    if server.cwd:
        servers[server.name]["cwd"] = server.cwd
    if server.env:
        servers[server.name]["env"] = server.env

    section["servers"] = servers
    cursor[table_name] = section
    return config


def parse_section_path(value: str) -> list[str]:
    parts = [part.strip() for part in value.split(".") if part.strip()]
    if not parts:
        raise ValueError("Section path must not be empty")
    return parts


def parse_env_pairs(values: list[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Invalid environment assignment: {value}")
        key, raw = value.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid environment assignment: {value}")
        env[key] = raw
    return env


def install_server_entry(
    config_path: Path,
    server: ServerConfig,
    *,
    section_path: list[str] | None = None,
    overwrite: bool = True,
    backup_before_write: bool = True,
) -> tuple[Path | None, dict[str, Any]]:
    current = load_toml(config_path)
    if section_path is None:
        merged = merge_server_config(current, server)
    else:
        merged = merge_server_config_at_path(current, server, section_path, overwrite=overwrite)
    backup = backup_file(config_path) if backup_before_write else None
    write_toml(config_path, merged)
    return backup, merged
