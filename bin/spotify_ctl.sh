#!/usr/bin/env bash
set -euo pipefail

cmd="${1:-}"
if [[ "$cmd" != "play" && "$cmd" != "pause" && "$cmd" != "play-pause" && "$cmd" != "next" && "$cmd" != "previous" ]]; then
  echo "Usage: $0 play|pause|play-pause|next|previous" >&2
  exit 2
fi

exec "$HOME/digital-vinyl-player/bin/spotify_cmd.sh" "$cmd"
