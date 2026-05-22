from __future__ import annotations

from datetime import UTC, datetime, timedelta


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_since(value: str | None, *, now: datetime | None = None) -> datetime | None:
    if not value:
        return None
    now = now or utc_now()
    text = value.strip().lower()
    units = {
        "h": "hours",
        "hour": "hours",
        "hours": "hours",
        "d": "days",
        "day": "days",
        "days": "days",
        "w": "weeks",
        "week": "weeks",
        "weeks": "weeks",
    }
    for suffix, unit in sorted(units.items(), key=lambda item: len(item[0]), reverse=True):
        if text.endswith(suffix):
            amount = text[: -len(suffix)].strip()
            if amount.isdigit():
                return now - timedelta(**{unit: int(amount)})
    parsed = parse_timestamp(value)
    if parsed is not None:
        return parsed
    raise ValueError(f"Unsupported --since value: {value!r}. Use values like 7d, 2w, 24h, or an ISO timestamp.")
