from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import copy
import os

import tomllib

try:  # pragma: no cover - dependency fallback
    import tomli_w
except Exception:  # pragma: no cover - fallback path
    tomli_w = None


class ConfigError(RuntimeError):
    """Raised when TOML merge input is invalid."""


@dataclass(frozen=True)
class InstallSpec:
    name: str
    command: str
    args: list[str]
    cwd: str
    env: dict[str, str]


@dataclass(frozen=True)
class ServerConfig:
    name: str
    command: str
    args: list[str]
    cwd: str
    env: dict[str, str] | None = None


def read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        raise ConfigError(f"Expected a TOML table at {path}")
    return data


def write_toml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if tomli_w is not None:
        with path.open("wb") as handle:
            tomli_w.dump(data, handle)
        return

    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(_dump_toml(data))


def build_install_spec(
    *,
    name: str = "code_review_graph",
    command: str = "code-review-graph",
    args: list[str] | None = None,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> InstallSpec:
    resolved_cwd = Path(cwd or Path.cwd()).resolve()
    return InstallSpec(
        name=name,
        command=command,
        args=list(args or ["serve"]),
        cwd=str(resolved_cwd),
        env=dict(env or {}),
    )


def merge_install_spec(
    config: dict[str, Any],
    *,
    section_path: list[str],
    spec: InstallSpec,
    overwrite: bool = True,
) -> dict[str, Any]:
    merged = copy.deepcopy(config)
    cursor: dict[str, Any] = merged

    for part in section_path:
        next_value = cursor.get(part)
        if next_value is None:
            next_value = {}
            cursor[part] = next_value
        if not isinstance(next_value, dict):
            raise ConfigError(f"Cannot merge into non-table section: {'.'.join(section_path)}")
        cursor = next_value

    if not overwrite and spec.name in cursor:
        raise ConfigError(f"Server entry already exists: {spec.name}")

    entry: dict[str, Any] = {
        "command": spec.command,
        "args": spec.args,
        "cwd": spec.cwd,
    }
    if spec.env:
        entry["env"] = spec.env

    cursor[spec.name] = entry
    return merged


def install_to_file(
    *,
    config_path: Path,
    section_path: list[str],
    spec: InstallSpec,
    overwrite: bool = True,
    create_backup: bool = True,
) -> dict[str, Any]:
    current = read_toml(config_path)
    merged = merge_install_spec(current, section_path=section_path, spec=spec, overwrite=overwrite)

    if create_backup and config_path.exists():
        backup_path = config_path.with_suffix(config_path.suffix + ".bak")
        backup_path.write_bytes(config_path.read_bytes())

    write_toml(config_path, merged)
    return merged


def load_toml(path: Path) -> dict[str, Any]:
    return read_toml(path)


def install_server_entry(config_path: Path, server: ServerConfig) -> tuple[Path | None, dict[str, Any]]:
    section_path = ["mcp", "servers"]
    spec = InstallSpec(
        name=server.name,
        command=server.command,
        args=list(server.args),
        cwd=server.cwd,
        env=dict(server.env or {}),
    )
    backup_path = config_path.with_suffix(config_path.suffix + ".bak") if config_path.exists() else None
    merged = install_to_file(config_path=config_path, section_path=section_path, spec=spec, create_backup=True)
    return backup_path if backup_path and backup_path.exists() else None, merged


def format_section_path(section: str) -> list[str]:
    parts = [part.strip() for part in section.split(".") if part.strip()]
    if not parts:
        raise ConfigError("Section path must not be empty")
    return parts


def parse_env_pairs(pairs: list[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ConfigError(f"Invalid environment assignment: {pair}")
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise ConfigError(f"Invalid environment assignment: {pair}")
        env[key] = value
    return env


def resolve_config_path(value: str | None) -> Path:
    return Path(value or "config.toml").expanduser().resolve()


def resolve_cwd(value: str | None) -> str:
    return str(Path(value or os.getcwd()).resolve())


def _dump_toml(data: dict[str, Any], prefix: tuple[str, ...] = ()) -> str:
    lines: list[str] = []
    scalar_items: list[tuple[str, Any]] = []
    table_items: list[tuple[str, dict[str, Any]]] = []

    for key, value in data.items():
        if isinstance(value, dict):
            table_items.append((key, value))
        else:
            scalar_items.append((key, value))

    if prefix:
        lines.append(f"[{'.'.join(prefix)}]")

    for key, value in scalar_items:
        lines.append(f"{key} = {_format_toml_value(value)}")

    for key, value in table_items:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(_dump_toml(value, prefix + (key,)))

    return "\n".join(line for line in lines if line is not None) + ("\n" if lines else "")


def _format_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return f"\"{value.replace('\"', '\\\"')}\""
    if isinstance(value, list):
        return "[" + ", ".join(_format_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        items = ", ".join(f"{key} = {_format_toml_value(item)}" for key, item in value.items())
        return "{ " + items + " }"
    raise ConfigError(f"Unsupported TOML value type: {type(value)!r}")
