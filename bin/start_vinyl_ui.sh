#!/usr/bin/env bash
set -euo pipefail

export DISPLAY=${DISPLAY:-:0}
export XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}
export SDL_VIDEODRIVER=x11

cd "$HOME/digital-vinyl-player/ui"

# Start UI
/usr/bin/python3 "$HOME/digital-vinyl-player/ui/vinyl_ui.py" &
UI_PID=$!

# Keep it on top (X11)
while kill -0 "$UI_PID" 2>/dev/null; do
  wmctrl -a "Vinyl UI" 2>/dev/null || true
  sleep 2
done
