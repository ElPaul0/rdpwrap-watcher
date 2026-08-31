# RDPWrap Watcher

Portable Python app that watches and automatically updates `rdpwrap.ini` from the [sebaxakerhtc](https://github.com/sebaxakerhtc/rdpwrap.ini) source, then reinstalls RDPWrap when the file changes.

Designed to run directly inside your RDPWrap folder on a Windows VM (next to `rdpwrap.ini` and `RDPWInst.exe`).

---

## What it does

After a Windows update, RDPWrap often needs an up-to-date `rdpwrap.ini`. This watcher:

1. Downloads the remote source file from GitHub
2. Compares the **SHA256 hash** with the local file
3. If different → replaces `rdpwrap.ini` and reinstalls RDPWrap
4. Sends an **ntfy** notification based on the result

---

## Requirements

- **Windows** (server VM)
- **Python 3** installed
- **Administrator rights** for `setup` (RDPWInst + scheduled tasks)
- Network access to GitHub and your ntfy server

---

## Installation

### 1. Copy files into the RDPWrap folder

Your RDPWrap folder should look like this:

```
C:\RDPWrap\                     ← example path
├── rdpwrap.ini
├── RDPWInst.exe
├── rdpwrap-watcher.bat
├── requirements.txt
├── config.yaml.example
└── rdpwrap_watcher\
    ├── __init__.py
    ├── __main__.py
    ├── cli.py
    ├── config.py
    ├── ntfy.py
    ├── scheduler.py
    └── watcher.py
```

> **Important**: always run commands **from this folder** (where `rdpwrap.ini` and `RDPWInst.exe` live).

### 2. Install Python dependencies (one time)

Open PowerShell or CMD in the RDPWrap folder:

```powershell
pip install -r requirements.txt
```

Dependencies: `pyyaml`, `requests`.

### 3. Initial setup (as administrator)

Right-click PowerShell → **Run as administrator**, then:

```powershell
cd C:\RDPWrap
.\rdpwrap-watcher.bat setup
```

Setup will:
- create `config.yaml` (if missing)
- generate `run-watcher.bat` (script used by the scheduler)
- install **2 Windows scheduled tasks**:
  - **RDPWrapWatcher-Startup** → 5 min after each boot
  - **RDPWrapWatcher-Daily** → every day at 03:00

### 4. Configure ntfy

After setup, configure your notification topic:

```powershell
.\rdpwrap-watcher.bat config-set ntfy-url https://your-ntfy-server/your-topic
.\rdpwrap-watcher.bat config-set ntfy-user your-username
.\rdpwrap-watcher.bat config-set ntfy-password your-password
```

Credentials are stored locally in `config.yaml` (gitignored). They are not included in the repository.

---

## Commands

All commands go through the `.bat` launcher or Python directly:

```powershell
.\rdpwrap-watcher.bat <command>
# or
python -m rdpwrap_watcher <command>
```

| Command | Description |
|---|---|
| `setup` | Create config + install scheduled tasks |
| `run` | **Immediate** one-shot check |
| `run --no-notify` | Same, without ntfy notifications |
| `config-show` | Show current configuration |
| `config-set <key> <value>` | Update a setting |
| `uninstall` | Remove scheduled tasks |

### Examples

```powershell
# Manual check right now
.\rdpwrap-watcher.bat run

# Show config
.\rdpwrap-watcher.bat config-show

# Change daily check time (recreates scheduled tasks)
.\rdpwrap-watcher.bat config-set schedule-time 04:30 --reinstall-tasks

# Change startup delay after Windows boot
.\rdpwrap-watcher.bat config-set startup-delay 10 --reinstall-tasks

# Change source URL
.\rdpwrap-watcher.bat config-set source-url https://raw.githubusercontent.com/sebaxakerhtc/rdpwrap.ini/master/rdpwrap.ini

# Configure ntfy
.\rdpwrap-watcher.bat config-set ntfy-url https://your-ntfy-server/your-topic
.\rdpwrap-watcher.bat config-set ntfy-user your-username
.\rdpwrap-watcher.bat config-set ntfy-password your-password

# Remove scheduled tasks
.\rdpwrap-watcher.bat uninstall
```

### Available `config-set` keys

| CLI key | YAML setting | Description |
|---|---|---|
| `source-url` | `source_url` | Raw URL of the remote ini file |
| `schedule-time` | `schedule_time` | Daily check time (`HH:MM`) |
| `startup-delay` | `startup_delay_minutes` | Minutes after boot before check |
| `reinstall-wait` | `reinstall_wait_seconds` | Pause between uninstall and reinstall |
| `ntfy-url` | `ntfy.url` | ntfy topic URL |
| `ntfy-user` | `ntfy.user` | ntfy username |
| `ntfy-password` | `ntfy.password` | ntfy password |

> Add `--reinstall-tasks` after changing schedule time or startup delay to update scheduled tasks.

---

## Configuration (`config.yaml`)

Created automatically on `setup`. See `config.yaml.example` for the full template.

```yaml
source_url: https://raw.githubusercontent.com/sebaxakerhtc/rdpwrap.ini/master/rdpwrap.ini
local_ini: rdpwrap.ini
rdpwinst: RDPWInst.exe
schedule_time: "03:00"
startup_delay_minutes: 5
reinstall_wait_seconds: 5
ntfy:
  url: https://your-ntfy-server/your-topic
  user: your-username
  password: your-password
task_names:
  startup: RDPWrapWatcher-Startup
  daily: RDPWrapWatcher-Daily
```

You can edit this file manually or via `config-set` / `config-show`.

> **Note**: always use the GitHub **raw** URL (`raw.githubusercontent.com/...`), not the `blob/` URL which returns HTML.

---

## How it works

On each run (manual or scheduled):

```
Download remote ini
        ↓
Compare SHA256 with local rdpwrap.ini
        ↓
   Match? ──→ ntfy notification (medium priority) → Done
        ↓ No
Backup current file in memory
        ↓
Write new rdpwrap.ini
        ↓
RDPWInst.exe -u -k
        ↓
Wait 5 seconds
        ↓
RDPWInst.exe -i
        ↓
   Failed? ──→ Restore previous ini → ntfy notification (max priority)
        ↓ OK
ntfy notification (high priority) → Done
```

---

## ntfy notifications

| Situation | Priority | Meaning |
|---|---|---|
| All good, no change | **medium** (3) | Nothing to do |
| Ini updated + reinstall OK | **high** (4) | Action completed |
| Error (network, RDPWInst, etc.) | **max** (5) | Manual intervention needed |

Notifications are skipped if `ntfy.url` is not configured.

---

## Windows scheduled tasks

Check them in **Task Scheduler** (`taskschd.msc`):

| Name | Trigger | Privileges |
|---|---|---|
| `RDPWrapWatcher-Startup` | At startup, +5 min delay | Highest |
| `RDPWrapWatcher-Daily` | Daily at 03:00 | Highest |

Both tasks run `run-watcher.bat`, generated automatically during setup.

To remove them: `.\rdpwrap-watcher.bat uninstall`

Quick check from PowerShell:

```powershell
Get-ScheduledTask -TaskName "RDPWrapWatcher-*" | Format-Table TaskName, State
```

---

## Troubleshooting

### Setup fails on scheduled tasks
→ Re-run PowerShell **as administrator**.

### `RDPWInst.exe not found`
→ Make sure you are in the RDPWrap folder and `RDPWInst.exe` is present.

### No ntfy notification
→ Check that ntfy is configured: `.\rdpwrap-watcher.bat config-show`
→ Verify your ntfy server is reachable from the VM.
→ Test manually: `.\rdpwrap-watcher.bat run`

### Force a check without notifications (debug)
```powershell
python -m rdpwrap_watcher run --no-notify
```

### Use a different RDPWrap folder
```powershell
python -m rdpwrap_watcher run --dir "D:\Path\To\RDPWrap"
```

### View scheduled task history
→ Task Scheduler → Task Scheduler Library → right-click the task → **History**.

---

## Project files

| File | Role |
|---|---|
| `rdpwrap-watcher.bat` | Main launcher |
| `rdpwrap_watcher/` | Python watcher code |
| `config.yaml` | Active config (created on setup, gitignored) |
| `config.yaml.example` | Reference template |
| `run-watcher.bat` | Generated script for the scheduler |
| `requirements.txt` | pip dependencies |

---

## Quick reference

```powershell
# First time
pip install -r requirements.txt
.\rdpwrap-watcher.bat setup          # run as admin
.\rdpwrap-watcher.bat config-set ntfy-url https://your-ntfy-server/your-topic
.\rdpwrap-watcher.bat config-set ntfy-user your-username
.\rdpwrap-watcher.bat config-set ntfy-password your-password

# Manual check
.\rdpwrap-watcher.bat run

# View / update config
.\rdpwrap-watcher.bat config-show
.\rdpwrap-watcher.bat config-set schedule-time 03:00 --reinstall-tasks

# Remove everything
.\rdpwrap-watcher.bat uninstall
```
