from __future__ import annotations

import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from codex_coach.parser import scan_logs
from codex_coach.prompts import score_prompt
from codex_coach.reports import render_markdown_report, write_suggestion_files
from codex_coach.timeutil import parse_since


FIXTURE_CODEX = Path(__file__).parent / "fixtures" / "codex"


class ScanTests(unittest.TestCase):
    def test_scan_reads_sessions_archives_and_redacts_prompt_examples(self) -> None:
        facts = scan_logs(FIXTURE_CODEX)

        self.assertEqual(facts["totals"]["files_scanned"], 2)
        self.assertEqual(facts["totals"]["sessions"], 2)
        self.assertEqual(facts["totals"]["turns"], 3)
        self.assertEqual(facts["totals"]["user_messages"], 3)
        self.assertEqual(facts["totals"]["verification_tool_calls"], 2)
        self.assertEqual(facts["totals"]["compactions"], 1)
        self.assertEqual(facts["totals"]["malformed_lines"], 1)
        token_usage = facts["token_efficiency"]["usage"]
        self.assertEqual(token_usage["input_tokens"], 53000)
        self.assertEqual(token_usage["cached_input_tokens"], 43700)
        self.assertEqual(token_usage["uncached_input_tokens"], 9300)
        self.assertEqual(token_usage["output_tokens"], 1200)
        self.assertEqual(facts["token_efficiency"]["max_last_input_tokens"], 50000)
        self.assertIn("exec_command", facts["tools"])
        self.assertIn("medium", facts["efforts"])
        self.assertTrue(facts["project_capsules"])
        self.assertEqual(facts["project_capsules"][0]["likely_workflow"], "terminal-heavy implementation or diagnosis")

        needs_work = facts["prompt_quality"]["examples_needing_work"]
        self.assertTrue(needs_work)
        self.assertIn("rewrite", needs_work[0])
        self.assertIn("target", needs_work[0]["missing"])
        serialized = json.dumps(facts)
        self.assertNotIn("sk-live-secretsecretsecretsecretsecret", serialized)
        self.assertNotIn("/home/alice/private-app/src/auth.py", serialized)
        self.assertNotIn("https://example.com/private-ticket", serialized)

    def test_since_filter_limits_old_archived_session(self) -> None:
        since_dt = parse_since("2026-05-21T00:00:00Z", now=datetime(2026, 5, 21, tzinfo=UTC))
        facts = scan_logs(FIXTURE_CODEX, since_dt=since_dt, since_label="2026-05-21T00:00:00Z")

        self.assertEqual(facts["totals"]["sessions"], 1)
        self.assertEqual(facts["totals"]["turns"], 2)
        self.assertEqual(facts["totals"]["user_messages"], 2)

    def test_report_omits_raw_private_values(self) -> None:
        facts = scan_logs(FIXTURE_CODEX)
        report = render_markdown_report(facts, generated_at=datetime(2026, 5, 21, tzinfo=UTC), expert=True)

        self.assertIn("# Codex Coach Report", report)
        self.assertIn("Token Efficiency", report)
        self.assertIn("43,700 cached", report)
        self.assertIn("9,300 uncached", report)
        self.assertIn("Plain English:", report)
        self.assertIn("Paste into:", report)
        self.assertIn("Prompt Quality", report)
        self.assertIn("Project Capsules", report)
        self.assertIn("Prompt rewrites to try", report)
        self.assertIn("[medium]", report)
        self.assertNotIn("sk-live-secretsecretsecretsecretsecret", report)
        self.assertNotIn("/home/alice/private-app/src/auth.py", report)
        self.assertNotIn("https://example.com/private-ticket", report)

    def test_suggestion_files_are_review_artifacts(self) -> None:
        facts = scan_logs(FIXTURE_CODEX)
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            written = write_suggestion_files(facts, Path(tmp))
            self.assertTrue(written)
            content = written[0].read_text(encoding="utf-8")
            self.assertIn("never edits your instructions automatically", content)
            self.assertIn("Paste into:", content)

    def test_machine_context_and_skill_invocations_are_not_prompt_rewrite_targets(self) -> None:
        self.assertEqual(score_prompt("<environment_context><cwd>/tmp/app</cwd></environment_context>").category, "good")
        self.assertEqual(score_prompt("[$codex-security:security-scan](/tmp/skill)").category, "good")


if __name__ == "__main__":
    unittest.main()
