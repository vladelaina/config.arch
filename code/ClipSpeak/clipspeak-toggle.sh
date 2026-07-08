#!/usr/bin/env sh
set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
PYTHON="$APP_DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
  PYTHON="$(command -v python3 || command -v python || true)"
fi

if [ -z "$PYTHON" ]; then
  echo "ClipSpeak: python not found" >&2
  exit 127
fi

CLIPSPEAK_READER="$APP_DIR/clipboard_reader.py"

if [ ! -r "$CLIPSPEAK_READER" ]; then
  echo "ClipSpeak: missing clipboard_reader.py at $CLIPSPEAK_READER" >&2
  exit 1
fi

if command -v kitty >/dev/null 2>&1; then
  exec kitty --class clipspeak --name clipspeak --title ClipSpeak -e sh -c '
    "$1" "$2" --once
    status=$?
    if [ "$status" -ne 0 ]; then
      printf "\nClipSpeak exited with status %s. Press Enter to close..." "$status"
      IFS= read -r _
    fi
    exit "$status"
  ' sh "$PYTHON" "$CLIPSPEAK_READER"
fi

exec "$PYTHON" "$CLIPSPEAK_READER" --once
