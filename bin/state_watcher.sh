#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

# -------------------------
# Spotify geometry (ON screen)
# -------------------------
SPOT_ON_X=80
SPOT_ON_Y=200
SPOT_ON_W=900
SPOT_ON_H=695

# Spotify geometry (OFF screen)
SPOT_OFF_X=2500
SPOT_OFF_Y=2500
SPOT_OFF_W=900
SPOT_OFF_H=700

# Onboard geometry
KB_X=86
KB_Y=564
KB_W=907
KB_H=266

# Vinyl window title contains this
VINYL_TITLE="Vinyl UI"

# Debounce: how long Paused/Stopped must persist before showing Spotify
PAUSE_DEBOUNCE_SEC=1.2

# How often to force-apply even if status didn't change
FORCE_EVERY=8   # 8 * 0.25s = every 2 seconds

# -------------------------
# Helpers
# -------------------------
now_s() { date +%s.%N; }

float_ge() {
  # usage: float_ge A B  -> returns 0 if A>=B else 1
  python3 - "$1" "$2" <<'PY'
import sys
a=float(sys.argv[1]); b=float(sys.argv[2])
sys.exit(0 if a>=b else 1)
PY
}

float_sub() {
  # usage: float_sub A B -> prints A-B
  python3 - "$1" "$2" <<'PY'
import sys
a=float(sys.argv[1]); b=float(sys.argv[2])
print(a-b)
PY
}

find_vinyl_win() {
  wmctrl -l | awk -v m="$VINYL_TITLE" 'index($0,m){print $1}' | tail -n 1
}

find_spotify_win() {
  # Chromium window that contains spotify in class/title lines
  wmctrl -lx | awk 'tolower($0) ~ /chromium/ && tolower($0) ~ /spotify/ {print $1}' | tail -n 1
}

raise_win() {
  local win="${1:-}"
  [[ -n "$win" ]] || return 0
  wmctrl -i -a "$win" >/dev/null 2>&1 || true
}

move_resize() {
  local win="${1:-}" x="$2" y="$3" w="$4" h="$5"
  [[ -n "$win" ]] || return 0
  wmctrl -i -r "$win" -b remove,maximized_vert,maximized_horz,fullscreen >/dev/null 2>&1 || true
  wmctrl -i -r "$win" -e "0,${x},${y},${w},${h}" >/dev/null 2>&1 || true
}

lock_onboard() {
  wmctrl -r "Onboard" -b remove,maximized_vert,maximized_horz,fullscreen >/dev/null 2>&1 || true
  wmctrl -r "Onboard" -e "0,${KB_X},${KB_Y},${KB_W},${KB_H}" >/dev/null 2>&1 || true
}

# Pick chromium.instance player
pick_player() {
  playerctl -l 2>/dev/null | grep -i '^chromium\.instance' | head -n 1 || true
}

PLAYER="$(pick_player)"
if [[ -z "${PLAYER:-}" ]]; then
  echo "No chromium.instance player found (playerctl -l)."
  exit 0
fi

last="__init__"
paused_since="0"
i=0

while true; do
  status="$(playerctl -p "$PLAYER" status 2>/dev/null || echo "Stopped")"
  t="$(now_s)"
  i=$((i+1))

  # Always refresh window IDs
  S="$(find_spotify_win || true)"
  V="$(find_vinyl_win   || true)"

  # If playing: immediately park Spotify + show Vinyl
  if [[ "$status" == "Playing" ]]; then
    paused_since="0"

    if [[ "$last" != "Playing" || $((i % FORCE_EVERY)) -eq 0 ]]; then
      move_resize "$S" "$SPOT_OFF_X" "$SPOT_OFF_Y" "$SPOT_OFF_W" "$SPOT_OFF_H"
      raise_win "$V"
      lock_onboard
      last="Playing"
    fi

  else
    # Paused/Stopped: start debounce timer
    if [[ "$paused_since" == "0" ]]; then
      paused_since="$t"
    fi

    # Only show Spotify if paused long enough
    dt="$(float_sub "$t" "$paused_since")"
    if float_ge "$dt" "$PAUSE_DEBOUNCE_SEC"; then
      if [[ "$last" == "Playing" || "$last" != "$status" || $((i % FORCE_EVERY)) -eq 0 ]]; then
        move_resize "$S" "$SPOT_ON_X" "$SPOT_ON_Y" "$SPOT_ON_W" "$SPOT_ON_H"
        raise_win "$S"
        lock_onboard
        last="$status"
      fi
    fi
  fi

  sleep 0.25
done

