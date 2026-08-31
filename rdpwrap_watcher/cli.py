"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from . import __version__
from .config import init_config, load_config, save_config
from .scheduler import install_tasks, remove_tasks
from .watcher import run_check


def _base_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    return Path.cwd().resolve()


def _cmd_setup(args: argparse.Namespace) -> int:
    base = _base_dir(args.dir)
    path = init_config(base)
    print(f"Config created/updated: {path}")

    try:
        tasks = install_tasks(base)
    except RuntimeError as exc:
        print(f"Scheduler error: {exc}", file=sys.stderr)
        print("Re-run as administrator if needed.", file=sys.stderr)
        return 1

    cfg = load_config(base)
    print("Scheduled tasks installed:")
    for name in tasks:
        print(f"  - {name}")
    print(f"  Startup: {cfg['startup_delay_minutes']} min after boot")
    print(f"  Daily: {cfg['schedule_time']}")
    if not cfg["ntfy"]["url"]:
        print("  Note: ntfy is not configured yet. Use config-set to add your topic URL and credentials.")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    base = _base_dir(args.dir)
    try:
        result = run_check(base, notify=not args.no_notify)
        print(result.message)
        return 0
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1


def _cmd_config_show(args: argparse.Namespace) -> int:
    base = _base_dir(args.dir)
    cfg = load_config(base)
    print(yaml.dump(cfg, default_flow_style=False, allow_unicode=True, sort_keys=False))
    return 0


def _cmd_config_set(args: argparse.Namespace) -> int:
    base = _base_dir(args.dir)
    cfg = load_config(base)
    key = args.key
    value = args.value

    mapping = {
        "source-url": "source_url",
        "schedule-time": "schedule_time",
        "startup-delay": "startup_delay_minutes",
        "reinstall-wait": "reinstall_wait_seconds",
        "ntfy-url": ("ntfy", "url"),
        "ntfy-user": ("ntfy", "user"),
        "ntfy-password": ("ntfy", "password"),
    }

    if key not in mapping:
        print(f"Unknown key: {key}", file=sys.stderr)
        print(f"Valid keys: {', '.join(mapping)}", file=sys.stderr)
        return 1

    target = mapping[key]
    if isinstance(target, tuple):
        section, field = target
        if section not in cfg:
            cfg[section] = {}
        if key in ("startup-delay", "reinstall-wait"):
            cfg[section][field] = int(value)
        else:
            cfg[section][field] = value
    elif key in ("startup-delay", "reinstall-wait"):
        cfg[target] = int(value)
    else:
        cfg[target] = value

    path = save_config(cfg, base)
    print(f"Config saved: {path}")

    if args.reinstall_tasks:
        try:
            install_tasks(base)
            print("Scheduled tasks updated.")
        except RuntimeError as exc:
            print(f"Scheduled tasks not updated: {exc}", file=sys.stderr)
            return 1
    return 0


def _cmd_uninstall(args: argparse.Namespace) -> int:
    base = _base_dir(args.dir)
    names = remove_tasks(base)
    print("Scheduled tasks removed:")
    for name in names:
        print(f"  - {name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rdpwrap-watcher",
        description="Watch and update rdpwrap.ini from the Seba source.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--dir",
        help="RDPWrap folder (default: current directory)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="Initialize config.yaml and install scheduled tasks")

    run_p = sub.add_parser("run", help="Run an immediate one-shot check")
    run_p.add_argument("--no-notify", action="store_true", help="Disable ntfy notifications")

    sub.add_parser("config-show", help="Show the current configuration")

    set_p = sub.add_parser("config-set", help="Update a configuration value")
    set_p.add_argument("key", help="Key (source-url, schedule-time, startup-delay, ...)")
    set_p.add_argument("value", help="New value")
    set_p.add_argument(
        "--reinstall-tasks",
        action="store_true",
        help="Recreate scheduled tasks after changing schedule settings",
    )

    sub.add_parser("uninstall", help="Remove Windows scheduled tasks")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "setup": _cmd_setup,
        "run": _cmd_run,
        "config-show": _cmd_config_show,
        "config-set": _cmd_config_set,
        "uninstall": _cmd_uninstall,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
