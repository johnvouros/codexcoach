from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CoachPaths:
    home: Path
    codex_home: Path
    coach_home: Path

    @property
    def reports_dir(self) -> Path:
        return self.coach_home / "reports"

    @property
    def facts_dir(self) -> Path:
        return self.coach_home / "facts"

    @property
    def suggestions_dir(self) -> Path:
        return self.coach_home / "suggestions"

    @property
    def instructions_dir(self) -> Path:
        return self.coach_home / "instructions"

    @property
    def config_file(self) -> Path:
        return self.coach_home / "config.toml"

    @property
    def app_dir(self) -> Path:
        return self.coach_home / "app"

    def ensure_output_dirs(self) -> None:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.facts_dir.mkdir(parents=True, exist_ok=True)
        self.suggestions_dir.mkdir(parents=True, exist_ok=True)
        self.instructions_dir.mkdir(parents=True, exist_ok=True)


def default_paths(
    *,
    home: str | Path | None = None,
    codex_home: str | Path | None = None,
    coach_home: str | Path | None = None,
) -> CoachPaths:
    home_path = Path(home or os.environ.get("HOME") or Path.home()).expanduser()
    codex_path = Path(codex_home or os.environ.get("CODEX_HOME") or home_path / ".codex").expanduser()
    coach_path = Path(coach_home or os.environ.get("CODEX_COACH_HOME") or home_path / ".codex-coach").expanduser()
    return CoachPaths(home=home_path, codex_home=codex_path, coach_home=coach_path)
