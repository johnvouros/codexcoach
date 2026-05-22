from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .parser import iter_log_paths
from .redaction import SECRET_RE, stable_hash
from .timeutil import parse_timestamp

GLOBAL_INSTRUCTION_FILES = (
    "AGENTS.md",
    "config.toml",
    "instructions.md",
    "custom-instructions.md",
    "custom_instructions.md",
)
PROJECT_INSTRUCTION_FILES = ("AGENTS.md",)

VERIFY_MARKERS = (
    "test",
    "pytest",
    "vitest",
    "jest",
    "playwright",
    "lint",
    "typecheck",
    "tsc",
    "build",
    "verify",
)
RESUME_MARKERS = ("checkpoint", "resume", "compaction", "ledger", "checklist", "state file")
PROMPT_MARKERS = ("success state", "target", "goal", "context", "constraints")
GLOBAL_SCOPE_LEAK_MARKERS = (
    "tailwind",
    "supabase",
    "next.js",
    "expo",
    "dark mode",
    "neon",
    "spacex",
    "operator-grade",
    "pytest",
    "project-specific",
)
MODE_LOCK_MARKERS = (
    "research only",
    "analysis only",
    "plan only",
    "do not implement",
    "do not edit",
    "no code changes",
)
STALE_MARKERS = ("temporary", "for now", "legacy", "deprecated", "old workflow", "until we")
ABSOLUTE_RE = re.compile(r"\b(always|never|must|exact|only|do not|don't|avoid|follow this exact)\b", re.IGNORECASE)
NPM_TOKEN_RE = re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b")
KEY_VALUE_SECRET_RE = re.compile(
    r"\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RecentProject:
    path: Path
    label: str
    events: int


@dataclass(frozen=True)
class InstructionCandidate:
    path: Path
    scope: str
    source: str
    project_labels: tuple[str, ...] = ()


def analyze_instructions(
    home: Path,
    codex_home: Path,
    *,
    since_dt: datetime | None = None,
    since_label: str | None = None,
    usage_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze local Codex instruction files without returning raw file content."""

    recent_projects = collect_recent_projects(codex_home, since_dt=since_dt)
    candidates = discover_instruction_files(home, codex_home, recent_projects)
    usage_by_project = {
        str(item.get("project")): item for item in (usage_facts or {}).get("project_capsules", []) if item.get("project")
    }

    files: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []
    covered_projects: set[str] = set()

    for candidate in candidates:
        summary, file_findings, file_suggestions = _analyze_file(candidate, usage_by_project)
        files.append(summary)
        findings.extend(file_findings)
        suggestions.extend(file_suggestions)
        covered_projects.update(candidate.project_labels)

    coverage_findings, coverage_suggestions = _coverage_findings(recent_projects, covered_projects)
    findings.extend(coverage_findings)
    suggestions.extend(coverage_suggestions)

    findings = _dedupe(findings)
    suggestions = _dedupe(suggestions)
    high_findings = sum(1 for item in findings if item.get("severity") == "high")
    status = "healthy"
    if high_findings:
        status = "needs_review"
    elif findings:
        status = "review"

    return {
        "schema_version": 1,
        "since": since_label,
        "status": status,
        "files_reviewed": len(files),
        "recent_projects": [
            {
                "project": project.label,
                "events": project.events,
                "has_playbook": project.label in covered_projects,
            }
            for project in recent_projects[:10]
        ],
        "files": files,
        "findings": findings,
        "suggestions": suggestions,
    }


def collect_recent_projects(codex_home: Path, *, since_dt: datetime | None = None) -> list[RecentProject]:
    cwd_counts: Counter[str] = Counter()
    for path in iter_log_paths(codex_home):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            timestamp = parse_timestamp(event.get("timestamp"))
            if since_dt is not None and timestamp is not None and timestamp < since_dt:
                continue
            if event.get("type") not in {"session_meta", "turn_context"}:
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            cwd = str(payload.get("cwd") or "").strip()
            if cwd and cwd != "<unknown>":
                cwd_counts[str(Path(cwd).expanduser())] += 1

    projects = [
        RecentProject(path=Path(cwd), label=_project_label(cwd), events=count)
        for cwd, count in cwd_counts.most_common()
    ]
    return projects


def discover_instruction_files(
    home: Path,
    codex_home: Path,
    recent_projects: list[RecentProject],
) -> list[InstructionCandidate]:
    candidates: dict[Path, dict[str, Any]] = {}

    def add(path: Path, *, scope: str, source: str, project_label: str | None = None) -> None:
        if not path.is_file():
            return
        key = path.resolve()
        current = candidates.setdefault(
            key,
            {
                "path": key,
                "scope": scope,
                "source": source,
                "project_labels": set(),
            },
        )
        if scope == "global":
            current["scope"] = "global"
        if source not in str(current["source"]).split(","):
            current["source"] = f"{current['source']},{source}"
        if project_label:
            current["project_labels"].add(project_label)

    for filename in GLOBAL_INSTRUCTION_FILES:
        add(codex_home / filename, scope="global", source="codex_home")

    for project in recent_projects:
        if not project.path.exists():
            continue
        for directory in _candidate_ancestors(project.path, home):
            for filename in PROJECT_INSTRUCTION_FILES:
                add(directory / filename, scope="project", source="project_ancestor", project_label=project.label)

    results = [
        InstructionCandidate(
            path=item["path"],
            scope=str(item["scope"]),
            source=str(item["source"]),
            project_labels=tuple(sorted(item["project_labels"])),
        )
        for item in candidates.values()
    ]
    return sorted(results, key=lambda item: (item.scope != "global", item.path.name, stable_hash(str(item.path))))


def _analyze_file(
    candidate: InstructionCandidate,
    usage_by_project: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        text = candidate.path.read_text(encoding="utf-8", errors="replace")
        stat = candidate.path.stat()
    except OSError:
        return _summary(candidate, "", None), [], []

    summary = _summary(candidate, text, stat.st_mtime)
    lower = text.lower()
    findings: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []
    target = _target(candidate)
    file_hash = summary["file_hash"]

    if _contains_secret(text):
        findings.append(
            _finding(
                f"secret-{file_hash}",
                "security",
                "high",
                "Potential secret in instruction file",
                "The file contains a token-shaped or key/value secret pattern. Move credentials to environment variables or a secret manager.",
                candidate,
            )
        )

    if any(marker in lower for marker in MODE_LOCK_MARKERS):
        findings.append(
            _finding(
                f"mode-lock-{file_hash}",
                "staleness",
                "medium",
                "Mode lock may be stale",
                "The file appears to force a narrow mode such as research-only or no-code work. This is useful temporarily but risky as a standing rule.",
                candidate,
            )
        )
        suggestions.append(
            _suggestion(
                f"mode-lock-{file_hash}",
                "Clarify temporary mode instructions",
                "medium",
                candidate.scope,
                target,
                "A narrow mode rule should say when it applies, otherwise Codex may avoid implementation when the user expects it.",
                "Use narrow modes only when the user explicitly asks for them. Otherwise, implement, verify, and report the smallest useful change.",
                "Remove this clarification if the workflow is intentionally research-only.",
            )
        )

    if candidate.scope == "global" and any(marker in lower for marker in GLOBAL_SCOPE_LEAK_MARKERS):
        findings.append(
            _finding(
                f"scope-leak-{file_hash}",
                "scope",
                "medium",
                "Project-specific preference may be global",
                "The global instruction file contains stack, style, or workflow markers that usually belong in a project AGENTS.md.",
                candidate,
            )
        )
        suggestions.append(
            _suggestion(
                f"scope-leak-{file_hash}",
                "Move project-specific rules out of global instructions",
                "medium",
                candidate.scope,
                target,
                "Global instructions should hold durable personal preferences. Project stack, UI style, and verification commands are safer in that project's AGENTS.md.",
                "Keep global instructions about your communication and safety preferences. Put project stack, UI style, commands, and workflow rules in the relevant AGENTS.md.",
                "Move the rule back only if it truly applies to every project.",
            )
        )

    if len(text) > 9000 or _word_count(text) > 1300:
        findings.append(
            _finding(
                f"bloat-{file_hash}",
                "maintainability",
                "low",
                "Instruction file is long",
                "Long instruction files increase the chance of stale, duplicated, or over-specific rules.",
                candidate,
            )
        )

    if len(ABSOLUTE_RE.findall(text)) >= 14:
        findings.append(
            _finding(
                f"absolute-rules-{file_hash}",
                "maintainability",
                "low",
                "Many absolute rules",
                "The file uses many absolute directives. Strong rules are useful, but too many can make Codex brittle across mixed tasks.",
                candidate,
            )
        )

    if any(marker in lower for marker in STALE_MARKERS):
        findings.append(
            _finding(
                f"stale-language-{file_hash}",
                "staleness",
                "low",
                "Stale-language markers found",
                "The file contains temporary or legacy wording. Review whether those rules still match the current workflow.",
                candidate,
            )
        )

    for project_label in candidate.project_labels:
        usage = usage_by_project.get(project_label, {})
        if not usage:
            continue
        suggestions.extend(_usage_suggestions(candidate, project_label, usage, lower, target, file_hash))

    return summary, findings, suggestions


def _usage_suggestions(
    candidate: InstructionCandidate,
    project_label: str,
    usage: dict[str, Any],
    lower_text: str,
    target: str,
    file_hash: str,
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    tool_calls = int(usage.get("tool_calls", 0) or 0)
    verification_calls = int(usage.get("verification_tool_calls", 0) or 0)
    compactions = int(usage.get("compactions", 0) or 0)
    prompt_average = float(usage.get("prompt_quality_average", 0) or 0)

    if tool_calls >= 6 and verification_calls / max(1, tool_calls) < 0.15 and not _has_any(lower_text, VERIFY_MARKERS):
        suggestions.append(
            _suggestion(
                f"verify-{file_hash}-{stable_hash(project_label)}",
                "Add a verification rule",
                "high" if tool_calls >= 12 else "medium",
                candidate.scope,
                target,
                f"{project_label} has implementation-like tool usage but this playbook does not mention verification.",
                "Before final status, run the smallest meaningful project check: test, build, lint, typecheck, browser probe, or runtime health check.",
                "Remove this rule if the project does not have a reliable local verification path.",
            )
        )

    if compactions > 0 and not _has_any(lower_text, RESUME_MARKERS):
        suggestions.append(
            _suggestion(
                f"resume-{file_hash}-{stable_hash(project_label)}",
                "Add a resume/checkpoint rule",
                "medium",
                candidate.scope,
                target,
                f"{project_label} had context compaction, but this playbook does not mention resume discipline.",
                "For long tasks, keep a short durable checklist and verify files or generated artifacts before resuming after interruption or compaction.",
                "Remove this rule if the project work is always short-lived.",
            )
        )

    if 0 < prompt_average < 5 and not _has_any(lower_text, PROMPT_MARKERS):
        suggestions.append(
            _suggestion(
                f"prompt-shape-{file_hash}-{stable_hash(project_label)}",
                "Add a prompt-shaping cue",
                "medium",
                candidate.scope,
                target,
                f"{project_label} has low prompt clarity scores and this playbook does not mention target or success-state cues.",
                "When asking for work in this project, include the action, target subsystem or file, relevant constraint, and success state.",
                "Remove this cue if it feels redundant after a week.",
            )
        )

    return suggestions


def _coverage_findings(
    recent_projects: list[RecentProject],
    covered_projects: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []
    for project in recent_projects[:6]:
        if project.label in covered_projects or project.events < 2 or not project.path.exists():
            continue
        project_hash = stable_hash(str(project.path))
        findings.append(
            {
                "id": f"missing-playbook-{project_hash}",
                "category": "coverage",
                "severity": "medium",
                "title": "Active project has no discovered AGENTS.md",
                "body": "A recently used project does not appear to have an AGENTS.md in the working directory or its nearby ancestors.",
                "scope": "project",
                "target": project.label,
            }
        )
        suggestions.append(
            _suggestion(
                f"missing-playbook-{project_hash}",
                "Add a small project playbook",
                "medium",
                "project",
                project.label,
                "Codex Coach saw repeated activity in this project but no local AGENTS.md. A short playbook can prevent repeated context rebuilding.",
                "# AGENTS\n\n## Project Context\n- Stack: [fill in]\n- Key commands: [test/build/lint]\n- Verification: run the smallest meaningful check before final status.\n- Constraints: [generated files, deployment, privacy, or style rules]\n",
                "Delete the AGENTS.md if it does not improve project handoffs.",
            )
        )
    return findings, suggestions


def _summary(candidate: InstructionCandidate, text: str, mtime: float | None) -> dict[str, Any]:
    modified_at = None
    if mtime is not None:
        modified_at = datetime.fromtimestamp(mtime, tz=UTC).isoformat(timespec="seconds")
    return {
        "file": candidate.path.name,
        "file_hash": stable_hash(str(candidate.path)),
        "content_hash": stable_hash(text) if text else None,
        "scope": candidate.scope,
        "source": candidate.source,
        "project_labels": list(candidate.project_labels),
        "bytes": len(text.encode("utf-8", "ignore")),
        "lines": len(text.splitlines()),
        "modified_at": modified_at,
    }


def _candidate_ancestors(path: Path, home: Path) -> list[Path]:
    start = path if path.is_dir() else path.parent
    try:
        current = start.resolve()
    except OSError:
        current = start
    ancestors: list[Path] = []
    for _ in range(8):
        ancestors.append(current)
        if current == current.parent:
            break
        if current == home:
            break
        current = current.parent
    return ancestors


def _project_label(cwd: str) -> str:
    path = Path(cwd)
    name = path.name or "project"
    return f"{name} [{stable_hash(cwd)}]"


def _finding(
    finding_id: str,
    category: str,
    severity: str,
    title: str,
    body: str,
    candidate: InstructionCandidate,
) -> dict[str, Any]:
    return {
        "id": finding_id,
        "category": category,
        "severity": severity,
        "title": title,
        "body": body,
        "scope": candidate.scope,
        "target": _target(candidate),
    }


def _suggestion(
    suggestion_id: str,
    title: str,
    confidence: str,
    scope: str,
    target: str,
    body: str,
    suggested_text: str,
    rollback: str,
) -> dict[str, Any]:
    return {
        "id": suggestion_id,
        "title": title,
        "confidence": confidence,
        "scope": scope,
        "target": target,
        "body": body,
        "suggested_text": suggested_text,
        "rollback": rollback,
    }


def _target(candidate: InstructionCandidate) -> str:
    if candidate.project_labels:
        return ", ".join(candidate.project_labels[:3])
    return f"{candidate.path.name} [{stable_hash(str(candidate.path))}]"


def _contains_secret(text: str) -> bool:
    return bool(SECRET_RE.search(text) or NPM_TOKEN_RE.search(text) or KEY_VALUE_SECRET_RE.search(text))


def _word_count(text: str) -> int:
    return len([word for word in re.split(r"\s+", text.strip()) if word])


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        item_id = str(item.get("id") or stable_hash(json.dumps(item, sort_keys=True, default=str)))
        if item_id in seen:
            continue
        seen.add(item_id)
        result.append(item)
    return result
