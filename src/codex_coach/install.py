from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .paths import CoachPaths

PLUGIN_NAME = "codex-coach"


def install_from_source(source_root: Path, paths: CoachPaths, *, schedule: str = "weekly") -> dict[str, str]:
    source_root = source_root.resolve()
    paths.ensure_output_dirs()
    paths.coach_home.mkdir(parents=True, exist_ok=True)
    _write_default_config(paths, schedule=schedule)
    if source_root != paths.app_dir.resolve():
        _copy_app(source_root, paths.app_dir)
    _install_command(paths)
    plugin_path = _install_plugin(source_root, paths.home)
    skill_paths = _install_user_skills(source_root, paths)
    marketplace = _update_marketplace(paths.home, plugin_path)
    scheduler = _write_scheduler(paths, schedule=schedule)
    return {
        "coach_home": str(paths.coach_home),
        "command": str(paths.home / ".local" / "bin" / "codex-coach"),
        "plugin": str(plugin_path),
        "skills": ", ".join(str(path) for path in skill_paths),
        "marketplace": str(marketplace),
        "scheduler": str(scheduler) if scheduler else "not configured",
    }


def uninstall(paths: CoachPaths) -> list[str]:
    removed: list[str] = []
    command = paths.home / ".local" / "bin" / "codex-coach"
    if command.exists():
        command.unlink()
        removed.append(str(command))
    for target in (
        paths.home / "plugins" / PLUGIN_NAME,
        paths.home / ".agents" / "skills" / PLUGIN_NAME,
        paths.home / ".codex" / "skills" / PLUGIN_NAME,
    ):
        if target.exists():
            shutil.rmtree(target)
            removed.append(str(target))
    _remove_marketplace_entry(paths.home)
    for target in _scheduler_paths(paths):
        if target.exists():
            target.unlink()
            removed.append(str(target))
    return removed


def _copy_app(source_root: Path, app_dir: Path) -> None:
    if app_dir.exists():
        shutil.rmtree(app_dir)
    ignore = shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache", "dist", "build", "*.egg-info")
    shutil.copytree(source_root, app_dir, ignore=ignore)


def _install_command(paths: CoachPaths) -> None:
    bin_dir = paths.home / ".local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    command = bin_dir / "codex-coach"
    python = os.environ.get("PYTHON", "python3")
    command.write_text(
        "#!/usr/bin/env sh\n"
        "set -eu\n"
        f'PYTHONPATH="{paths.app_dir / "src"}${{PYTHONPATH:+:$PYTHONPATH}}" exec {python} -m codex_coach.cli "$@"\n',
        encoding="utf-8",
    )
    command.chmod(0o755)


def _install_plugin(source_root: Path, home: Path) -> Path:
    plugin_root = home / "plugins" / PLUGIN_NAME
    if plugin_root.exists():
        shutil.rmtree(plugin_root)
    plugin_root.mkdir(parents=True, exist_ok=True)
    for name in (".codex-plugin", "skills", "README.md", "LICENSE"):
        source = source_root / name
        target = plugin_root / name
        if source.is_dir():
            shutil.copytree(source, target)
        elif source.exists():
            shutil.copy2(source, target)
    return plugin_root


def _install_user_skills(source_root: Path, paths: CoachPaths) -> list[Path]:
    skill_source = source_root / "skills" / PLUGIN_NAME
    target = paths.codex_home / "skills" / PLUGIN_NAME
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill_source, target)
    _remove_legacy_duplicate_skill(paths.home, target)
    return [target]


def _remove_legacy_duplicate_skill(home: Path, canonical_target: Path) -> None:
    legacy_target = home / ".agents" / "skills" / PLUGIN_NAME
    if legacy_target.resolve() == canonical_target.resolve() or not legacy_target.exists():
        return
    skill_file = legacy_target / "SKILL.md"
    try:
        skill_text = skill_file.read_text(encoding="utf-8")
    except OSError:
        return
    if f"name: {PLUGIN_NAME}" in skill_text:
        shutil.rmtree(legacy_target)


