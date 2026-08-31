"""Windows Task Scheduler integration."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .config import load_config

RUNNER_BAT = "run-watcher.bat"


def _runner_script(base_dir: Path) -> Path:
    return base_dir / RUNNER_BAT


def _write_runner(base_dir: Path) -> Path:
    exe = Path(sys.executable).resolve()
    root = base_dir.resolve()
    content = f"""@echo off
cd /d "{root}"
set "PYTHONPATH={root};%PYTHONPATH%"
"{exe}" -m rdpwrap_watcher run --dir "{root}"
"""
    path = _runner_script(base_dir)
    path.write_text(content, encoding="utf-8")
    return path


def _run_schtasks(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["schtasks", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _delete_task(name: str) -> None:
    _run_schtasks(["/Delete", "/TN", name, "/F"])


def _create_startup_task(task_name: str, runner: Path, delay_minutes: int) -> None:
    runner_cmd = str(runner.resolve())
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <BootTrigger>
      <Delay>PT{delay_minutes}M</Delay>
      <Enabled>true</Enabled>
    </BootTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <Enabled>true</Enabled>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{runner_cmd}</Command>
    </Exec>
  </Actions>
</Task>"""
    xml_path = runner.parent / "_startup_task.xml"
    xml_path.write_text(xml, encoding="utf-16")
    try:
        result = _run_schtasks(["/Create", "/TN", task_name, "/XML", str(xml_path), "/F"])
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    finally:
        xml_path.unlink(missing_ok=True)


def _create_daily_task(task_name: str, runner: Path, schedule_time: str) -> None:
    result = _run_schtasks([
        "/Create",
        "/TN", task_name,
        "/TR", str(runner.resolve()),
        "/SC", "DAILY",
        "/ST", schedule_time,
        "/RL", "HIGHEST",
        "/F",
    ])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def install_tasks(base_dir: Path) -> list[str]:
    cfg = load_config(base_dir)
    runner = _write_runner(base_dir)
    startup_name = cfg["task_names"]["startup"]
    daily_name = cfg["task_names"]["daily"]
    delay = int(cfg["startup_delay_minutes"])
    schedule_time = cfg["schedule_time"]

    _delete_task(startup_name)
    _delete_task(daily_name)
    _create_startup_task(startup_name, runner, delay)
    _create_daily_task(daily_name, runner, schedule_time)

    return [startup_name, daily_name]


def remove_tasks(base_dir: Path) -> list[str]:
    cfg = load_config(base_dir)
    names = [cfg["task_names"]["startup"], cfg["task_names"]["daily"]]
    for name in names:
        _delete_task(name)
    runner = _runner_script(base_dir)
    runner.unlink(missing_ok=True)
    return names
