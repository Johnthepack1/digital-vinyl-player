# Digital Vinyl Player (Spotify Web + Overlay)

This repo contains the **foundation setup** for a Raspberry Pi 5 Spotify “vinyl player” build:
- Spotify runs in Chromium (not fullscreen)
- Chromium is started automatically at boot using a **systemd user service**
- Audio routes to USB speakers via PipeWire (default sink)

## What’s included (so far)
- `install/start_spotify.sh` — launches Chromium to open Spotify Web Player
- `install/spotify.service` — systemd user service to auto-start Spotify on boot

> Note: This build intentionally avoids an `app/` folder. Installed scripts live in `~/bin`.

---

## Requirements
- Raspberry Pi OS (Bookworm) with desktop
- Chromium installed (`chromium`)
- X11 recommended if you plan to use `wmctrl` to keep Spotify behind the overlay UI

Packages:
```bash
sudo apt update
sudo apt install -y chromium wmctrl
