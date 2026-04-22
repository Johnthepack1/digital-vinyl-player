#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}"

PROVIDER_RAW="${VINYL_MUSIC_PROVIDER:-spotify}"
PROVIDER="$(printf '%s' "$PROVIDER_RAW" | tr '[:upper:]' '[:lower:]')"
SETUP_MODE_FLAG="${VINYL_SETUP_MODE_FLAG:-$HOME/digital-vinyl-player/runtime/setup_mode.flag}"

case "$PROVIDER" in
  apple|applemusic|apple_music)
    MUSIC_PROVIDER="apple_music"
    WINDOW_PATTERN="(apple music|music\\.apple\\.com)"
    ;;
  *)
    MUSIC_PROVIDER="spotify"
    WINDOW_PATTERN="(spotify|open\\.spotify\\.com)"
    ;;
esac

SPOT_ON_X=80
SPOT_ON_Y=200
SPOT_ON_W=900
SPOT_ON_H=695

SPOT_OFF_X=2500
SPOT_OFF_Y=2500
SPOT_OFF_W=900
SPOT_OFF_H=700

VINYL_ON_X=0
VINYL_ON_Y=0
VINYL_ON_W=1080
VINYL_ON_H=1080

VINYL_OFF_X=2500
VINYL_OFF_Y=2500
VINYL_OFF_W=1
VINYL_OFF_H=1

START_KEYBOARD=1
KEYBOARD_AUTO_SHOW=1

KB_X=86
KB_Y=564
KB_W=907
KB_H=266

VINYL_TITLE="Vinyl UI"
PAUSE_DEBOUNCE_SEC=1.25
PLAYER_REFRESH_SEC=1.0

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >&2
}

wait_for_x() {
  for _ in {1..200}; do
    wmctrl -m >/dev/null 2>&1 && return 0
    sleep 0.1
  done
  return 1
}

find_vinyl_win() {
  wmctrl -l | awk -v m="$VINYL_TITLE" 'index($0,m){print $1}' | tail -n 1
}

find_music_win() {
  local id=""
  id="$(wmctrl -lx | awk 'tolower($0) ~ /vinyl-music-kiosk/ {print $1}' | tail -n 1)"
  [[ -n "$id" ]] && { echo "$id"; return 0; }
  id="$(wmctrl -l | awk -v pat="$WINDOW_PATTERN" 'tolower($0) ~ pat {print $1}' | tail -n 1)"
  [[ -n "$id" ]] && { echo "$id"; return 0; }
  wmctrl -lx | awk -v pat="$WINDOW_PATTERN" 'tolower($0) ~ pat {print $1}' | tail -n 1
}

raise_win() {
  local win="${1:-}"
  [[ -n "$win" ]] || return 0
  wmctrl -i -R "$win" >/dev/null 2>&1 || true
  wmctrl -i -a "$win" >/dev/null 2>&1 || true
}

move_resize() {
  local win="${1:-}" x="$2" y="$3" w="$4" h="$5"
  [[ -n "$win" ]] || return 0
  wmctrl -i -r "$win" -b remove,maximized_vert,maximized_horz,fullscreen >/dev/null 2>&1 || true
  wmctrl -i -r "$win" -e "0,${x},${y},${w},${h}" >/dev/null 2>&1 || true
}

