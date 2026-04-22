#!/usr/bin/env bash
set -euo pipefail

cd "$HOME/digital-vinyl-player"

if [ -x "$HOME/digital-vinyl-player/venv/bin/python" ]; then
  exec "$HOME/digital-vinyl-player/venv/bin/python" -u bin/setup_portal.py
fi

exec /usr/bin/python3 -u bin/setup_portal.py
