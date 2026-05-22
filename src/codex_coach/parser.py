from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .prompts import score_prompt
from .redaction import stable_hash
from .timeutil import parse_timestamp

VERIFY_RE = (
    "test",
    "pytest",
    "vitest",
    "jest",
    "playwright",
    "lint",
    "typecheck",
    "tsc",
    "mypy",
    "ruff",
    "build",
    "cargo test",
    "go test",
    "gradle test",
)
ERROR_RE = (
    "error",
    "exception",
    "traceback",
    "failed",
    "failure",
    "timeout",
    "panic",
    "context_length_exceeded",
    "usage_limit_reached",
    "upstream_unavailable",
)


@dataclass
class ScanAccumulator:
    since: str | None = None
    files_scanned: int = 0
    malformed_lines: int = 0
    sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    projects: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    project_sessions: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    totals: Counter = field(default_factory=Counter)
    tool_counts: Counter = field(default_factory=Counter)
    model_counts: Counter = field(default_factory=Counter)
    effort_counts: Counter = field(default_factory=Counter)
    source_counts: Counter = field(default_factory=Counter)
    originator_counts: Counter = field(default_factory=Counter)
    project_tools: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    project_efforts: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    project_verification_tools: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    project_prompt_scores: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    prompt_scores: list[dict[str, Any]] = field(default_factory=list)
    error_counts: Counter = field(default_factory=Counter)
    verification_tools: Counter = field(default_factory=Counter)
    compacted_sessions: set[str] = field(default_factory=set)
    current_file_session: dict[str, str] = field(default_factory=dict)

    def to_facts(self) -> dict[str, Any]:
        projects = []
        project_capsules = []
        for cwd, counts in self.projects.items():
            project_counts = counts.copy()
            project_counts["sessions"] = len(self.project_sessions[cwd])
            verification_tool_calls = sum(self.project_verification_tools[cwd].values())
            projects.append(
                {
                    "cwd": cwd,
                    "sessions": project_counts["sessions"],
                    "turns": counts["turns"],
                    "user_messages": counts["user_messages"],
                    "tool_calls": counts["tool_calls"],
                    "verification_tool_calls": verification_tool_calls,
                    "compactions": counts["compactions"],
                }
            )
            project_capsules.append(
                _project_capsule(
                    cwd,
                    project_counts,
                    self.project_tools[cwd],
                    self.project_efforts[cwd],
                    self.project_prompt_scores[cwd],
                    verification_tool_calls,
                )
            )
        projects.sort(key=lambda item: (item["user_messages"], item["tool_calls"], item["turns"]), reverse=True)
        project_capsules.sort(key=lambda item: (item["user_messages"], item["tool_calls"], item["turns"]), reverse=True)

        prompt_categories = Counter(item["category"] for item in self.prompt_scores)
        avg_prompt = 0.0
        if self.prompt_scores:
            avg_prompt = round(sum(int(item["score"]) for item in self.prompt_scores) / len(self.prompt_scores), 2)

        return {
            "schema_version": 1,
            "since": self.since,
            "totals": {
                "files_scanned": self.files_scanned,
                "malformed_lines": self.malformed_lines,
                "sessions": len(self.sessions),
                "turns": self.totals["turns"],
                "user_messages": self.totals["user_messages"],
                "assistant_messages": self.totals["assistant_messages"],
                "tool_calls": self.totals["tool_calls"],
                "web_searches": self.totals["web_searches"],
                "reasoning_items": self.totals["reasoning_items"],
                "compactions": self.totals["compactions"],
                "errors": sum(self.error_counts.values()),
                "verification_tool_calls": sum(self.verification_tools.values()),
            },
            "projects": projects,
            "project_capsules": project_capsules,
            "models": dict(self.model_counts.most_common()),
            "efforts": dict(self.effort_counts.most_common()),
            "sources": dict(self.source_counts.most_common()),
            "originators": dict(self.originator_counts.most_common()),
            "tools": dict(self.tool_counts.most_common()),
            "verification_tools": dict(self.verification_tools.most_common()),
            "errors": dict(self.error_counts.most_common()),
            "prompt_quality": {
                "average_score": avg_prompt,
                "categories": dict(prompt_categories),
                "examples_needing_work": [item for item in self.prompt_scores if item["category"] == "needs_work"][:10],
                "rewrite_examples": [item for item in self.prompt_scores if item["category"] == "needs_work"][:5],
            },
            "compacted_session_ids": sorted(self.compacted_sessions),
        }


