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
    previous_facts: dict[str, Any] | None = None,
) -> str:
    generated_at = generated_at or datetime.now(UTC)
    expert = expert or mode == "expert"
    totals = facts.get("totals", {})
    prompt_quality = facts.get("prompt_quality", {})
    suggestions = build_suggestions(facts)
    verification_rate = _verification_rate(facts)
    lines: list[str] = [
        "# Codex Coach Report",
        "",
        "| Generated | Window | Mode |",
        "|---|---|---|",
        f"| `{generated_at.isoformat(timespec='seconds')}` | `{facts.get('since') or 'all available local logs'}` | `{'expert' if expert else 'beginner'}` |",
    ]
    lines.extend(_comparison_lines(facts, previous_facts))
    lines.extend([
        "## At A Glance",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Sessions | {_fmt_int(int(totals.get('sessions', 0) or 0))} |",
        f"| Turns | {_fmt_int(int(totals.get('turns', 0) or 0))} |",
        f"| User messages | {_fmt_int(int(totals.get('user_messages', 0) or 0))} |",
        f"| Tool calls | {_fmt_int(int(totals.get('tool_calls', 0) or 0))} |",
        f"| Verification rate | {verification_rate:.1%} |",
        f"| Errors detected | {_fmt_int(int(totals.get('errors', 0) or 0))} |",
        f"| Compactions | {_fmt_int(int(totals.get('compactions', 0) or 0))} |",
        f"| Prompt clarity | {prompt_quality.get('average_score', 0)}/10 |",
        "",
    ])
    lines.extend(_tldr_lines(suggestions, expert=expert))
    lines.extend(_token_efficiency_lines(facts, expert=expert))
    lines.extend(["", "## Project Mix", ""])
    lines.append("Where Codex spent the most work.")
    lines.append("")
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
        lines.append("| Project | Pattern | Suggested AGENTS.md cue |")
        lines.append("|---|---|---|")
        for capsule in capsules:
            lines.append(
                f"| `{capsule.get('project')}` | {capsule.get('likely_workflow')} | "
                f"{capsule.get('recommended_instruction')} |"
            )
    else:
        lines.append("No project capsules available.")

    lines.extend(_instruction_playbook_lines(facts.get("instruction_audit", {}), expert=expert))

    lines.extend(["", "## Prompt Quality", ""])
    lines.append("Short prompts are fine when context is obvious. If Codex guesses, add target, symptom, and success state.")
    lines.append("")
    categories = prompt_quality.get("categories", {})
    if categories:
        lines.append("| Category | Count |")
        lines.append("|---|---:|")
        for name in ("excellent", "good", "needs_work"):
            lines.append(f"| {name.replace('_', ' ').title()} | {categories.get(name, 0)} |")
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

    if expert:
        lines.extend(["", "## Suggested Improvements", ""])
        lines.append("Full detail for review. Nothing is applied automatically.")
        lines.append("")
        for suggestion in suggestions:
            lines.extend(_suggestion_lines(suggestion))
    else:
        lines.extend(["", "## Suggestion Files", ""])
        lines.append("Want the pasteable patches? Run `codex-coach suggest-config --since 7d` and review `~/.codex-coach/suggestions/`.")

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


