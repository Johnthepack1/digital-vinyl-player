#!/usr/bin/env bash
set -euo pipefail

SPOT_X=80
SPOT_Y=200
SPOT_W=900
SPOT_H=695

HIDE_TOP_PX=0
ZOOM=110

PARK_OFFSCREEN=0
OFF_X=2500
OFF_Y=2500

START_KEYBOARD=1
KEYBOARD_AUTO_SHOW=1

KB_X=86
KB_Y=564
KB_W=907
KB_H=266

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

PROVIDER_RAW="${VINYL_MUSIC_PROVIDER:-spotify}"
PROVIDER="$(printf '%s' "$PROVIDER_RAW" | tr '[:upper:]' '[:lower:]')"
SETUP_MODE_FLAG="${VINYL_SETUP_MODE_FLAG:-$HOME/digital-vinyl-player/runtime/setup_mode.flag}"
SETUP_PORTAL_PORT="${VINYL_SETUP_PORTAL_PORT:-8787}"
WINDOW_CLASS="vinyl-music-kiosk"

case "$PROVIDER" in
  apple|applemusic|apple_music)
    MUSIC_PROVIDER="apple_music"
    URL="https://music.apple.com/"
    LOGIN_URL="https://music.apple.com/"
    PROFILE_DIR="$HOME/.config/apple-music-kiosk-chromium"
    WINDOW_PATTERN="(apple music|music\\.apple\\.com)"
    ;;
  *)
    MUSIC_PROVIDER="spotify"
    URL="https://open.spotify.com/home?facet=music-chip"
    LOGIN_URL="https://accounts.spotify.com/en/login?continue=https%3A%2F%2Fopen.spotify.com%2F"
    PROFILE_DIR="$HOME/.config/spotify-kiosk-chromium"
    WINDOW_PATTERN="(spotify|open\\.spotify\\.com)"
    ;;
esac

SETUP_PORTAL_URL="http://127.0.0.1:${SETUP_PORTAL_PORT}/"
SETUP_MODE=0
if [[ -f "$SETUP_MODE_FLAG" ]]; then
  SETUP_MODE=1
fi

command -v wmctrl >/dev/null 2>&1 || { echo "wmctrl not found. Install: sudo apt install wmctrl"; exit 1; }
command -v xdotool >/dev/null 2>&1 || { echo "xdotool not found. Install: sudo apt install xdotool"; exit 1; }

CHROME=""
for candidate in chromium chromium-browser chromium-launcher; do
  if command -v "$candidate" >/dev/null 2>&1; then
    CHROME="$candidate"
    break
  fi
done

if [[ -z "$CHROME" ]]; then
  echo "ERROR: No Chromium binary found." >&2
  exit 127
fi

SPOT_Y2=$((SPOT_Y - HIDE_TOP_PX))
SPOT_H2=$((SPOT_H + HIDE_TOP_PX))
(( SPOT_Y2 < 0 )) && SPOT_Y2=0

find_music_win_id() {
  local id=""
  id="$(wmctrl -lx | awk 'tolower($0) ~ /vinyl-music-kiosk/ {print $1}' | tail -n 1 || true)"
  if [[ -n "${id:-}" ]]; then
    echo "$id"
    return 0
  fi

  id="$(wmctrl -lx | awk -v pat="$WINDOW_PATTERN" 'tolower($0) ~ /chromium/ && tolower($0) ~ pat {print $1}' | tail -n 1 || true)"
  if [[ -n "${id:-}" ]]; then
    echo "$id"
    return 0
  fi

  wmctrl -l | awk -v pat="$WINDOW_PATTERN" 'tolower($0) ~ pat {print $1}' | tail -n 1
}

apply_geometry() {
  local win="$1" x="$2" y="$3" w="$4" h="$5"
  wmctrl -i -r "$win" -b remove,maximized_vert,maximized_horz,fullscreen >/dev/null 2>&1 || true
  wmctrl -i -r "$win" -e "0,${x},${y},${w},${h}" >/dev/null 2>&1 || true
}

park_or_show_spotify() {
  local win="$1"
  if (( PARK_OFFSCREEN == 1 )); then
    apply_geometry "$win" "$OFF_X" "$OFF_Y" "$SPOT_W" "$SPOT_H2"
    return
  fi

  apply_geometry "$win" "$SPOT_X" "$SPOT_Y2" "$SPOT_W" "$SPOT_H2"
}

set_zoom() {
  local win="$1"
  xdotool windowactivate --sync "$win" >/dev/null 2>&1 || true
  sleep 0.15
  xdotool key --clearmodifiers ctrl+0 >/dev/null 2>&1 || true
  sleep 0.12

  case "$ZOOM" in
    100) ;;
    110) xdotool key --clearmodifiers ctrl+plus >/dev/null 2>&1 || true ;;
    125) xdotool key --clearmodifiers ctrl+plus ctrl+plus >/dev/null 2>&1 || true ;;
    150) xdotool key --clearmodifiers ctrl+plus ctrl+plus ctrl+plus >/dev/null 2>&1 || true ;;
  esac
}

start_onboard() {
  (( START_KEYBOARD == 1 )) || return 0

  if command -v gsettings >/dev/null 2>&1; then
    if (( KEYBOARD_AUTO_SHOW == 1 )); then
      gsettings set org.onboard auto-show true >/dev/null 2>&1 || true
      gsettings set org.onboard show-status-icon false >/dev/null 2>&1 || true
    else
      gsettings set org.onboard auto-show false >/dev/null 2>&1 || true
    fi
  fi

  if ! pgrep -x onboard >/dev/null 2>&1; then
    onboard --hidden >/dev/null 2>&1 &
  fi

  sleep 0.6
  wmctrl -r "Onboard" -b remove,maximized_vert,maximized_horz,fullscreen >/dev/null 2>&1 || true
  wmctrl -r "Onboard" -e "0,${KB_X},${KB_Y},${KB_W},${KB_H}" >/dev/null 2>&1 || true
}

pkill -f "$PROFILE_DIR" >/dev/null 2>&1 || true
sleep 0.2

COMMON_ARGS=(
  --new-window
  --class="$WINDOW_CLASS"
  --no-first-run
  --disable-infobars
  --disable-session-crashed-bubble
  --disable-features=TranslateUI
  --overscroll-history-navigation=0
  --autoplay-policy=no-user-gesture-required
  --user-data-dir="$PROFILE_DIR"
  --window-size="${SPOT_W},${SPOT_H2}"
  --window-position="0,0"
)

if (( SETUP_MODE == 1 )); then
  "$CHROME" \
    "${COMMON_ARGS[@]}" \
    "$SETUP_PORTAL_URL" \
    "$LOGIN_URL" \
    >/dev/null 2>&1 &
else
  "$CHROME" \
    "${COMMON_ARGS[@]}" \
    --app="$URL" \
    >/dev/null 2>&1 &
fi
CHROME_PID="$!"

WIN_ID=""
for _ in {1..140}; do
  WIN_ID="$(find_music_win_id || true)"
  [[ -n "${WIN_ID:-}" ]] && break
  sleep 0.1
done

if [[ -n "${WIN_ID:-}" ]]; then
  park_or_show_spotify "$WIN_ID"
  set_zoom "$WIN_ID"
  start_onboard
fi

wait "$CHROME_PID"
