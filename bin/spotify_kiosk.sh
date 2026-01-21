#!/usr/bin/env bash
set -euo pipefail

# ==========================================================
# spotify_kiosk.sh (vinyl2 / 1080x1080 round screen)
# - Launch Spotify Web in Chromium app mode (windowed)
# - Sets zoom (100/110/125/150)
# - Snaps Spotify window to fixed geometry OR parks off-screen
# - Optional top-bar hide by shifting window up
# - Starts Onboard keyboard (auto-show) + locks its geometry
#
# NOTE: Do NOT "disown" chromium. We wait on it so systemd
#       keeps the service alive.
# ==========================================================

# -------------------------
# EASY TUNING
# -------------------------
URL="https://open.spotify.com/home?facet=music-chip"

# Spotify window geometry (visible)
SPOT_X=80
SPOT_Y=200
SPOT_W=900
SPOT_H=695

# Hide Spotify's top bar by shifting window UP and increasing height.
HIDE_TOP_PX=0   # 0 disables; try 70–90 at 110% zoom

# Zoom levels via Ctrl+0 then Ctrl++
ZOOM=110        # 100, 110, 125, 150

# Park Spotify off-screen (so Vinyl UI can cover it)
PARK_OFFSCREEN=0   # 1 = move to OFF_X/OFF_Y
OFF_X=2500
OFF_Y=2500

# On-screen keyboard (Onboard)
START_KEYBOARD=1        # 1 = start onboard, 0 = don't
KEYBOARD_AUTO_SHOW=1    # 1 = show only on text fields

# Onboard window geometry (mouse tuned)
KB_X=86
KB_Y=564
KB_W=907
KB_H=266

# -------------------------
# X session env (SSH-safe)
# -------------------------
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

# -------------------------
# Tools check
# -------------------------
command -v wmctrl  >/dev/null 2>&1 || { echo "wmctrl not found. Install: sudo apt install wmctrl"; exit 1; }
command -v xdotool >/dev/null 2>&1 || { echo "xdotool not found. Install: sudo apt install xdotool"; exit 1; }

# -------------------------
# Choose Chromium binary
# -------------------------
CHROME=""
for c in chromium chromium-browser chromium-launcher; do
  if command -v "$c" >/dev/null 2>&1; then
    CHROME="$c"
    break
  fi
done
if [ -z "$CHROME" ]; then
  echo "ERROR: No chromium binary found (chromium/chromium-browser/chromium-launcher)" >&2
  exit 127
fi

# -------------------------
# Derived geometry (top-bar hide)
# -------------------------
SPOT_Y2=$(( SPOT_Y - HIDE_TOP_PX ))
SPOT_H2=$(( SPOT_H + HIDE_TOP_PX ))
(( SPOT_Y2 < 0 )) && SPOT_Y2=0

# -------------------------
# Find Spotify window id
# -------------------------
find_spotify_win_id() {
  # Prefer wmctrl -lx (class list): match chromium + spotify
  local id=""
  id="$(wmctrl -lx | awk 'tolower($0) ~ /chromium/ && tolower($0) ~ /spotify/ {print $1}' | tail -n 1 || true)"
  if [[ -n "${id:-}" ]]; then
    echo "$id"
    return 0
  fi

  # Fallback: window title
  wmctrl -l | awk 'tolower($0) ~ /spotify|open\.spotify/ {print $1}' | tail -n 1
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
  else
    apply_geometry "$win" "$SPOT_X" "$SPOT_Y2" "$SPOT_W" "$SPOT_H2"
  fi
}

set_zoom() {
  local win="$1"
  xdotool windowactivate --sync "$win" >/dev/null 2>&1 || true
  sleep 0.15
  xdotool key --clearmodifiers ctrl+0 >/dev/null 2>&1 || true
  sleep 0.12

  case "$ZOOM" in
    100) : ;;
    110) xdotool key --clearmodifiers ctrl+plus >/dev/null 2>&1 || true ;;
    125) xdotool key --clearmodifiers ctrl+plus ctrl+plus >/dev/null 2>&1 || true ;;
    150) xdotool key --clearmodifiers ctrl+plus ctrl+plus ctrl+plus >/dev/null 2>&1 || true ;;
    *)   : ;;
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

  # lock geometry
  sleep 0.6
  wmctrl -r "Onboard" -b remove,maximized_vert,maximized_horz,fullscreen >/dev/null 2>&1 || true
  wmctrl -r "Onboard" -e "0,${KB_X},${KB_Y},${KB_W},${KB_H}" >/dev/null 2>&1 || true
}

# -------------------------
# Clean old kiosk instance (optional)
# -------------------------
pkill -f "$CHROME.*spotify-kiosk-chromium" >/dev/null 2>&1 || true
sleep 0.2

# -------------------------
# Launch Chromium (background) then WAIT (systemd stays alive)
# -------------------------
"$CHROME" \
  --new-window \
  --app="$URL" \
  --no-first-run \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=TranslateUI \
  --overscroll-history-navigation=0 \
  --autoplay-policy=no-user-gesture-required \
  --user-data-dir="$HOME/.config/spotify-kiosk-chromium" \
  --window-size="${SPOT_W},${SPOT_H2}" \
  --window-position="0,0" \
  >/dev/null 2>&1 &
CHROME_PID="$!"

# Wait for window, then position + zoom + keyboard
WIN_ID=""
for _ in {1..140}; do
  WIN_ID="$(find_spotify_win_id || true)"
  [[ -n "${WIN_ID:-}" ]] && break
  sleep 0.1
done

if [[ -n "${WIN_ID:-}" ]]; then
  park_or_show_spotify "$WIN_ID"
  set_zoom "$WIN_ID"
  start_onboard
fi

wait "$CHROME_PID"
