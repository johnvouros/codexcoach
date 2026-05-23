from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PluginTests(unittest.TestCase):
    def test_plugin_manifest_has_required_public_fields(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "codex-coach")
        self.assertEqual(manifest["version"], "0.1.10")
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
        self.assertTrue((ROOT / "skills" / "codex-coach" / "references" / "privacy.md").exists())

    def test_npm_package_exposes_cli_and_assets(self) -> None:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

        self.assertEqual(package["name"], "codex-coach")
        self.assertEqual(package["version"], "0.1.10")
        self.assertEqual(package["bin"]["codex-coach"], "bin/codex-coach.js")
        self.assertIn("assets/", package["files"])
        self.assertTrue((ROOT / "bin" / "codex-coach.js").exists())
        self.assertTrue((ROOT / "assets" / "brand" / "codex-coach-logo.png").exists())


if __name__ == "__main__":
    unittest.main()