def _comparison_lines(facts: dict[str, Any], previous_facts: dict[str, Any] | None) -> list[str]:
    lines = ["", "## Since Last Report", ""]
    if not isinstance(previous_facts, dict) or not previous_facts:
        lines.append("No previous report detected yet. This report becomes the baseline for the next comparison.")
        lines.append("")
        return lines

    previous_since = previous_facts.get("since") or "all available local logs"
    previous_generated = previous_facts.get("generated_at") or "unknown time"
    lines.append(
        "Plain English: this compares the current report with the last report Codex Coach generated, "
        "so you can see whether habits improved, stayed steady, or need attention."
    )
    lines.append("")
    lines.append(f"Previous baseline: generated `{previous_generated}` for window `{previous_since}`.")
    lines.append("")
    lines.append("| Habit | Previous | Current | Change | Trend |")
    lines.append("|---|---:|---:|---:|---|")

    rows = [
        _comparison_row(
            "Prompt clarity",
            _prompt_average(previous_facts),
            _prompt_average(facts),
            formatter=lambda value: f"{value:.1f}/10",
            delta_formatter=lambda value: _fmt_signed(value, suffix=""),
            higher_is_better=True,
            scale=2.0,
        ),
        _comparison_row(
            "Verification rate",
            _verification_rate(previous_facts),
            _verification_rate(facts),
            formatter=lambda value: f"{value:.1%}",
            delta_formatter=lambda value: _fmt_signed(value * 100, suffix=" pts"),
            higher_is_better=True,
            scale=0.25,
        ),
        _comparison_row(
            "Errors detected",
            _total_value(previous_facts, "errors"),
            _total_value(facts, "errors"),
            formatter=lambda value: _fmt_int(int(value)),
            delta_formatter=lambda value: _fmt_signed(value),
            higher_is_better=False,
            scale=max(1.0, _total_value(previous_facts, "errors"), _total_value(facts, "errors")),
        ),
        _comparison_row(
            "Compactions",
            _total_value(previous_facts, "compactions"),
            _total_value(facts, "compactions"),
            formatter=lambda value: _fmt_int(int(value)),
            delta_formatter=lambda value: _fmt_signed(value),
            higher_is_better=False,
            scale=max(1.0, _total_value(previous_facts, "compactions"), _total_value(facts, "compactions")),
        ),
    ]

    if _has_token_usage(previous_facts) or _has_token_usage(facts):
        previous_uncached = _uncached_per_turn(previous_facts)
        current_uncached = _uncached_per_turn(facts)
        rows.append(
            _comparison_row(
                "Uncached input / turn",
                previous_uncached,
                current_uncached,
                formatter=lambda value: _fmt_float(value),
                delta_formatter=lambda value: _fmt_signed(value),
                higher_is_better=False,
                scale=max(1.0, previous_uncached, current_uncached),
            )
        )

    lines.extend(rows)
    lines.append("")
    lines.append("Trend key: `+` means improving, `-` means drifting, `=` means basically unchanged.")
    lines.append("")
    return lines


def _comparison_row(
    label: str,
    previous: float,
    current: float,
    *,
    formatter,
    delta_formatter,
    higher_is_better: bool,
    scale: float,
) -> str:
    delta = current - previous
    score_delta = delta if higher_is_better else -delta
    if abs(score_delta) < 0.0001:
        trend = "steady"
    else:
        trend = "better" if score_delta > 0 else "watch"
    return (
        f"| {label} | {formatter(previous)} | {formatter(current)} | "
        f"{delta_formatter(delta)} | `{_trend_bar(score_delta, scale=scale)}` {trend} |"
    )


def _trend_bar(score_delta: float, *, scale: float) -> str:
    if abs(score_delta) < 0.0001:
        return "[==========]"
    width = 10
    filled = max(1, min(width, int(round(abs(score_delta) / max(scale, 0.0001) * width))))
    char = "+" if score_delta > 0 else "-"
    return f"[{char * filled}{'.' * (width - filled)}]"


def _total_value(facts: dict[str, Any], key: str) -> float:
    totals = facts.get("totals", {}) if isinstance(facts, dict) else {}
    return _as_float(totals.get(key, 0) if isinstance(totals, dict) else 0)


def _prompt_average(facts: dict[str, Any]) -> float:
    prompt_quality = facts.get("prompt_quality", {}) if isinstance(facts, dict) else {}
    return _as_float(prompt_quality.get("average_score", 0) if isinstance(prompt_quality, dict) else 0)


def _verification_rate(facts: dict[str, Any]) -> float:
    tool_calls = max(1.0, _total_value(facts, "tool_calls"))
    return _total_value(facts, "verification_tool_calls") / tool_calls


def _has_token_usage(facts: dict[str, Any]) -> bool:
    token_efficiency = facts.get("token_efficiency", {}) if isinstance(facts, dict) else {}
    return isinstance(token_efficiency, dict) and token_efficiency.get("status") == "observed"


def _uncached_per_turn(facts: dict[str, Any]) -> float:
    token_efficiency = facts.get("token_efficiency", {}) if isinstance(facts, dict) else {}
    usage = token_efficiency.get("usage", {}) if isinstance(token_efficiency, dict) else {}
    return _as_float(usage.get("uncached_input_tokens_per_turn", 0) if isinstance(usage, dict) else 0)