def _update_marketplace(home: Path, plugin_path: Path) -> Path:
    marketplace = home / ".agents" / "plugins" / "marketplace.json"
    marketplace.parent.mkdir(parents=True, exist_ok=True)
    if marketplace.exists():
        try:
            data = json.loads(marketplace.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = _new_marketplace()
    else:
        data = _new_marketplace()
    plugins = [item for item in data.get("plugins", []) if item.get("name") != PLUGIN_NAME]
    plugins.append(
        {
            "name": PLUGIN_NAME,
            "source": {"source": "local", "path": "./plugins/codex-coach"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        }
    )
    data["plugins"] = plugins
    marketplace.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return marketplace


def _remove_marketplace_entry(home: Path) -> None:
    marketplace = home / ".agents" / "plugins" / "marketplace.json"
    if not marketplace.exists():
        return
    try:
        data = json.loads(marketplace.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    data["plugins"] = [item for item in data.get("plugins", []) if item.get("name") != PLUGIN_NAME]
    marketplace.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _new_marketplace() -> dict:
    return {"name": "personal", "interface": {"displayName": "Personal"}, "plugins": []}


def _write_default_config(paths: CoachPaths, *, schedule: str) -> None:
    if paths.config_file.exists():
        return
    paths.config_file.write_text(
        "\n".join(
            [
                "# Codex Coach config",
                "redact_prompts = true",
                "include_source_code = false",
                f'schedule = "{schedule}"',
                'default_since = "7d"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_scheduler(paths: CoachPaths, *, schedule: str) -> Path | None:
    if schedule == "none":
        return None
    if schedule not in {"daily", "weekly"}:
        raise ValueError(f"unsupported schedule: {schedule}")
    systemd_dir = paths.home / ".config" / "systemd" / "user"
    if os.name == "posix" and Path("/run/systemd").exists():
        systemd_dir.mkdir(parents=True, exist_ok=True)
        service = systemd_dir / "codex-coach.service"
        timer = systemd_dir / "codex-coach.timer"
        service.write_text(
            "[Unit]\nDescription=Codex Coach report\n\n"
            "[Service]\nType=oneshot\n"
            f"ExecStart={paths.home / '.local' / 'bin' / 'codex-coach'} report --since 7d\n",
            encoding="utf-8",
        )
        calendar = "09:00" if schedule == "daily" else "Sun 09:00"
        timer.write_text(
            f"[Unit]\nDescription=Run Codex Coach {schedule}\n\n"
            f"[Timer]\nOnCalendar={calendar}\nPersistent=true\n\n"
            "[Install]\nWantedBy=timers.target\n",
            encoding="utf-8",
        )
        return timer

    launch_agents = paths.home / "Library" / "LaunchAgents"
    if os.name == "posix" and (paths.home / "Library").exists():
        launch_agents.mkdir(parents=True, exist_ok=True)
        plist = launch_agents / f"com.codex-coach.{schedule}.plist"
        interval = (
            "<dict><key>Hour</key><integer>9</integer></dict>"
            if schedule == "daily"
            else "<dict><key>Weekday</key><integer>0</integer><key>Hour</key><integer>9</integer></dict>"
        )
        plist.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.codex-coach.{schedule}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{paths.home / '.local' / 'bin' / 'codex-coach'}</string>
    <string>report</string>
    <string>--since</string>
    <string>7d</string>
  </array>
  <key>StartCalendarInterval</key>
  {interval}
</dict>
</plist>
""",
            encoding="utf-8",
        )
        return plist
    return None


def _scheduler_paths(paths: CoachPaths) -> list[Path]:
    return [
        paths.home / ".config" / "systemd" / "user" / "codex-coach.service",
        paths.home / ".config" / "systemd" / "user" / "codex-coach.timer",
        paths.home / "Library" / "LaunchAgents" / "com.codex-coach.weekly.plist",
        paths.home / "Library" / "LaunchAgents" / "com.codex-coach.daily.plist",
    ]
