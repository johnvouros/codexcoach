from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def write_json_facts(facts: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_markdown_report(
    facts: dict[str, Any],
    *,
    generated_at: datetime | None = None,
    expert: bool = False,
    mode: str = "beginner",
) -> str:
    generated_at = generated_at or datetime.now(UTC)
    expert = expert or mode == "expert"
    totals = facts.get("totals", {})
    prompt_quality = facts.get("prompt_quality", {})
    suggestions = build_suggestions(facts)
    lines: list[str] = [
        "# Codex Coach Report",
        "",
        f"Generated: {generated_at.isoformat(timespec='seconds')}",
        f"Window: {facts.get('since') or 'all available local logs'}",
        f"Mode: {'expert' if expert else 'beginner'}",
        "",
        "## Summary",
        "",
        f"- Sessions: {totals.get('sessions', 0)}",
        f"- Turns: {totals.get('turns', 0)}",
        f"- User messages: {totals.get('user_messages', 0)}",
        f"- Tool calls: {totals.get('tool_calls', 0)}",
        f"- Verification tool calls: {totals.get('verification_tool_calls', 0)}",
        f"- Errors detected: {totals.get('errors', 0)}",
        f"- Compactions: {totals.get('compactions', 0)}",
        f"- Prompt quality average: {prompt_quality.get('average_score', 0)}/10",
        "",
        "## Top Coaching Notes",
        "",
    ]
    lines.extend(_coaching_notes(suggestions, limit=5 if expert else 3))
    lines.extend(["", "## Project Mix", ""])
    projects = facts.get("projects", [])[:8]
    if projects:
        lines.append("| Project | Sessions | Turns | User Messages | Tool Calls | Verification |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for project in projects:
            lines.append(
                f"| `{project.get('cwd')}` | {project.get('sessions', 0)} | {project.get('turns', 0)} | "
                f"{project.get('user_messages', 0)} | {project.get('tool_calls', 0)} | "
                f"{project.get('verification_tool_calls', 0)} |"
            )
    else:
        lines.append("No project activity found.")

    lines.extend(["", "## Project Capsules", ""])
    capsules = facts.get("project_capsules", [])[:5]
    if capsules:
        for capsule in capsules:
            lines.append(f"- `{capsule.get('project')}`: {capsule.get('likely_workflow')}. {capsule.get('recommended_instruction')}")
    else:
        lines.append("No project capsules available.")

    lines.extend(_instruction_playbook_lines(facts.get("instruction_audit", {}), expert=expert))

    lines.extend(["", "## Prompt Quality", ""])
    categories = prompt_quality.get("categories", {})
    if categories:
        for name in ("excellent", "good", "needs_work"):
            lines.append(f"- {name.replace('_', ' ').title()}: {categories.get(name, 0)}")
    else:
        lines.append("- No user prompts found.")

    needs_work = prompt_quality.get("examples_needing_work", [])
    if needs_work:
        lines.extend(["", "Prompt rewrites to try, shown with redacted previews:"])
        for item in needs_work[:5]:
            missing = ", ".join(item.get("missing", [])) or "none"
            lines.append(
                f"- Score {item.get('score')}/10, missing {missing}: `{item.get('preview')}` -> "
                f"{item.get('rewrite')}"
            )

    lines.extend(["", "## Suggested Improvements", ""])
    for suggestion in suggestions:
        lines.append(f"- [{suggestion['confidence']}] {suggestion['title']}: {suggestion['body']}")

    skill_opportunities = build_skill_opportunities(facts)
    if skill_opportunities:
        lines.extend(["", "## Skill Opportunities", ""])
        for item in skill_opportunities[:5]:
            lines.append(f"- `{item['project']}`: {item['title']} - {item['body']}")

    if expert:
        lines.extend(["", "## Expert Metrics", ""])
        lines.append(f"- Models: `{facts.get('models', {})}`")
        lines.append(f"- Efforts: `{facts.get('efforts', {})}`")
        lines.append(f"- Tools: `{facts.get('tools', {})}`")
        lines.append(f"- Verification tools: `{facts.get('verification_tools', {})}`")
        lines.append(f"- Errors: `{facts.get('errors', {})}`")

    lines.extend(
        [
            "",
            "## Privacy",
            "",
            "This report is generated from local Codex logs. Full prompt bodies and source code are not included by default.",
            "",
        ]
    )
    return "\n".join(lines)


def write_markdown_report(report: str, reports_dir: Path, *, generated_at: datetime | None = None) -> tuple[Path, Path]:
    generated_at = generated_at or datetime.now(UTC)
    reports_dir.mkdir(parents=True, exist_ok=True)
    latest = reports_dir / "latest.md"
    weekly = reports_dir / f"weekly-{generated_at.date().isoformat()}.md"
    latest.write_text(report, encoding="utf-8")
    weekly.write_text(report, encoding="utf-8")
    return latest, weekly


def build_suggestions(facts: dict[str, Any]) -> list[dict[str, str]]:
    totals = facts.get("totals", {})
    suggestions: list[dict[str, str]] = []
    efforts = facts.get("efforts", {})
    turns = max(1, int(totals.get("turns", 0)))
    high_effort = sum(int(efforts.get(name, 0)) for name in ("high", "xhigh"))
    if high_effort / turns >= 0.6 and turns >= 5:
        ratio = high_effort / turns
        suggestions.append(
            {
                "id": "right-size-reasoning",
                "title": "Right-size reasoning effort",
                "confidence": _confidence(ratio, high=0.75, medium=0.6),
                "body": "High reasoning dominates recent turns. Default simple status, search, and small edit tasks to medium; reserve high/xhigh for ambiguous debugging, architecture, security, or broad refactors.",
            }
        )

    verification = int(totals.get("verification_tool_calls", 0))
    tool_calls = max(1, int(totals.get("tool_calls", 0)))
    if tool_calls >= 10 and verification / tool_calls < 0.12:
        ratio = verification / tool_calls
        suggestions.append(
            {
                "id": "verify-before-done",
                "title": "Verify before calling work done",
                "confidence": "high" if ratio < 0.08 and tool_calls >= 20 else "medium",
                "body": "Verification commands are a small share of tool use. Ask Codex to run the smallest meaningful test, build, lint, browser check, or runtime probe before final status.",
            }
        )

    if int(totals.get("compactions", 0)) > 0:
        compactions = int(totals.get("compactions", 0))
        suggestions.append(
            {
                "id": "checkpoint-long-runs",
                "title": "Checkpoint long runs",
                "confidence": "high" if compactions >= 3 else "medium",
                "body": "Compactions appeared in the window. For long tasks, ask Codex to keep a small task ledger and validate durable files before resuming.",
            }
        )

    prompt_quality = facts.get("prompt_quality", {})
    categories = prompt_quality.get("categories", {})
    needs_work = int(categories.get("needs_work", 0))
    user_messages = max(1, int(totals.get("user_messages", 0)))
    if needs_work / user_messages >= 0.08:
        ratio = needs_work / user_messages
        suggestions.append(
            {
                "id": "tighten-ambiguous-prompts",
                "title": "Tighten ambiguous prompts",
                "confidence": _confidence(ratio, high=0.15, medium=0.08),
                "body": "A noticeable share of prompts are too short to identify the target. Include action, file/project, symptom, and success state when context is not obvious.",
            }
        )

    projects = facts.get("projects", [])
    if len(projects) >= 4:
        suggestions.append(
            {
                "id": "project-capsules",
                "title": "Use project capsules",
                "confidence": "high" if len(projects) >= 6 else "medium",
                "body": "Recent work spans several projects. Keep a short per-project AGENTS or context note so Codex does not rebuild project intent every time.",
            }
        )

    if build_skill_opportunities(facts):
        suggestions.append(
            {
                "id": "make-repeated-workflows-skills",
                "title": "Turn repeated workflows into skills",
                "confidence": "medium",
                "body": "At least one project shows repeated tool patterns. Consider a small user skill with the workflow steps, validation commands, and resume rules.",
            }
        )

    instruction_audit = facts.get("instruction_audit", {})
    instruction_findings = instruction_audit.get("findings", []) if isinstance(instruction_audit, dict) else []
    if instruction_findings:
        high = any(item.get("severity") == "high" for item in instruction_findings if isinstance(item, dict))
        suggestions.append(
            {
                "id": "review-instruction-playbook",
                "title": "Review instruction playbook",
                "confidence": "high" if high else "medium",
                "body": "Instruction files have review findings. Check for stale mode locks, project-specific global rules, missing AGENTS.md coverage, or secrets before changing user instructions.",
            }
        )

    if not suggestions:
        suggestions.append(
            {
                "id": "keep-current-loop",
                "title": "Keep the current loop",
                "confidence": "medium",
                "body": "No strong coaching warnings stood out. Keep using explicit success states and ask for verification on user-facing or production-sensitive work.",
            }
        )
    return suggestions


def build_skill_opportunities(facts: dict[str, Any]) -> list[dict[str, str]]:
    opportunities: list[dict[str, str]] = []
    for capsule in facts.get("project_capsules", []):
        if not capsule.get("skill_candidate"):
            continue
        project = str(capsule.get("project", "<unknown>"))
        workflow = str(capsule.get("likely_workflow", "mixed workflow"))
        opportunities.append(
            {
                "project": project,
                "title": "Create a project workflow skill",
                "body": (
                    f"Capture the {workflow} loop as a reusable skill: when to trigger, what context to gather, "
                    "which commands verify the work, and how to resume after interruption."
                ),
            }
        )
    return opportunities


def write_suggestion_files(facts: dict[str, Any], suggestions_dir: Path) -> list[Path]:
    suggestions_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for suggestion in build_suggestions(facts):
        path = suggestions_dir / f"{suggestion['id']}.patch.md"
        text = _render_suggestion_patch(suggestion)
        path.write_text(text, encoding="utf-8")
        written.append(path)
    written.extend(write_instruction_suggestion_files(facts.get("instruction_audit", {}), suggestions_dir))
    return written


def write_instruction_suggestion_files(instruction_audit: dict[str, Any], suggestions_dir: Path) -> list[Path]:
    suggestions_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if not isinstance(instruction_audit, dict):
        return written
    for suggestion in instruction_audit.get("suggestions", []):
        if not isinstance(suggestion, dict):
            continue
        suggestion_id = str(suggestion.get("id") or "instruction-suggestion")
        path = suggestions_dir / f"instruction-{suggestion_id}.patch.md"
        path.write_text(_render_instruction_suggestion_patch(suggestion), encoding="utf-8")
        written.append(path)
    return written


def render_instruction_report(instruction_audit: dict[str, Any], *, generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(UTC)
    lines = [
        "# Codex Coach Instruction Playbook Report",
        "",
        f"Generated: {generated_at.isoformat(timespec='seconds')}",
        f"Window: {instruction_audit.get('since') or 'all available local logs'}",
    ]
    lines.extend(_instruction_playbook_lines(instruction_audit, expert=True))
    lines.extend(
        [
            "",
            "## Privacy",
            "",
            "Instruction files are analyzed locally. Reports use file hashes, project labels, and review categories instead of raw instruction text.",
            "",
        ]
    )
    return "\n".join(lines)


def _coaching_notes(suggestions: list[dict[str, str]], *, limit: int) -> list[str]:
    return [f"- [{item['confidence']}] {item['title']}: {item['body']}" for item in suggestions[:limit]]


def _instruction_playbook_lines(instruction_audit: dict[str, Any], *, expert: bool) -> list[str]:
    lines = ["", "## Instruction Playbook", ""]
    if not isinstance(instruction_audit, dict) or not instruction_audit:
        lines.append("No instruction audit was generated.")
        return lines

    lines.append(f"- Status: {instruction_audit.get('status', 'unknown')}")
    lines.append(f"- Files reviewed: {instruction_audit.get('files_reviewed', 0)}")
    lines.append(f"- Findings: {len(instruction_audit.get('findings', []))}")
    lines.append(f"- Reviewable suggestions: {len(instruction_audit.get('suggestions', []))}")

    findings = [item for item in instruction_audit.get("findings", []) if isinstance(item, dict)]
    if findings:
        lines.extend(["", "Top playbook findings:"])
        for item in findings[: 8 if expert else 4]:
            lines.append(
                f"- [{item.get('severity', 'info')}] {item.get('title')}: "
                f"{item.get('body')} Target: `{item.get('target', 'unknown')}`"
            )
    else:
        lines.extend(["", "No instruction playbook issues stood out."])

    suggestions = [item for item in instruction_audit.get("suggestions", []) if isinstance(item, dict)]
    if suggestions:
        lines.extend(["", "Suggested playbook changes:"])
        for item in suggestions[: 8 if expert else 4]:
            lines.append(f"- [{item.get('confidence', 'medium')}] {item.get('title')}: {item.get('body')}")

    if expert:
        files = [item for item in instruction_audit.get("files", []) if isinstance(item, dict)]
        if files:
            lines.extend(["", "Reviewed files:"])
            for item in files[:10]:
                projects = ", ".join(item.get("project_labels", [])) or "global"
                lines.append(
                    f"- `{item.get('file')}` scope={item.get('scope')} hash={item.get('file_hash')} "
                    f"lines={item.get('lines', 0)} projects={projects}"
                )
    return lines


def _render_suggestion_patch(suggestion: dict[str, str]) -> str:
    return "\n".join(
        [
            f"# Suggested Codex Instruction Change: {suggestion['title']}",
            "",
            "Review this suggestion before applying it. Codex Coach never edits your instructions automatically.",
            "",
            "## Why",
            "",
            f"Confidence: {suggestion['confidence']}",
            "",
            suggestion["body"],
            "",
            "## Suggested Text",
            "",
            "```md",
            f"- {suggestion['body']}",
            "```",
            "",
            "## Rollback",
            "",
            "Remove the added instruction if it does not improve your workflow after a week.",
            "",
        ]
    )


def _render_instruction_suggestion_patch(suggestion: dict[str, Any]) -> str:
    suggested_text = str(suggestion.get("suggested_text") or suggestion.get("body") or "")
    return "\n".join(
        [
            f"# Instruction Playbook Suggestion: {suggestion.get('title', 'Review instruction')}",
            "",
            "Review this suggestion before applying it. Codex Coach never edits custom instructions or AGENTS.md automatically.",
            "",
            "## Target",
            "",
            f"- Scope: {suggestion.get('scope', 'unknown')}",
            f"- Target: {suggestion.get('target', 'unknown')}",
            f"- Confidence: {suggestion.get('confidence', 'medium')}",
            "",
            "## Why",
            "",
            str(suggestion.get("body") or ""),
            "",
            "## Suggested Text",
            "",
            "```md",
            suggested_text,
            "```",
            "",
            "## Rollback",
            "",
            str(suggestion.get("rollback") or "Remove the added instruction if it does not improve the workflow."),
            "",
        ]
    )


def _confidence(value: float, *, high: float, medium: float) -> str:
    if value >= high:
        return "high"
    if value >= medium:
        return "medium"
    return "low"
