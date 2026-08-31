"""Core watcher logic: download, compare, update, reinstall."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from .config import load_config, resolve_paths
from .ntfy import NtfyClient


@dataclass
class WatchResult:
    updated: bool
    reinstalled: bool
    message: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_source(url: str, timeout: float = 30.0) -> bytes:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def reinstall_rdpwrap(rdpwinst: Path, wait_seconds: int) -> None:
    if not rdpwinst.exists():
        raise FileNotFoundError(f"RDPWInst.exe not found: {rdpwinst}")

    cwd = rdpwinst.parent
    subprocess.run(
        [str(rdpwinst), "-u", "-k"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    time.sleep(wait_seconds)
    subprocess.run(
        [str(rdpwinst), "-i"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _notify(ntfy: NtfyClient, method: str, message: str) -> None:
    if not ntfy.configured:
        return
    try:
        getattr(ntfy, method)(message)
    except Exception as ntfy_err:
        print(f"ntfy notification skipped: {ntfy_err}", file=sys.stderr)


def run_check(base_dir: Path | None = None, notify: bool = True) -> WatchResult:
    base = (base_dir or Path.cwd()).resolve()
    cfg = load_config(base)
    paths = resolve_paths(cfg, base)
    ntfy_cfg = cfg["ntfy"]
    ntfy = NtfyClient(ntfy_cfg["url"], ntfy_cfg["user"], ntfy_cfg["password"])

    local_ini = paths["local_ini"]
    rdpwinst = paths["rdpwinst"]
    source_url = cfg["source_url"]
    wait_seconds = int(cfg["reinstall_wait_seconds"])

    try:
        remote_content = download_source(source_url)
        remote_hash = sha256_bytes(remote_content)

        if local_ini.exists():
            local_hash = sha256_file(local_ini)
        else:
            local_hash = None

        if local_hash == remote_hash:
            msg = f"No update required (hash match).\nSource: {source_url}"
            if notify:
                _notify(ntfy, "ok", msg)
            return WatchResult(updated=False, reinstalled=False, message=msg)

        backup = None
        if local_ini.exists():
            backup = local_ini.read_bytes()

        local_ini.write_bytes(remote_content)
        try:
            reinstall_rdpwrap(rdpwinst, wait_seconds)
        except Exception:
            if backup is not None:
                local_ini.write_bytes(backup)
            elif local_ini.exists():
                local_ini.unlink()
            raise

        msg = (
            f"rdpwrap.ini updated and RDPWrap reinstalled.\n"
            f"Previous hash: {local_hash or 'missing'}\n"
            f"New hash: {remote_hash}"
        )
        if notify:
            _notify(ntfy, "updated", msg)
        return WatchResult(updated=True, reinstalled=True, message=msg)

    except Exception as exc:
        msg = f"Watcher error: {exc}"
        if notify:
            _notify(ntfy, "error", msg)
        raise