def _as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _fmt_signed(value: float, *, suffix: str = "") -> str:
    if abs(value) < 0.0001:
        return f"0{suffix}"
    sign = "+" if value > 0 else ""
    if float(value).is_integer():
        return f"{sign}{int(value):,}{suffix}"
    return f"{sign}{value:,.1f}{suffix}"


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
                "body": "High reasoning dominates recent turns. To actually reduce effort, choose medium in the Codex UI or CLI for routine work. A custom instruction can only remind Codex of the preference; it cannot override a manually selected model or effort setting.",
                "paste_target": "Codex UI/CLI effort setting plus optional Global custom instructions",
                "suggested_text": "For model effort, prefer medium for routine status checks, targeted searches, formatting, small edits, and deterministic reports. Use high or xhigh only for ambiguous debugging, architecture decisions, security review, broad refactors, or production-risk changes. If the Codex client has already fixed the model or effort setting, follow that setting and mention when the task appears over- or under-scoped for it.",
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
                "paste_target": "Project AGENTS.md",
                "suggested_text": "Before final status, run the smallest meaningful verification for the change: a focused test, build, lint/typecheck, browser check, or runtime probe. If verification cannot run, say exactly why and what risk remains.",
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
                "paste_target": "Global custom instructions or project AGENTS.md",
                "suggested_text": "For long tasks, keep a short task ledger with completed, in-progress, and pending steps. After compaction or interruption, verify the current file state and last successful command before continuing.",
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
                "paste_target": "Global custom instructions",
                "suggested_text": "When my prompt is vague, infer the likely task from the current repo and recent context. If the target or success state is still unclear, ask one concise question before making broad changes.",
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
                "paste_target": "Each active project's AGENTS.md",
                "suggested_text": "## Project Capsule\n- Purpose: <what this repo is for>\n- Stack: <main frameworks, runtime, package manager>\n- Entry points: <key files or commands>\n- Verify: <smallest reliable test/build/check>\n- Avoid: <repo-specific traps or risky commands>",
            }
        )

    if build_skill_opportunities(facts):
        suggestions.append(
            {
                "id": "make-repeated-workflows-skills",
                "title": "Turn repeated workflows into skills",
                "confidence": "medium",
                "body": "At least one project shows repeated tool patterns. Consider a small user skill with the workflow steps, validation commands, and resume rules.",
                "paste_target": "A Codex skill `SKILL.md` or project AGENTS.md",
                "suggested_text": "Use this workflow when <trigger>. First read <specific files>. Then perform <steps>. Verify with <commands>. If interrupted, resume by checking <durable artifact or command output>.",
            }
        )

    suggestions.extend(build_token_suggestions(facts))

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
                "paste_target": "Instruction review checklist",
                "suggested_text": "Keep global instructions limited to durable personal preferences. Move repo-specific stack, commands, UI style, and deployment rules into that repo's AGENTS.md. Never store tokens, passwords, or API keys in instruction files.",
            }
        )

    if not suggestions:
        suggestions.append(
            {
                "id": "keep-current-loop",
                "title": "Keep the current loop",
                "confidence": "medium",
                "body": "No strong coaching warnings stood out. Keep using explicit success states and ask for verification on user-facing or production-sensitive work.",
                "paste_target": "Global custom instructions",
                "suggested_text": "For user-facing or production-sensitive changes, finish with a short verification note that names the command or check that passed and any remaining risk.",
            }
        )
    return suggestions