def iter_log_paths(codex_home: Path) -> list[Path]:
    paths: list[Path] = []
    sessions_dir = codex_home / "sessions"
    archived_dir = codex_home / "archived_sessions"
    if sessions_dir.exists():
        paths.extend(sessions_dir.glob("**/*.jsonl"))
    if archived_dir.exists():
        paths.extend(archived_dir.glob("*.jsonl"))
    return sorted(path for path in paths if path.is_file())


def scan_logs(codex_home: Path, *, since_dt=None, since_label: str | None = None) -> dict[str, Any]:
    acc = ScanAccumulator(since=since_label)
    for path in iter_log_paths(codex_home):
        if since_dt is not None:
            try:
                if path.stat().st_mtime < since_dt.timestamp():
                    continue
            except OSError:
                acc.malformed_lines += 1
                continue
        _scan_file(path, acc, since_dt=since_dt)
    return acc.to_facts()


def _scan_file(path: Path, acc: ScanAccumulator, *, since_dt) -> None:
    acc.files_scanned += 1
    fallback_session_id = path.stem
    current_session_id = fallback_session_id
    current_cwd = "<unknown>"
    file_had_session = False

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        acc.malformed_lines += 1
        return

    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            acc.malformed_lines += 1
            continue

        timestamp = parse_timestamp(event.get("timestamp"))
        if since_dt is not None and timestamp is not None and timestamp < since_dt:
            continue

        event_type = event.get("type")
        payload = event.get("payload") or {}
        if event_type == "session_meta":
            current_session_id, current_cwd = _handle_session(payload, acc, fallback_session_id)
            if not file_had_session:
                file_had_session = True
            continue
        if event_type == "turn_context":
            current_cwd = _project_label(str(payload.get("cwd") or current_cwd or "<unknown>"))
            acc.project_sessions[current_cwd].add(current_session_id)
            _handle_turn(payload, acc, current_cwd)
            continue
        if event_type == "response_item":
            _handle_response_item(payload, acc, current_cwd)
            continue
        if event_type == "event_msg":
            _handle_event_msg(payload, acc)
            continue
        if event_type == "compacted":
            acc.totals["compactions"] += 1
            acc.projects[current_cwd]["compactions"] += 1
            acc.compacted_sessions.add(current_session_id)


def _handle_session(payload: dict[str, Any], acc: ScanAccumulator, fallback_session_id: str) -> tuple[str, str]:
    session_id = str(payload.get("id") or fallback_session_id)
    cwd = _project_label(str(payload.get("cwd") or "<unknown>"))
    acc.sessions.setdefault(
        session_id,
        {
            "cwd": cwd,
            "timestamp": payload.get("timestamp"),
            "source": payload.get("source"),
            "originator": payload.get("originator"),
            "cli_version": payload.get("cli_version"),
        },
    )
    if payload.get("source"):
        acc.source_counts[str(payload["source"])] += 1
    if payload.get("originator"):
        acc.originator_counts[str(payload["originator"])] += 1
    acc.project_sessions[cwd].add(session_id)
    return session_id, cwd


def _project_label(cwd: str) -> str:
    if not cwd or cwd == "<unknown>":
        return "<unknown>"
    path = Path(cwd)
    name = path.name or "project"
    return f"{name} [{stable_hash(cwd)}]"


def _handle_turn(payload: dict[str, Any], acc: ScanAccumulator, cwd: str) -> None:
    acc.totals["turns"] += 1
    acc.projects[cwd]["turns"] += 1
    model = payload.get("model")
    effort = payload.get("effort")
    if model:
        acc.model_counts[str(model)] += 1
    if effort:
        acc.effort_counts[str(effort)] += 1
        acc.project_efforts[cwd][str(effort)] += 1


