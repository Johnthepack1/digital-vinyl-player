#!/usr/bin/env bash
set -euo pipefail

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}"

CMD="${1:-play-pause}"
PROVIDER_RAW="${VINYL_MUSIC_PROVIDER:-spotify}"
PROVIDER="$(printf '%s' "$PROVIDER_RAW" | tr '[:upper:]' '[:lower:]')"

case "$PROVIDER" in
  apple|applemusic|apple_music)
    WINDOW_PATTERN="(apple music|music\\.apple\\.com)"
    ;;
  *)
    WINDOW_PATTERN="(spotify|open\\.spotify\\.com)"
    ;;
esac

pick_player() {
  playerctl -l 2>/dev/null | grep -i '^chromium\.instance' | head -n 1 && return 0
  playerctl -l 2>/dev/null | grep -Ei '^(chromium|chrome)' | head -n 1 && return 0
  playerctl -l 2>/dev/null | grep -i 'spotify' | head -n 1 && return 0
  return 1
}

find_music_win() {
  local id=""
  id="$(wmctrl -lx | awk 'tolower($0) ~ /vinyl-music-kiosk/ {print $1}' | tail -n 1 || true)"
  [[ -n "${id:-}" ]] && { echo "$id"; return 0; }
  id="$(wmctrl -l | awk -v pat="$WINDOW_PATTERN" 'tolower($0) ~ pat {print $1}' | tail -n 1 || true)"
  [[ -n "${id:-}" ]] && { echo "$id"; return 0; }
  wmctrl -lx | awk -v pat="$WINDOW_PATTERN" 'tolower($0) ~ pat {print $1}' | tail -n 1 || true
}

focus_music_window() {
  local win_id="${1:-}"
  [[ -n "${win_id:-}" ]] || return 1

  wmctrl -i -a "$win_id" >/dev/null 2>&1 || true
  sleep 0.05
  xdotool windowactivate --sync "$win_id" >/dev/null 2>&1 || true
  sleep 0.05
  return 0
}

case "$CMD" in
  next|previous|pause|play|play-pause)
    PLAYER="$(pick_player || true)"
    if [[ -n "${PLAYER:-}" ]]; then
      playerctl -p "$PLAYER" "$CMD" >/dev/null 2>&1 || true
      sleep 0.10

      STATUS="$(playerctl -p "$PLAYER" status 2>/dev/null || true)"
      if [[ "$CMD" == "pause" ]]; then
        exit 0
      fi
      if [[ "$STATUS" == "Playing" ]]; then
        exit 0
      fi
    fi
    ;;
esac

WIN_ID="$(find_music_win || true)"
focus_music_window "${WIN_ID:-}" || true
wmctrl -a "Spotify" 2>/dev/null || true
wmctrl -a "Spotify – Web Player" 2>/dev/null || true
wmctrl -a "Spotify - Web Player" 2>/dev/null || true
wmctrl -a "Apple Music" 2>/dev/null || true
wmctrl -a "Chromium" 2>/dev/null || true
sleep 0.10

case "$CMD" in
  next) xdotool key XF86AudioNext >/dev/null 2>&1 || true ;;
  previous) xdotool key XF86AudioPrev >/dev/null 2>&1 || true ;;
  pause) xdotool key XF86AudioPause >/dev/null 2>&1 || xdotool key space >/dev/null 2>&1 || true ;;
  play) xdotool key XF86AudioPlay >/dev/null 2>&1 || xdotool key space >/dev/null 2>&1 || true ;;
  browser-back)
    if [[ -n "${WIN_ID:-}" ]]; then
      xdotool key --window "$WIN_ID" --clearmodifiers Alt_L+Left >/dev/null 2>&1 \
        || xdotool key --window "$WIN_ID" --clearmodifiers XF86Back >/dev/null 2>&1 \
        || true
    else
      xdotool key --clearmodifiers Alt_L+Left >/dev/null 2>&1 \
        || xdotool key --clearmodifiers XF86Back >/dev/null 2>&1 \
        || true
    fi
    ;;
  *) xdotool key space >/dev/null 2>&1 || true ;;
esac