pick_player() {
  playerctl -l 2>/dev/null | grep -i '^chromium\.instance' | head -n 1 && return 0
  playerctl -l 2>/dev/null | grep -Ei '^(chromium|chrome)' | head -n 1 && return 0
  playerctl -l 2>/dev/null | grep -i 'spotify' | head -n 1 && return 0
  return 1
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

show_vinyl_mode() {
  local spotify_win="${1:-}" vinyl_win="${2:-}"
  move_resize "$spotify_win" "$SPOT_OFF_X" "$SPOT_OFF_Y" "$SPOT_OFF_W" "$SPOT_OFF_H"
  [[ -n "$spotify_win" ]] && wmctrl -i -r "$spotify_win" -b add,below >/dev/null 2>&1 || true
  move_resize "$vinyl_win" "$VINYL_ON_X" "$VINYL_ON_Y" "$VINYL_ON_W" "$VINYL_ON_H"
  [[ -n "$vinyl_win" ]] && wmctrl -i -r "$vinyl_win" -b remove,below >/dev/null 2>&1 || true
  [[ -n "$vinyl_win" ]] && wmctrl -i -r "$vinyl_win" -b add,fullscreen >/dev/null 2>&1 || true
  [[ -n "$vinyl_win" ]] && wmctrl -i -r "$vinyl_win" -b add,above >/dev/null 2>&1 || true
  raise_win "$vinyl_win"
  lock_onboard_geom
}

show_kiosk_mode() {
  local spotify_win="${1:-}" vinyl_win="${2:-}"
  move_resize "$vinyl_win" "$VINYL_OFF_X" "$VINYL_OFF_Y" "$VINYL_OFF_W" "$VINYL_OFF_H"
  [[ -n "$vinyl_win" ]] && wmctrl -i -r "$vinyl_win" -b add,below >/dev/null 2>&1 || true
  move_resize "$spotify_win" "$SPOT_ON_X" "$SPOT_ON_Y" "$SPOT_ON_W" "$SPOT_ON_H"
  [[ -n "$spotify_win" ]] && wmctrl -i -r "$spotify_win" -b remove,below >/dev/null 2>&1 || true
  [[ -n "$vinyl_win" ]] && wmctrl -i -r "$vinyl_win" -b remove,above >/dev/null 2>&1 || true
  raise_win "$spotify_win"
  lock_onboard_geom
}

until wait_for_x; do
  sleep 1
done

start_keyboard

PLAYER="$(pick_player || true)"
last_player_refresh=0
screen_mode=""
last_spotify_state=""
paused_since=""

while true; do
  now="$(date +%s.%N)"
  force_setup="0"
  if [[ -f "$SETUP_MODE_FLAG" ]]; then
    force_setup="1"
  fi

  spotify_win="$(find_music_win || true)"
  vinyl_win="$(find_vinyl_win || true)"

  if [[ "$force_setup" == "1" ]]; then
    paused_since="$now"
    if [[ "$screen_mode" != "KIOSK" ]]; then
      show_kiosk_mode "$spotify_win" "$vinyl_win"
      screen_mode="KIOSK"
      log "screen=KIOSK setup=1"
    else
      raise_win "$spotify_win"
      lock_onboard_geom
    fi
    sleep 0.25
    continue
  fi

  refresh_player="$(python3 - <<PY 2>/dev/null || echo 1
last=float("${last_player_refresh}")
tn=float("${now}")
print(1 if (tn-last) >= float("${PLAYER_REFRESH_SEC}") else 0)
PY
)"

  if [[ "$refresh_player" == "1" || -z "${PLAYER:-}" ]]; then
    PLAYER="$(pick_player || true)"
    last_player_refresh="$now"
  fi

  if [[ -z "${PLAYER:-}" ]]; then
    lock_onboard_geom
    sleep 0.25
    continue
  fi

  status="$(playerctl -p "$PLAYER" status 2>/dev/null || true)"
  if [[ -z "${status:-}" ]]; then
    PLAYER=""
    sleep 0.25
    continue
  fi

  spotify_state="PAUSED"
  desired_screen_mode="KIOSK"
  if [[ "$status" == "Playing" ]]; then
    spotify_state="PLAYING"
    desired_screen_mode="VINYL"
  fi

  if [[ "$spotify_state" != "$last_spotify_state" ]]; then
    log "spotify=$spotify_state desired_screen=$desired_screen_mode"
    last_spotify_state="$spotify_state"
  fi

  if [[ "$desired_screen_mode" == "VINYL" ]]; then
    paused_since=""
    if [[ "$screen_mode" != "VINYL" ]]; then
      show_vinyl_mode "$spotify_win" "$vinyl_win"
      screen_mode="VINYL"
      log "screen=VINYL"
    fi
  else
    if [[ -z "${paused_since:-}" ]]; then
      paused_since="$now"
    fi

    ok="$(python3 - <<PY 2>/dev/null || echo 0
t0=float("${paused_since}")
tn=float("${now}")
print(1 if (tn-t0) >= float("${PAUSE_DEBOUNCE_SEC}") else 0)
PY
)"

    if [[ "$ok" == "1" && "$screen_mode" != "KIOSK" ]]; then
      show_kiosk_mode "$spotify_win" "$vinyl_win"
      screen_mode="KIOSK"
      log "screen=KIOSK"
    fi
  fi

  lock_onboard_geom
  sleep 0.25
done
