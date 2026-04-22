#!/usr/bin/env bash
set -euo pipefail

# Ensure we can open the desktop from a service
export DISPLAY=${DISPLAY:-:0}
export XAUTHORITY=${XAUTHORITY:-/home/$USER/.Xauthority}

URL="https://open.spotify.com"

CACHE_DIR="/tmp/chromium-cache"
mkdir -p "$CACHE_DIR"

# IMPORTANT:
# - use --app= for a single clean window
# - use exec so Chromium becomes the service process (no "&")
exec chromium \
  --app="$URL" \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --autoplay-policy=no-user-gesture-required \
  --disk-cache-dir="$CACHE_DIR" \
  --user-data-dir="/home/$USER/.config/chromium-spotify" \
  --window-size=900,700 \
  --window-position=20,20
