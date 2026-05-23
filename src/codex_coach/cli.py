from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from .instruction_audit import analyze_instructions
from .install import install_from_source, uninstall
from .parser import iter_log_paths, scan_logs
from .paths import default_paths
from .prompts import score_prompt
from .reports import (
    render_instruction_report,
    render_markdown_report,
    write_instruction_suggestion_files,
    write_json_facts,
    write_markdown_report,
    write_suggestion_files,
)
from .timeutil import parse_since


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="codex-coach", description="Local-first Codex usage coach")
    parser.add_argument("--home", help="Override HOME for testing or portable installs")
    parser.add_argument("--codex-home", help="Override Codex home directory")
    parser.add_argument("--coach-home", help="Override Codex Coach output directory")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="Check local Codex Coach setup")

    scan = sub.add_parser("scan", help="Scan Codex logs and write JSON facts")
    scan.add_argument("--since", default="7d", help="Window such as 7d, 2w, 24h, or ISO timestamp")

    report = sub.add_parser("report", help="Write a Markdown coaching report")
    report.add_argument("--since", default="7d")
    report.add_argument("--mode", choices=("beginner", "expert"), default="beginner")
    report.add_argument("--expert", action="store_true", help="Include raw expert metrics")

    suggest = sub.add_parser("suggest-config", help="Write reviewable config suggestion files")
    suggest.add_argument("--since", default="7d")

    instructions = sub.add_parser("instructions", help="Audit Codex custom instructions and project AGENTS.md files")
    instructions_sub = instructions.add_subparsers(dest="instructions_command", required=True)
    instructions_scan = instructions_sub.add_parser("scan", help="Write instruction audit facts")
    instructions_scan.add_argument("--since", default="30d")
    instructions_report = instructions_sub.add_parser("report", help="Write an instruction playbook report")
    instructions_report.add_argument("--since", default="30d")
    instructions_suggest = instructions_sub.add_parser("suggest", help="Write reviewable instruction suggestion files")
    instructions_suggest.add_argument("--since", default="30d")

    lint = sub.add_parser("lint-prompt", help="Score one prompt and suggest a safer rewrite")
    lint.add_argument("prompt", nargs="*", help="Prompt text. Reads stdin when omitted.")
    lint.add_argument("--json", action="store_true", help="Write machine-readable JSON")

    install_cmd = sub.add_parser("install", help="Install command, plugin, skill, and default config")
    install_cmd.add_argument("--source-root", default=_repo_root(), help="Source checkout root")
    install_cmd.add_argument("--schedule", choices=("daily", "weekly", "none"), default="weekly")

    sub.add_parser("uninstall", help="Remove installed command, plugin, skill, and scheduler files")

    args = parser.parse_args(argv)
    paths = default_paths(home=args.home, codex_home=args.codex_home, coach_home=args.coach_home)

    try:
        if args.command == "doctor":
            return _doctor(paths)
        if args.command == "scan":
            facts = _scan(paths, args.since)
            print(f"Wrote facts to {paths.facts_dir / 'latest.json'}")
            return 0
        if args.command == "report":
            previous_facts = _read_json_facts(paths.facts_dir / "report-latest.json")
            facts = _scan(paths, args.since)
            generated_at = datetime.now(UTC)
            report_text = render_markdown_report(
                facts,
                generated_at=generated_at,
                expert=args.expert,
                mode=args.mode,
                previous_facts=previous_facts,
            )
            latest, weekly = write_markdown_report(report_text, paths.reports_dir, generated_at=generated_at)
            write_json_facts(facts, paths.facts_dir / "report-latest.json")
            print(f"Wrote report to {latest}")
            print(f"Wrote weekly copy to {weekly}")
            return 0
        if args.command == "suggest-config":
            facts = _scan(paths, args.since)
            written = write_suggestion_files(facts, paths.suggestions_dir)
            for path in written:
                print(f"Wrote suggestion {path}")
            return 0
        if args.command == "instructions":
            return _instructions(paths, args.instructions_command, args.since)
        if args.command == "lint-prompt":
            prompt_text = " ".join(args.prompt).strip() if args.prompt else sys.stdin.read().strip()
            return _lint_prompt(prompt_text, as_json=args.json)
        if args.command == "install":
            result = install_from_source(Path(args.source_root), paths, schedule=args.schedule)
            for key, value in result.items():
                print(f"{key}: {value}")
            return 0
        if args.command == "uninstall":
            removed = uninstall(paths)
            if removed:
                for path in removed:
                    print(f"Removed {path}")
            else:
                print("Nothing to remove")
            return 0
    except Exception as exc:  # noqa: BLE001 - CLI should provide a direct error.
        print(f"codex-coach: {exc}", file=sys.stderr)
        return 1
    return 1


