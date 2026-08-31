"""YAML configuration management."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG: dict[str, Any] = {
    "source_url": "https://raw.githubusercontent.com/sebaxakerhtc/rdpwrap.ini/master/rdpwrap.ini",
    "local_ini": "rdpwrap.ini",
    "rdpwinst": "RDPWInst.exe",
    "schedule_time": "03:00",
    "startup_delay_minutes": 5,
    "reinstall_wait_seconds": 5,
    "ntfy": {
        "url": "http://192.168.1.131:8090/rdpwrap-watcher",
        "user": "admin",
        "password": "admin",
    },
    "task_names": {
        "startup": "RDPWrapWatcher-Startup",
        "daily": "RDPWrapWatcher-Daily",
    },
}


def config_path(base_dir: Path | None = None) -> Path:
    base = base_dir or Path(__file__).resolve().parent.parent
    return base / "config.yaml"


def load_config(base_dir: Path | None = None) -> dict[str, Any]:
    path = config_path(base_dir)
    if not path.exists():
        return deepcopy(DEFAULT_CONFIG)

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    merged = deepcopy(DEFAULT_CONFIG)
    _deep_merge(merged, data)
    return merged


def save_config(cfg: dict[str, Any], base_dir: Path | None = None) -> Path:
    path = config_path(base_dir)
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return path


def init_config(base_dir: Path | None = None) -> Path:
    path = config_path(base_dir)
    if path.exists():
        return path
    return save_config(deepcopy(DEFAULT_CONFIG), base_dir)


def resolve_paths(cfg: dict[str, Any], base_dir: Path) -> dict[str, Path]:
    return {
        "base_dir": base_dir,
        "local_ini": base_dir / cfg["local_ini"],
        "rdpwinst": base_dir / cfg["rdpwinst"],
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
