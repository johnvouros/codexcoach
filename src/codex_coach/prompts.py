from __future__ import annotations

import re
from dataclasses import dataclass

from .redaction import redact_text, text_stats

PATH_HINT_RE = re.compile(r"(?:^|\s)(?:\.{0,2}/|~?/|[A-Za-z]:\\|[\w.-]+\.(?:py|ts|tsx|js|jsx|md|json|toml|yaml|yml|go|rs|java|cs|rb|php))")
URL_HINT_RE = re.compile(r"https?://")
ERROR_HINT_RE = re.compile(r"\b(error|exception|traceback|failed|failing|crash|stuck|timeout|panic|bug|regression|broken)\b", re.IGNORECASE)
SUCCESS_HINT_RE = re.compile(r"\b(success|done|verify|should|expected|acceptance|criteria|when|until|so that)\b", re.IGNORECASE)
COMMAND_HINT_RE = re.compile(r"`[^`]+`|\b(npm|pnpm|bun|uv|python|pytest|git|cargo|go test|make|docker|codex)\b", re.IGNORECASE)
ACTION_HINT_RE = re.compile(r"\b(run|implement|build|fix|debug|analyze|review|refactor|test|install|deploy|create|update|remove|delete|generate|explain)\b", re.IGNORECASE)
VAGUE_RE = re.compile(r"^(fix|run|update|delete|improve|optimi[sz]e|make better|where|why|ok|nice|worked|continue|proceed|do it|go)$", re.IGNORECASE)
VALID_CONTEXT_REPLY_RE = re.compile(r"^(yes|y|no|n|ok|okay|proceed|continue|go ahead|do it|run tests|commit|push|retry|try again|1|2|3|4|5|a|b|c|d)$", re.IGNORECASE)


@dataclass(frozen=True)
class PromptScore:
    score: int
    category: str
    reason: str
    preview: str
    missing: tuple[str, ...]
    rewrite: str
    stats: dict[str, int | str]


def score_prompt(text: str) -> PromptScore:
    stripped = text.strip()
    lower = stripped.lower()
    words = [part for part in re.split(r"\s+", stripped) if part]
    score = 4
    reasons: list[str] = []

    if not stripped:
        return PromptScore(0, "needs_work", "empty prompt", "", ("action", "target", "success state"), _rewrite_prompt(()), text_stats(text))

    if stripped.startswith("<environment_context>") or stripped.startswith("# AGENTS.md instructions"):
        return PromptScore(
            7,
            "good",
            "machine-provided context block",
            redact_text(text),
            (),
            "No rewrite needed for machine-provided context blocks.",
            text_stats(text),
        )

    if VALID_CONTEXT_REPLY_RE.match(stripped):
        return PromptScore(
            7,
            "good",
            "brief response that is usually valid with conversation context",
            redact_text(text),
            (),
            "No rewrite needed when the previous Codex turn made the choice explicit.",
            text_stats(text),
        )

    if stripped.startswith("[$") and "](" in stripped:
        return PromptScore(
            7,
            "good",
            "Codex skill or plugin invocation",
            redact_text(text),
            (),
            "No rewrite needed when the invocation intentionally activates a Codex skill or plugin.",
            text_stats(text),
        )

    if len(words) <= 2 and VAGUE_RE.match(stripped):
        missing = ("target", "success state")
        return PromptScore(
            3,
            "needs_work",
            "very short prompt with ambiguous target or action",
            redact_text(text),
            missing,
            _rewrite_prompt(missing),
            text_stats(text),
        )

    has_action = bool(ACTION_HINT_RE.search(stripped))
    has_target = bool(PATH_HINT_RE.search(stripped) or URL_HINT_RE.search(stripped))
    has_failure = bool(ERROR_HINT_RE.search(stripped))
    has_success = bool(SUCCESS_HINT_RE.search(stripped))
    has_command = bool(COMMAND_HINT_RE.search(stripped))

    if len(words) >= 8:
        score += 1
        reasons.append("clear length")
    if has_action:
        score += 1
        reasons.append("action stated")
    if has_target:
        score += 1
        reasons.append("file or path context")
    if has_failure:
        score += 1
        reasons.append("failure context")
    if has_success:
        score += 1
        reasons.append("success context")
    if has_command:
        score += 1
        reasons.append("command context")

    if len(words) < 4:
        score -= 1
        reasons.append("short")
    if re.search(r"\b(fix|update|delete|improve|optimi[sz]e|make)\b", lower) and not (
        has_target or has_failure or has_success
    ):
        score -= 2
        reasons.append("missing target detail")

    missing: list[str] = []
    if not has_action:
        missing.append("action")
    if not has_target and not has_failure and len(words) >= 3:
        missing.append("target")
    if (has_action or has_failure) and not has_success:
        missing.append("success state")
    if has_action and not has_command and any(verb in lower for verb in ("fix", "debug", "implement", "build", "refactor", "deploy")):
        missing.append("verification")

    score = max(0, min(10, score))
    if score >= 8:
        category = "excellent"
    elif score >= 5:
        category = "good"
    else:
        category = "needs_work"
    reason = ", ".join(reasons[:4]) or "basic request"
    missing_tuple = tuple(dict.fromkeys(missing))
    return PromptScore(score, category, reason, redact_text(text), missing_tuple, _rewrite_prompt(missing_tuple), text_stats(text))


def _rewrite_prompt(missing: tuple[str, ...]) -> str:
    if not missing:
        return "Keep the prompt shape. Add a success check only if the task touches code, config, deploys, or user-visible behavior."
    parts = [
        "[Action] in [project/file]",
        "because [symptom or goal]",
        "using [relevant command, link, or constraint]",
        "Success means [observable verification result].",
    ]
    if "verification" in missing and "success state" not in missing:
        parts[-1] = "Verify with [smallest meaningful test/build/runtime check]."
    return " ".join(parts)