def _scan(paths, since: str) -> dict:
    since_dt = parse_since(since)
    paths.ensure_output_dirs()
    facts = scan_logs(paths.codex_home, since_dt=since_dt, since_label=since)
    facts["instruction_audit"] = analyze_instructions(
        paths.home,
        paths.codex_home,
        since_dt=since_dt,
        since_label=since,
        usage_facts=facts,
    )
    facts["generated_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    write_json_facts(facts, paths.facts_dir / "latest.json")
    write_json_facts(facts["instruction_audit"], paths.instructions_dir / "index.json")
    return facts


def _read_json_facts(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _instructions(paths, command: str, since: str) -> int:
    facts = _scan(paths, since)
    audit = facts.get("instruction_audit", {})
    if command == "scan":
        print(f"Wrote instruction audit to {paths.instructions_dir / 'index.json'}")
        return 0
    if command == "report":
        generated_at = datetime.now(UTC)
        report_text = render_instruction_report(audit, generated_at=generated_at)
        paths.reports_dir.mkdir(parents=True, exist_ok=True)
        latest = paths.reports_dir / "instructions-latest.md"
        weekly = paths.reports_dir / f"instructions-{generated_at.date().isoformat()}.md"
        latest.write_text(report_text, encoding="utf-8")
        weekly.write_text(report_text, encoding="utf-8")
        print(f"Wrote instruction report to {latest}")
        print(f"Wrote dated copy to {weekly}")
        return 0
    if command == "suggest":
        written = write_instruction_suggestion_files(audit, paths.suggestions_dir)
        if written:
            for path in written:
                print(f"Wrote instruction suggestion {path}")
        else:
            print("No instruction suggestions found")
        return 0
    raise ValueError(f"unknown instructions command: {command}")


def _doctor(paths) -> int:
    log_paths = iter_log_paths(paths.codex_home)
    print(f"home: {paths.home}")
    print(f"codex_home: {paths.codex_home} {'OK' if paths.codex_home.exists() else 'MISSING'}")
    print(f"coach_home: {paths.coach_home}")
    print(f"log_files: {len(log_paths)}")
    print(f"reports_dir: {paths.reports_dir}")
    print(f"instructions_dir: {paths.instructions_dir}")
    command = paths.home / ".local" / "bin" / "codex-coach"
    print(f"command: {command} {'OK' if command.exists() else 'not installed'}")
    plugin = paths.home / "plugins" / "codex-coach" / ".codex-plugin" / "plugin.json"
    print(f"plugin: {plugin} {'OK' if plugin.exists() else 'not installed'}")
    skill = paths.codex_home / "skills" / "codex-coach" / "SKILL.md"
    legacy_skill = paths.home / ".agents" / "skills" / "codex-coach" / "SKILL.md"
    print(f"skill: {skill} {'OK' if skill.exists() else 'not installed'}")
    if legacy_skill.exists():
        print(f"legacy_skill: {legacy_skill} duplicate")
    return 0 if paths.codex_home.exists() else 1


def _lint_prompt(prompt_text: str, *, as_json: bool) -> int:
    score = score_prompt(prompt_text)
    result = {
        "score": score.score,
        "category": score.category,
        "reason": score.reason,
        "missing": list(score.missing),
        "preview": score.preview,
        "rewrite": score.rewrite,
    }
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if score.category != "needs_work" else 2

    print(f"Score: {score.score}/10 ({score.category})")
    print(f"Reason: {score.reason}")
    if score.missing:
        print(f"Missing: {', '.join(score.missing)}")
    print(f"Preview: {score.preview}")
    print(f"Try: {score.rewrite}")
    return 0 if score.category != "needs_work" else 2


def _repo_root() -> str:
    return str(Path(__file__).resolve().parents[2])


if __name__ == "__main__":
    raise SystemExit(main())
