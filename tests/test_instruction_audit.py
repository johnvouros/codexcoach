from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codex_coach.instruction_audit import analyze_instructions
from codex_coach.parser import scan_logs
from codex_coach.reports import write_instruction_suggestion_files


def write_session(codex_home: Path, cwd: Path, *, tool_calls: int = 0) -> None:
    session_path = codex_home / "sessions" / "2026" / "05" / "21" / f"{cwd.name}.jsonl"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        {
            "timestamp": "2026-05-21T00:00:00Z",
            "type": "session_meta",
            "payload": {"id": f"{cwd.name}-session", "cwd": str(cwd), "source": "cli"},
        },
        {
            "timestamp": "2026-05-21T00:01:00Z",
            "type": "turn_context",
            "payload": {"turn_id": "turn-1", "cwd": str(cwd), "model": "gpt-5", "effort": "medium"},
        },
        {
            "timestamp": "2026-05-21T00:01:10Z",
            "type": "response_item",
            "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "fix"}]},
        },
    ]
    for index in range(tool_calls):
        lines.append(
            {
                "timestamp": "2026-05-21T00:01:20Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": json.dumps({"cmd": f"python scripts/task_{index}.py"}),
                },
            }
        )
    session_path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")


class InstructionAuditTests(unittest.TestCase):
    def test_instruction_audit_flags_secret_mode_lock_scope_leak_without_leaking_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            codex_home = home / ".codex"
            codex_home.mkdir()
            project = home / "private-app"
            project.mkdir()
            secret = "fake-secret-token-000000000000"
            (project / "AGENTS.md").write_text(
                f"Understand: Research only.\ntoken={secret}\nKeep answers short.\n",
                encoding="utf-8",
            )
            (codex_home / "config.toml").write_text(
                'style = "dark mode neon Tailwind operator-grade UI"\n',
                encoding="utf-8",
            )
            write_session(codex_home, project, tool_calls=6)

            facts = scan_logs(codex_home)
            audit = analyze_instructions(home, codex_home, usage_facts=facts)

            self.assertEqual(audit["status"], "needs_review")
            self.assertGreaterEqual(audit["files_reviewed"], 2)
            titles = {item["title"] for item in audit["findings"]}
            self.assertIn("Potential secret in instruction file", titles)
            self.assertIn("Mode lock may be stale", titles)
            self.assertIn("Project-specific preference may be global", titles)
            suggestion_titles = {item["title"] for item in audit["suggestions"]}
            self.assertIn("Add a verification rule", suggestion_titles)
            self.assertNotIn(secret, json.dumps(audit))

    def test_instruction_audit_recommends_project_playbook_for_active_project_without_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            codex_home = home / ".codex"
            codex_home.mkdir()
            project = home / "project-without-playbook"
            project.mkdir()
            write_session(codex_home, project)

            facts = scan_logs(codex_home)
            audit = analyze_instructions(home, codex_home, usage_facts=facts)

            titles = {item["title"] for item in audit["findings"]}
            self.assertIn("Active project has no discovered AGENTS.md", titles)
            suggestion_titles = {item["title"] for item in audit["suggestions"]}
            self.assertIn("Add a small project playbook", suggestion_titles)

            written = write_instruction_suggestion_files(audit, home / ".codex-coach" / "suggestions")
            self.assertTrue(written)
            content = written[0].read_text(encoding="utf-8")
            self.assertIn("Paste into:", content)
            self.assertIn("```md", content)


if __name__ == "__main__":
    unittest.main()
