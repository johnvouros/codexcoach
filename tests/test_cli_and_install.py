from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codex_coach.cli import main
from codex_coach.install import install_from_source, uninstall
from codex_coach.paths import default_paths


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_CODEX = ROOT / "tests" / "fixtures" / "codex"


class CliAndInstallTests(unittest.TestCase):
    def test_cli_scan_report_and_suggestions_write_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            coach_home = home / ".codex-coach"
            code = main(["--home", str(home), "--codex-home", str(FIXTURE_CODEX), "--coach-home", str(coach_home), "scan", "--since", "3650d"])
            self.assertEqual(code, 0)
            facts_path = coach_home / "facts" / "latest.json"
            self.assertTrue(facts_path.exists())
            self.assertTrue((coach_home / "instructions" / "index.json").exists())
            facts = json.loads(facts_path.read_text(encoding="utf-8"))
            self.assertEqual(facts["totals"]["sessions"], 2)
            self.assertIn("instruction_audit", facts)

            code = main(["--home", str(home), "--codex-home", str(FIXTURE_CODEX), "--coach-home", str(coach_home), "report", "--since", "3650d"])
            self.assertEqual(code, 0)
            self.assertTrue((coach_home / "reports" / "latest.md").exists())
            report = coach_home / "reports" / "latest.md"
            self.assertIn("| Generated | Window | Mode |", report.read_text(encoding="utf-8"))
            self.assertIn("| `3650d` | `beginner` |", report.read_text(encoding="utf-8"))
            self.assertIn("No previous report detected yet", report.read_text(encoding="utf-8"))
            self.assertTrue((coach_home / "facts" / "report-latest.json").exists())

            code = main(
                [
                    "--home",
                    str(home),
                    "--codex-home",
                    str(FIXTURE_CODEX),
                    "--coach-home",
                    str(coach_home),
                    "report",
                    "--since",
                    "3650d",
                    "--mode",
                    "expert",
                ]
            )
            self.assertEqual(code, 0)
            self.assertIn("## Expert Metrics", report.read_text(encoding="utf-8"))
            self.assertIn("Previous baseline: generated", report.read_text(encoding="utf-8"))

            code = main(["--home", str(home), "--codex-home", str(FIXTURE_CODEX), "--coach-home", str(coach_home), "suggest-config", "--since", "3650d"])
            self.assertEqual(code, 0)
            self.assertTrue(list((coach_home / "suggestions").glob("*.patch.md")))

            code = main(
                [
                    "--home",
                    str(home),
                    "--codex-home",
                    str(FIXTURE_CODEX),
                    "--coach-home",
                    str(coach_home),
                    "instructions",
                    "scan",
                    "--since",
                    "3650d",
                ]
            )
            self.assertEqual(code, 0)
            code = main(
                [
                    "--home",
                    str(home),
                    "--codex-home",
                    str(FIXTURE_CODEX),
                    "--coach-home",
                    str(coach_home),
                    "instructions",
                    "report",
                    "--since",
                    "3650d",
                ]
            )
            self.assertEqual(code, 0)
            self.assertTrue((coach_home / "reports" / "instructions-latest.md").exists())
            code = main(
                [
                    "--home",
                    str(home),
                    "--codex-home",
                    str(FIXTURE_CODEX),
                    "--coach-home",
                    str(coach_home),
                    "instructions",
                    "suggest",
                    "--since",
                    "3650d",
                ]
            )
            self.assertEqual(code, 0)

    def test_install_and_uninstall_copy_plugin_skill_and_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            paths = default_paths(home=home, codex_home=home / ".codex", coach_home=home / ".codex-coach")
            result = install_from_source(ROOT, paths, schedule="none")

            self.assertTrue(Path(result["command"]).exists())
            self.assertTrue((home / "plugins" / "codex-coach" / ".codex-plugin" / "plugin.json").exists())
            self.assertTrue((home / ".codex" / "skills" / "codex-coach" / "SKILL.md").exists())
            self.assertFalse((home / ".agents" / "skills" / "codex-coach" / "SKILL.md").exists())
            marketplace = home / ".agents" / "plugins" / "marketplace.json"
            self.assertTrue(marketplace.exists())
            data = json.loads(marketplace.read_text(encoding="utf-8"))
            self.assertEqual(data["plugins"][0]["name"], "codex-coach")

            removed = uninstall(paths)
            self.assertIn(str(home / ".local" / "bin" / "codex-coach"), removed)
            self.assertFalse((home / "plugins" / "codex-coach").exists())

    def test_reinstall_from_installed_app_does_not_delete_itself(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            paths = default_paths(home=home, codex_home=home / ".codex", coach_home=home / ".codex-coach")
            install_from_source(ROOT, paths, schedule="none")

            result = install_from_source(paths.app_dir, paths, schedule="none")

            self.assertTrue(paths.app_dir.exists())
            self.assertTrue((paths.app_dir / "src" / "codex_coach" / "cli.py").exists())
            self.assertTrue(Path(result["command"]).exists())

    def test_install_removes_legacy_duplicate_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            paths = default_paths(home=home, codex_home=home / ".codex", coach_home=home / ".codex-coach")
            legacy = home / ".agents" / "skills" / "codex-coach"
            legacy.mkdir(parents=True)
            (legacy / "SKILL.md").write_text("---\nname: codex-coach\n---\nold copy\n", encoding="utf-8")

            install_from_source(ROOT, paths, schedule="none")

            self.assertTrue((home / ".codex" / "skills" / "codex-coach" / "SKILL.md").exists())
            self.assertFalse(legacy.exists())

    def test_cli_accepts_daily_schedule_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            code = main(["--home", str(home), "install", "--source-root", str(ROOT), "--schedule", "daily"])
            self.assertEqual(code, 0)
            config = home / ".codex-coach" / "config.toml"
            self.assertIn('schedule = "daily"', config.read_text(encoding="utf-8"))

    def test_lint_prompt_scores_and_rewrites_one_prompt(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = main(["lint-prompt", "fix"])
        self.assertEqual(code, 2)
        text = output.getvalue()
        self.assertIn("Score: 3/10", text)
        self.assertIn("Missing: target, success state", text)
        self.assertIn("Try: [Action] in [project/file]", text)

        output = StringIO()
        with redirect_stdout(output):
            code = main(["lint-prompt", "--json", "Fix auth and verify pytest passes"])
        self.assertEqual(code, 0)
        payload = json.loads(output.getvalue())
        self.assertIn("rewrite", payload)


if __name__ == "__main__":
    unittest.main()