def build_token_suggestions(facts: dict[str, Any]) -> list[dict[str, str]]:
    token_efficiency = facts.get("token_efficiency", {})
    if not isinstance(token_efficiency, dict) or token_efficiency.get("status") != "observed":
        return []

    usage = token_efficiency.get("usage", {})
    if not isinstance(usage, dict):
        return []

    suggestions: list[dict[str, str]] = []
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    uncached_tokens = int(usage.get("uncached_input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    cache_ratio = float(usage.get("cache_ratio", 0.0) or 0.0)
    uncached_per_turn = float(usage.get("uncached_input_tokens_per_turn", 0.0) or 0.0)
    turns = max(1, int((facts.get("totals") or {}).get("turns", 0) or 0))
    efforts = facts.get("efforts", {})
    high_effort = sum(int(efforts.get(name, 0) or 0) for name in ("high", "xhigh"))

    if input_tokens >= 100_000 and cache_ratio >= 0.75:
        suggestions.append(
            {
                "id": "use-compact-context-artifacts",
                "title": "Use compact context artifacts",
                "confidence": _confidence(cache_ratio, high=0.85, medium=0.75),
                "body": "Most input is repeated cached context. Keep short project capsules, latest facts, and resume notes so routine coaching can start from compact artifacts instead of full history.",
                "paste_target": "Global custom instructions",
                "suggested_text": "Before re-reading a large repo or long history, first check existing summaries, reports, AGENTS.md, and recent task notes. Use those compact artifacts to choose the smallest next context to inspect.",
            }
        )

    if uncached_tokens >= 50_000 or uncached_per_turn >= 12_000:
        suggestions.append(
            {
                "id": "cap-uncached-context",
                "title": "Cap uncached context",
                "confidence": "high" if uncached_per_turn >= 20_000 else "medium",
                "body": "Uncached input is the expensive part. Ask Codex to read one likely file first, summarize before widening, and prefer targeted searches over broad file dumps.",
                "paste_target": "Global custom instructions",
                "suggested_text": "Before broad exploration, identify the likely bottleneck and inspect the one most relevant file or targeted search result first. Widen only after explaining what is still unknown.",
            }
        )

    if high_effort and high_effort / turns >= 0.25:
        suggestions.append(
            {
                "id": "route-routine-work-to-mini",
                "title": "Route routine work to mini or medium",
                "confidence": "high" if high_effort / turns >= 0.5 else "medium",
                "body": "High effort appears often enough to merit routing. To actually save tokens or credits, start routine scan, report, grep, formatting, and deterministic edit tasks with mini or medium in the Codex UI or CLI. A custom instruction is only a reminder; it does not override the selected setting.",
                "paste_target": "Codex UI/CLI effort setting plus optional Global custom instructions",
                "suggested_text": "Prefer cheaper routine routing: start scans, reports, greps, formatting, and deterministic small edits with mini or medium reasoning when the Codex client allows it. Escalate only when the task needs judgment, tradeoff analysis, or high-risk debugging. This is a preference, not an automatic override of the UI or CLI model/effort setting.",
            }
        )

    if output_tokens >= 20_000 and input_tokens and output_tokens / input_tokens >= 0.08:
        suggestions.append(
            {
                "id": "request-concise-outputs",
                "title": "Request concise outputs",
                "confidence": "medium",
                "body": "Output tokens are a visible part of spend. Ask for summaries first and detailed evidence only when deciding or reviewing.",
                "paste_target": "Global custom instructions",
                "suggested_text": "Default to concise final answers: say what changed, how it was verified, and any risk. Include detailed logs or long evidence only when asked or when needed for a decision.",
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


def _tldr_lines(suggestions: list[dict[str, str]], *, expert: bool) -> list[str]:
    lines = [
        "## TL;DR",
        "",
        "Start here. These are optional, not errors.",
        "",
    ]
    if not suggestions:
        lines.append("No strong changes stood out.")
        return lines

    for index, suggestion in enumerate(suggestions[: 5 if expert else 3], start=1):
        paste_target = suggestion.get("paste_target", "custom instructions or project AGENTS.md")
        suggested_text = suggestion.get("suggested_text")
        location = _placement_help(paste_target)
        lines.extend(
            [
                f"### {index}. {suggestion['title']}",
                "",
                f"- Why: {suggestion['body']}",
                f"- Where: {location['where']}",
                f"- Scope: {location['scope']}",
                f"- Do: {location['action']}",
            ]
        )
        if suggested_text:
            lines.extend(_collapsible_paste_block(str(suggested_text)))
        else:
            lines.append("- What to paste: review the detailed suggestion below before writing a new instruction.")
        lines.append("")
    return lines


def _suggestion_lines(suggestion: dict[str, Any]) -> list[str]:
    paste_target = suggestion.get("paste_target")
    location = _placement_help(str(paste_target or "custom instructions or project AGENTS.md"))
    lines = [
        f"### {suggestion['title']}",
        "",
        f"- Confidence: {suggestion['confidence']}",
        f"- Why: {suggestion['body']}",
        f"- Where: {location['where']}",
        f"- Scope: {location['scope']}",
    ]
    suggested_text = suggestion.get("suggested_text")
    if paste_target and suggested_text:
        lines.extend(
            [
                f"- How to apply it: {location['action']}",
                "",
                *_collapsible_paste_block(str(suggested_text)),
            ]
        )
    lines.append("")
    return lines


def _token_efficiency_lines(facts: dict[str, Any], *, expert: bool) -> list[str]:
    lines = ["", "## Token Efficiency", ""]
    token_efficiency = facts.get("token_efficiency", {})
    if not isinstance(token_efficiency, dict) or token_efficiency.get("status") != "observed":
        lines.append("No token usage events were found in this window.")
        return lines

    usage = token_efficiency.get("usage", {})
    if not isinstance(usage, dict):
        lines.append("No token usage events were found in this window.")
        return lines

    input_tokens = int(usage.get("input_tokens", 0) or 0)
    cached_tokens = int(usage.get("cached_input_tokens", 0) or 0)
    uncached_tokens = int(usage.get("uncached_input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    reasoning_tokens = int(usage.get("reasoning_output_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", 0) or 0)
    cache_ratio = float(usage.get("cache_ratio", 0.0) or 0.0)
    uncached_ratio = float(usage.get("uncached_ratio", 0.0) or 0.0)

    lines.append("Cached input is repeated context. Uncached input is new context and usually the bigger savings target.")
    lines.append("")
    lines.append(
        f"- Input: {_fmt_int(input_tokens)} "
        f"({_fmt_int(cached_tokens)} cached, {_fmt_int(uncached_tokens)} uncached)"
    )
    lines.append(f"- Output: {_fmt_int(output_tokens)} ({_fmt_int(reasoning_tokens)} reasoning)")
    lines.append(f"- Total: {_fmt_int(total_tokens)} across {_fmt_int(int(usage.get('events', 0) or 0))} token events")
    lines.append(f"- Cache ratio: {cache_ratio:.1%}; uncached ratio: {uncached_ratio:.1%}")
    lines.append(
        f"- Per turn: {_fmt_float(usage.get('input_tokens_per_turn'))} input, "
        f"{_fmt_float(usage.get('uncached_input_tokens_per_turn'))} uncached"
    )

    max_last_input = int(token_efficiency.get("max_last_input_tokens", 0) or 0)
    max_last_uncached = int(token_efficiency.get("max_last_uncached_input_tokens", 0) or 0)
    context_window = int(token_efficiency.get("max_model_context_window", 0) or 0)
    if max_last_input:
        context_note = f" of {_fmt_int(context_window)}" if context_window else ""
        lines.append(
            f"- Largest step: {_fmt_int(max_last_input)} input tokens{context_note}; "
            f"{_fmt_int(max_last_uncached)} uncached"
        )

    token_suggestions = build_token_suggestions(facts)
    if token_suggestions:
        lines.extend(
            [
                "",
                "Token-saving moves:",
                "",
                "Optional. UI/CLI settings control actual model and effort; instructions only guide behavior.",
                "",
                "| Move | Confidence | First action |",
                "|---|---|---|",
            ]
        )
        for item in token_suggestions[: 5 if expert else 3]:
            paste_target = item.get("paste_target", "instructions")
            location = _placement_help(str(paste_target))
            lines.append(f"| {item['title']} | {item['confidence']} | {location['action']} |")
    else:
        lines.extend(
            [
                "",
                "Token-saving moves:",
                "- No strong token-efficiency warning stood out. Keep routing routine work to cheaper models and reserve high effort for judgment-heavy turns.",
            ]
        )

    if expert:
        capsules = [item for item in facts.get("project_capsules", []) if isinstance(item, dict)]
        token_capsules = [item for item in capsules if (item.get("token_usage") or {}).get("input_tokens")]
        if token_capsules:
            token_capsules.sort(key=lambda item: int((item.get("token_usage") or {}).get("input_tokens", 0)), reverse=True)
            lines.extend(["", "Top token projects:"])
            for item in token_capsules[:5]:
                token_usage = item.get("token_usage") or {}
                lines.append(
                    f"- `{item.get('project')}`: {_fmt_int(int(token_usage.get('input_tokens', 0) or 0))} input, "
                    f"{_fmt_int(int(token_usage.get('uncached_input_tokens', 0) or 0))} uncached, "
                    f"{token_usage.get('cache_ratio', 0):.1%} cached"
                )

    return lines


def _placement_help(paste_target: str) -> dict[str, str]:
    target = paste_target.lower()
    if "ui/cli effort setting" in target:
        return {
            "where": "Codex UI model/effort picker or CLI model/effort flag. Optional reminder text can go in Global custom instructions.",
            "scope": "Actual setting change, not just a prompt. Custom instructions cannot override a manually selected UI/CLI effort.",
            "action": "For routine work, start the session with mini or medium in the UI/CLI. Paste the reminder only if you want Codex to call out over- or under-scoped effort.",
        }
    if "instruction review checklist" in target:
        return {
            "where": "Open the Instruction Playbook section of this report first.",
            "scope": "This is a review step, not something to paste into a chat prompt.",
            "action": "Read the finding, then decide whether the matching custom instruction or AGENTS.md file should change.",
        }
    if "skill" in target:
        return {
            "where": "Advanced: create or update a Codex skill, or put the simpler version in the project AGENTS.md file.",
            "scope": "Use a skill for a repeated workflow across projects. Use AGENTS.md for one project.",
            "action": "Start with AGENTS.md unless you already know you want a reusable skill.",
        }
    if "each active project" in target:
        return {
            "where": "In each active project folder, open or create a file named AGENTS.md.",
            "scope": "Project file. This affects only that project, not every Codex chat.",
            "action": "Paste the block into AGENTS.md for projects where this advice actually applies.",
        }
    if "global custom instructions" in target and "project" in target:
        return {
            "where": "Codex settings -> Custom instructions, or the project AGENTS.md file.",
            "scope": "Use settings if you want this everywhere. Use AGENTS.md if it should apply only to one repo.",
            "action": "If unsure, put it in AGENTS.md first so the habit stays scoped to one project.",
        }
    if "project agents" in target or "agents.md" in target:
        return {
            "where": "In the project folder, open or create a file named AGENTS.md.",
            "scope": "Project file. This is better than a prompt when the rule should stay with the repo.",
            "action": "Paste the block into AGENTS.md, then ask Codex to use that project normally.",
        }
    if "global custom instructions" in target or "custom instructions" in target:
        return {
            "where": "Codex settings -> Custom instructions.",
            "scope": "Settings, not the chat prompt. Use this for habits you want Codex to follow everywhere.",
            "action": "Open Codex settings, edit Custom instructions, paste the block below, then remove it later if it does not help.",
        }
    return {
        "where": paste_target or "Custom instructions or AGENTS.md.",
        "scope": "Use settings for global habits, a prompt for one-off tasks, and AGENTS.md for one project.",
        "action": "Paste the block only if the recommendation matches how you want Codex to behave.",
    }


def _collapsible_paste_block(text: str) -> list[str]:
    return [
        "- What to paste:",
        "",
        "<details>",
        "<summary>Show snippet</summary>",
        "",
        "```md",
        text,
        "```",
        "",
        "</details>",
    ]


def _instruction_playbook_lines(instruction_audit: dict[str, Any], *, expert: bool) -> list[str]:
    lines = ["", "## Instruction Playbook", ""]
    if not isinstance(instruction_audit, dict) or not instruction_audit:
        lines.append("No instruction audit was generated.")
        return lines

    lines.append("Plain English: this checks whether your global custom instructions and project `AGENTS.md` files are helping Codex, getting stale, or leaking project-specific rules into every repo.")
    lines.append("")
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
        lines.extend(["", "Suggested playbook changes with pasteable examples:"])
        for item in suggestions[: 8 if expert else 4]:
            lines.append(f"- [{item.get('confidence', 'medium')}] {item.get('title')}: {item.get('body')}")
            lines.append(f"  Paste into: `{item.get('target', 'instruction file')}`")
            suggested_text = str(item.get("suggested_text") or "").strip()
            if suggested_text:
                lines.extend(["", "```md", suggested_text, "```", ""])

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
    paste_target = suggestion.get("paste_target", "custom instructions or project AGENTS.md")
    suggested_text = suggestion.get("suggested_text") or f"- {suggestion['body']}"
    location = _placement_help(paste_target)
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
            f"Target: {paste_target}",
            "",
            f"Where: {location['where']}",
            "",
            f"Scope: {location['scope']}",
            "",
            f"How: {location['action']}",
            "",
            "```md",
            suggested_text,
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
            f"Paste into: {suggestion.get('target', 'instruction file')}",
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


def _fmt_int(value: int) -> str:
    return f"{int(value):,}"


def _fmt_float(value: Any) -> str:
    try:
        return f"{float(value):,.1f}"
    except (TypeError, ValueError):
        return "0.0"
