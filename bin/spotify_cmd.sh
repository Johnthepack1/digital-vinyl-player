#!/usr/bin/env bash
set -euo pipefail
export DISPLAY=${DISPLAY:-:0}
export XAUTHORITY=${XAUTHORITY:-/home/vinyl2/.Xauthority}

CMD="${1:-play-pause}"

# Try playerctl first (best)
playerctl "$CMD" >/dev/null 2>&1 || true
sleep 0.15

# If it worked, stop here
STATUS="$(playerctl status 2>/dev/null || true)"
if [[ "$CMD" == "pause" ]]; then
  exit 0
fi
if [[ "$STATUS" == "Playing" ]]; then
  exit 0
fi

# Fallback: focus Spotify/Chromium window and send Space (X11)
# Try common window titles used by Chromium --app and Spotify
wmctrl -a "Spotify" 2>/dev/null || true
wmctrl -a "Spotify – Web Player" 2>/dev/null || true
wmctrl -a "Spotify - Web Player" 2>/dev/null || true
wmctrl -a "Chromium" 2>/dev/null || true
sleep 0.10

# Space toggles play in Spotify Web Player
xdotool key space >/dev/null 2>&1 || true
