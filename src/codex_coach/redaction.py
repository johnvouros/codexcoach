from __future__ import annotations

import hashlib
import re

PATH_RE = re.compile(r"(?<!\w)(?:~|/Users/[^ \n\t]+|/home/[^ \n\t]+|/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+){2,})")
URL_RE = re.compile(r"https?://[^\s)>\]]+")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
SECRET_RE = re.compile(r"\b(?:sk|pk|ghp|github_pat|xox[baprs])-?[A-Za-z0-9_\-]{12,}\b", re.IGNORECASE)
LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")
WHITESPACE_RE = re.compile(r"\s+")


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()[:12]


def redact_text(text: str, *, max_chars: int = 96) -> str:
    text = URL_RE.sub("[url]", text)
    text = EMAIL_RE.sub("[email]", text)
    text = SECRET_RE.sub("[secret]", text)
    text = PATH_RE.sub("[path]", text)
    text = LONG_TOKEN_RE.sub("[token]", text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    if len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "..."
    return text


def text_stats(text: str) -> dict[str, int | str]:
    return {
        "chars": len(text),
        "words": len([part for part in WHITESPACE_RE.split(text.strip()) if part]),
        "hash": stable_hash(text),
    }
