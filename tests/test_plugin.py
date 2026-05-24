from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PluginTests(unittest.TestCase):
    def test_plugin_manifest_has_required_public_fields(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "codex-coach")
        self.assertEqual(manifest["version"], "0.1.12")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["interface"]["displayName"], "Codex Coach")
        self.assertLessEqual(len(manifest["interface"]["defaultPrompt"]), 3)
        self.assertNotIn("[TODO", json.dumps(manifest))

    def test_skill_and_references_exist(self) -> None:
        skill = ROOT / "skills" / "codex-coach" / "SKILL.md"
        self.assertTrue(skill.exists())
        text = skill.read_text(encoding="utf-8")
        self.assertIn("name: codex-coach", text)
        self.assertIn("codex-coach report --since 7d", text)
        self.assertIn("clickable absolute Markdown links", text)
        self.assertIn("[latest.md](/home/example/.codex-coach/reports/latest.md)", text)
        self.assertTrue((ROOT / "skills" / "codex-coach" / "references" / "privacy.md").exists())

    def test_npm_package_exposes_cli_and_assets(self) -> None:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

        self.assertEqual(package["name"], "codex-coach")
        self.assertEqual(package["version"], "0.1.12")
        self.assertEqual(package["bin"]["codex-coach"], "bin/codex-coach.js")
        self.assertIn("assets/", package["files"])
        self.assertIn("docs/", package["files"])
        self.assertTrue((ROOT / "bin" / "codex-coach.js").exists())
        self.assertTrue((ROOT / "assets" / "brand" / "codex-coach-logo.png").exists())
        self.assertTrue((ROOT / "docs" / "demo-report.md").exists())

    def test_readme_has_beginner_quick_start_and_heartbeat(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("## Quick Start", readme)
        self.assertIn("npm install -g codex-coach", readme)
        self.assertIn("Coach my Codex usage", readme)
        self.assertIn("[demo report](docs/demo-report.md)", readme)
        self.assertIn("## Weekly Heartbeat", readme)
        self.assertIn("Set a weekly Codex Coach check-in every 7 days", readme)


if __name__ == "__main__":
    unittest.main()
