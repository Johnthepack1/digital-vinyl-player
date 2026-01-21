#!/usr/bin/env bash
set -euo pipefail

# ==========================================================
# spotify_kiosk.sh (vinyl2 / 1080x1080 round screen)
# - Launch Spotify Web in Chromium app mode
# - Keep login persistent (stable profile dir)
# - Snap to your mouse-tuned geometry
# - Set zoom (100/110/125/150 via key presses)
# - Optional: Onboard keyboard auto-show + lock geometry
# ==========================================================

# -------------------------
# EASY TUNING
# -------------------------
URL="https://open.spotify.com/home?facet=music-chip"

# Spotify window (mouse-tuned final)
SPOT_X=80
SPOT_Y=200
SPOT_W=900
SPOT_H=695

# Hide Spotify's top bar by shifting window UP and increasing height.
# Set 0 to disable. Typical: 70–90 at 110% zoom.
HIDE_TOP_PX=0

# Zoom levels supported reliably via key presses:
# 100, 110, 125, 150
ZOOM=110

# On-screen keyboard
START_KEYBOARD=0          # 1 = start onboard, 0 = don't
KEYBOARD_AUTO_SHOW=1      # 1 = pop up only on text fields

# Onboard window (mouse-tuned final)
KB_X=86
KB_Y=564
KB_W=907
KB_H=266

# Persistent Chromium profile (keeps Spotify logged in)
PROFILE_DIR="$HOME/.config/chromium-spotify"
CACHE_DIR="/tmp/chromium-cache"

# -------------------------
# X session env (PuTTY-safe)
# -------------------------
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
export NO_AT_BRIDGE=1

# Don’t launch a second copy if one is already open
if wmctrl -l | grep -q "Spotify"; then
  exit 0
fi

mkdir -p "$PROFILE_DIR" "$CACHE_DIR"

# -------------------------
# Tools check
# -------------------------
command -v wmctrl  >/dev/null 2>&1 || { echo "wmctrl not found. Install: sudo apt install wmctrl"; exit 1; }
command -v xdotool >/dev/null 2>&1 || { echo "xdotool not found. Install: sudo apt install xdotool"; exit 1; }

# -------------------------
# Choose Chromium binary
# -------------------------
CHROME="chromium-browser"
command -v "$CHROME" >/dev/null 2>&1 || CHROME="chromium"

# -------------------------
# Derived geometry (top-bar hide)
# -------------------------
SPOT_Y2=$(( SPOT_Y - HIDE_TOP_PX ))
SPOT_H2=$(( SPOT_H + HIDE_TOP_PX ))
(( SPOT_Y2 < 0 )) && SPOT_Y2=0

# -------------------------
# Helper: find Spotify window id
# -------------------------
find_spotify_win_id() {
  wmctrl -l | awk '/Spotify/ {print $1}' | tail -n 1
}

# -------------------------
# Start Onboard keyboard
# -------------------------
start_keyboard() {
  (( START_KEYBOARD == 1 )) || return 0

  if command -v gsettings >/dev/null 2>&1; then
    if (( KEYBOARD_AUTO_SHOW == 1 )); then
      gsettings set org.onboard auto-show true  >/dev/null 2>&1 || true
      gsettings set org.onboard show-status-icon false >/dev/null 2>&1 || true
    else
      gsettings set org.onboard auto-show false >/dev/null 2>&1 || true
    fi
  fi

  pkill onboard >/dev/null 2>&1 || true
  onboard --hidden >/dev/null 2>&1 & disown || onboard >/dev/null 2>&1 & disown
}

# -------------------------
# Launch Chromium app window
# -------------------------
pkill -f "$CHROME" >/dev/null 2>&1 || true
sleep 0.2

"$CHROME" \
  --new-window \
  --user-data-dir="$PROFILE_DIR" \
  --profile-directory=Default \
  --disk-cache-dir="$CACHE_DIR" \
  --app="$URL" \
  --no-first-run \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --overscroll-history-navigation=0 \
  --autoplay-policy=no-user-gesture-required \
  --window-size="${SPOT_W},${SPOT_H2}" \
  --window-position="0,0" \
  >/dev/null 2>&1 & disown

start_keyboard

# -------------------------
# Wait for Spotify window
# -------------------------
WIN_ID=""
for _ in {1..120}; do
  WIN_ID="$(find_spotify_win_id || true)"
  [[ -n "${WIN_ID:-}" ]] && break
  sleep 0.1
done
[[ -n "${WIN_ID:-}" ]] || exit 0

# -------------------------
# Apply Spotify geometry
# -------------------------
wmctrl -i -r "$WIN_ID" -b remove,maximized_vert,maximized_horz,fullscreen >/dev/null 2>&1 || true
wmctrl -i -r "$WIN_ID" -e "0,${SPOT_X},${SPOT_Y2},${SPOT_W},${SPOT_H2}" >/dev/null 2>&1 || true
wmctrl -i -a "$WIN_ID" >/dev/null 2>&1 || true

# -------------------------
# Set zoom (Ctrl+0 then Ctrl+plus)
# -------------------------
xdotool windowactivate --sync "$WIN_ID" >/dev/null 2>&1 || true
sleep 0.15
xdotool key --clearmodifiers ctrl+0 >/dev/null 2>&1 || true
sleep 0.1

case "$ZOOM" in
  100) : ;;
  110) xdotool key --clearmodifiers ctrl+plus >/dev/null 2>&1 || true ;;
  125) xdotool key --clearmodifiers ctrl+plus ctrl+plus >/dev/null 2>&1 || true ;;
  150) xdotool key --clearmodifiers ctrl+plus ctrl+plus ctrl+plus >/dev/null 2>&1 || true ;;
  *)   : ;;
esac

# -------------------------
# Lock Onboard geometry (only if enabled)
# -------------------------
if (( START_KEYBOARD == 1 )); then
  for _ in {1..80}; do
    wmctrl -l | grep -q "Onboard" && break
    sleep 0.1
  done
  wmctrl -r "Onboard" -b remove,maximized_vert,maximized_horz,fullscreen >/dev/null 2>&1 || true
  wmctrl -r "Onboard" -e "0,${KB_X},${KB_Y},${KB_W},${KB_H}" >/dev/null 2>&1 || true
fi

exit 0
