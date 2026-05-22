#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SCHEDULE="weekly"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --daily)
      SCHEDULE="daily"
      ;;
    --weekly)
      SCHEDULE="weekly"
      ;;
    --no-schedule)
      SCHEDULE="none"
      ;;
    *)
      echo "unknown option: $1" >&2
      echo "usage: ./install.sh [--weekly|--daily|--no-schedule]" >&2
      exit 2
      ;;
  esac
  shift
done

PYTHON_BIN="${PYTHON:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "python3 is required to install Codex Coach" >&2
  exit 1
fi

PYTHONPATH="$SCRIPT_DIR/src${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" -m codex_coach.cli install \
  --source-root "$SCRIPT_DIR" \
  --schedule "$SCHEDULE"

cat <<'MSG'

Codex Coach installed.

Next:
  1. Make sure ~/.local/bin is on PATH.
  2. Restart Codex.
  3. Ask: Coach my Codex usage

CLI:
  codex-coach doctor
  codex-coach report --since 7d
MSG
