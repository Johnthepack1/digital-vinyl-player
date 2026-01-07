#!/usr/bin/env bash
set -euo pipefail

# Run inside the active desktop session
export DISPLAY=${DISPLAY:-:0}
export XAUTHORITY=${XAUTHORITY:-/home/$USER/.Xauthority}

URL="https://open.spotify.com"
CACHE_DIR="/tmp/chromium-cache"
mkdir -p "$CACHE_DIR"

# IMPORTANT:
# - --app opens a clean single window (no tabs)
# - exec keeps Chromium as the service process (prevents endless relaunching)
exec chromium \
  --app="$URL" \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --autoplay-policy=no-user-gesture-required \
  --disk-cache-dir="$CACHE_DIR" \
  --user-data-dir="/home/$USER/.config/chromium-spotify" \
  --start-minimized \
  --window-size=900,700 \
  --window-position=20,20
