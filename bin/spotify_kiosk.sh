#!/usr/bin/env bash
set -euo pipefail

# Pick a chromium binary that exists on Debian
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

# If you're using X11/LXDE, these help systemd launches
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

# Spotify web player
URL="https://open.spotify.com/"

# NOTE: DO NOT put '&' at the end. We want systemd to track chromium.
exec "$CHROME" \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=TranslateUI \
  --autoplay-policy=no-user-gesture-required \
  --user-data-dir="$HOME/.config/spotify-kiosk-chromium" \
  "$URL"