def _handle_response_item(payload: dict[str, Any], acc: ScanAccumulator, cwd: str) -> None:
    item = payload.get("item") if isinstance(payload.get("item"), dict) else payload
    item_type = item.get("type")
    if item_type == "message":
        role = item.get("role")
        text = _content_text(item.get("content"))
        if role == "user":
            acc.totals["user_messages"] += 1
            acc.projects[cwd]["user_messages"] += 1
            score = score_prompt(text)
            acc.prompt_scores.append(
                {
                    "score": score.score,
                    "category": score.category,
                    "reason": score.reason,
                    "preview": score.preview,
                    "missing": list(score.missing),
                    "rewrite": score.rewrite,
                    **score.stats,
                }
            )
            acc.project_prompt_scores[cwd].append(score.score)
        elif role == "assistant":
            acc.totals["assistant_messages"] += 1
        _count_errors(text, acc)
        return

    if item_type == "function_call":
        name = str(item.get("name") or "<unknown>")
        acc.totals["tool_calls"] += 1
        acc.projects[cwd]["tool_calls"] += 1
        acc.tool_counts[name] += 1
        acc.project_tools[cwd][name] += 1
        arguments = item.get("arguments")
        arg_text = arguments if isinstance(arguments, str) else json.dumps(arguments, default=str)
        if _looks_like_verification(name, arg_text):
            acc.verification_tools[name] += 1
            acc.project_verification_tools[cwd][name] += 1
        return

    if item_type == "function_call_output":
        text = _content_text(item.get("output") or item.get("content"))
        _count_errors(text, acc)
        return

    if item_type == "web_search_call":
        acc.totals["web_searches"] += 1
        return

    if item_type == "reasoning":
        acc.totals["reasoning_items"] += 1


def _handle_event_msg(payload: dict[str, Any], acc: ScanAccumulator) -> None:
    message = _content_text(payload.get("message") or payload.get("text") or payload)
    _count_errors(message, acc)


def _project_capsule(
    cwd: str,
    counts: Counter,
    tools: Counter,
    efforts: Counter,
    prompt_scores: list[int],
    verification_tool_calls: int,
) -> dict[str, Any]:
    prompt_average = round(sum(prompt_scores) / len(prompt_scores), 2) if prompt_scores else 0.0
    workflow = _infer_workflow(tools, counts)
    instruction = _project_instruction(counts, prompt_average, verification_tool_calls)
    return {
        "project": cwd,
        "sessions": counts["sessions"],
        "turns": counts["turns"],
        "user_messages": counts["user_messages"],
        "tool_calls": counts["tool_calls"],
        "verification_tool_calls": verification_tool_calls,
        "compactions": counts["compactions"],
        "prompt_quality_average": prompt_average,
        "top_tools": dict(tools.most_common(5)),
        "effort_mix": dict(efforts.most_common()),
        "likely_workflow": workflow,
        "recommended_instruction": instruction,
        "skill_candidate": counts["turns"] >= 3 or counts["tool_calls"] >= 10,
    }


def _infer_workflow(tools: Counter, counts: Counter) -> str:
    names = set(tools)
    if any(name.startswith("browser_") or name in {"screenshot", "view_image"} for name in names):
        return "UI or browser verification"
    if tools.get("web.run", 0) or "web_search" in names:
        return "research and current-information checks"
    if tools.get("exec_command", 0) >= max(2, counts["tool_calls"] // 2):
        return "terminal-heavy implementation or diagnosis"
    if tools.get("update_plan", 0) >= 2:
        return "multi-step planning and execution"
    if counts["tool_calls"] == 0:
        return "conversation and planning"
    return "mixed Codex workflow"


def _project_instruction(counts: Counter, prompt_average: float, verification_tool_calls: int) -> str:
    tool_calls = max(1, counts["tool_calls"])
    if counts["compactions"] > 0:
        return "For long tasks in this project, keep a short durable checklist and validate files before resuming after compaction."
    if counts["tool_calls"] >= 6 and verification_tool_calls / tool_calls < 0.15:
        return "Before final status in this project, run the smallest meaningful test, build, lint, browser check, or runtime probe."
    if prompt_average and prompt_average < 5:
        return "Start prompts for this project with action, target file or subsystem, symptom or goal, and success state."
    return "Keep the project context compact: state the active subsystem, constraints, and the verification expected for user-facing changes."


def _content_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        chunks: list[str] = []
        for item in value:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                chunks.append(str(item.get("text") or item.get("content") or ""))
        return "\n".join(part for part in chunks if part)
    if isinstance(value, dict):
        return str(value.get("text") or value.get("content") or value.get("message") or "")
    return str(value)


def _looks_like_verification(tool_name: str, arguments: str) -> bool:
    text = f"{tool_name} {arguments}".lower()
    return any(marker in text for marker in VERIFY_RE)


def _count_errors(text: str, acc: ScanAccumulator) -> None:
    lower = text.lower()
    for marker in ERROR_RE:
        if marker in lower:
            acc.error_counts[marker] += 1
            return
