#!/usr/bin/env bash
set -euo pipefail

cd "$HOME/digital-vinyl-player"

# Prefer venv python if present
if [ -x "$HOME/digital-vinyl-player/venv/bin/python" ]; then
  exec "$HOME/digital-vinyl-player/venv/bin/python" -u ui/vinyl_ui.py
else
  exec /usr/bin/python3 -u ui/vinyl_ui.py
fi
