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

# On-screen keyboard
START_KEYBOARD=1
KEYBOARD_AUTO_SHOW=1

# Onboard window geometry
KB_X=86
KB_Y=564
KB_W=907
KB_H=266

VINYL_TITLE="Vinyl UI"

# Debounce so a quick "Paused" during track skip doesn't flash Spotify
PAUSE_DEBOUNCE_SEC=1.25

# -------------------------
# Wait for GUI / X to be usable
# -------------------------
wait_for_x() {
  # wmctrl will fail if X isn't ready, so loop until it works
  for _ in {1..200}; do
    wmctrl -m >/dev/null 2>&1 && return 0
    sleep 0.1
  done
  return 1
}

# -------------------------
# Helpers
# -------------------------
find_vinyl_win() {
  wmctrl -l | awk -v m="$VINYL_TITLE" 'index($0,m){print $1}' | tail -n 1
}

find_spotify_win() {
  # your class is: open.spotify.com__home.Chromium
  wmctrl -lx | awk 'tolower($0) ~ /open\.spotify\.com/ {print $1}' | tail -n 1
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

pick_player() {
  # prefer chromium.instance*
  playerctl -l 2>/dev/null | grep -i '^chromium\.instance' | head -n 1 || true
}

start_keyboard() {
  (( START_KEYBOARD == 1 )) || return 0

  if command -v gsettings >/dev/null 2>&1; then
    if (( KEYBOARD_AUTO_SHOW == 1 )); then
      gsettings set org.onboard auto-show true >/dev/null 2>&1 || true
      gsettings set org.onboard show-status-icon false >/dev/null 2>&1 || true
    else
      gsettings set org.onboard auto-show false >/dev/null 2>&1 || true
    fi
  fi

  pgrep -x onboard >/dev/null 2>&1 || (onboard --hidden >/dev/null 2>&1 & disown || true)
}

lock_onboard_geom() {
  wmctrl -r "Onboard" -b remove,maximized_vert,maximized_horz,fullscreen >/dev/null 2>&1 || true
  wmctrl -r "Onboard" -e "0,${KB_X},${KB_Y},${KB_W},${KB_H}" >/dev/null 2>&1 || true
}

# -------------------------
# Main
# -------------------------
# Never exit if X isn't ready yet — just keep waiting.
until wait_for_x; do
  sleep 1
done

start_keyboard

PLAYER="$(pick_player || true)"
last="__init__"
paused_since=""

while true; do
  # player might appear later; keep trying
  if [[ -z "${PLAYER:-}" ]]; then
    PLAYER="$(pick_player || true)"
    sleep 0.25
    continue
  fi

  status="$(playerctl -p "$PLAYER" status 2>/dev/null || echo "Stopped")"
  now="$(date +%s.%N)"

  S="$(find_spotify_win || true)"
  V="$(find_vinyl_win   || true)"

  if [[ "$status" == "Playing" ]]; then
    paused_since=""
    if [[ "$last" != "Playing" ]]; then
      move_resize "$S" "$SPOT_OFF_X" "$SPOT_OFF_Y" "$SPOT_OFF_W" "$SPOT_OFF_H"
      wmctrl -i -r "$S" -b add,below >/dev/null 2>&1 || true
      wmctrl -i -r "$V" -b add,above >/dev/null 2>&1 || true
      raise_win "$V"
      last="Playing"
    fi

  else
    # Paused / Stopped
    if [[ -z "${paused_since:-}" ]]; then
      paused_since="$now"
    fi

    # Only switch back after debounce time
    ok="$(python3 - <<PY 2>/dev/null || echo 0
t0=float("${paused_since}")
tn=float("${now}")
print(1 if (tn-t0) >= float("${PAUSE_DEBOUNCE_SEC}") else 0)
PY
)"
    if [[ "$ok" == "1" && "$last" != "Paused" ]]; then
      move_resize "$S" "$SPOT_ON_X" "$SPOT_ON_Y" "$SPOT_ON_W" "$SPOT_ON_H"
      wmctrl -i -r "$S" -b remove,below >/dev/null 2>&1 || true
      wmctrl -i -r "$V" -b remove,above >/dev/null 2>&1 || true
      raise_win "$S"
      last="Paused"
    fi
  fi

  lock_onboard_geom
  sleep 0.25
done
