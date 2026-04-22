![Digital Vinyl Player](../assets/images/RecordPlayer.png)

# Digital Vinyl Player

This version of the project is a Raspberry Pi-only rebuild of the prototype.

It uses:

- Chromium kiosk for a configured web music provider
- A Python/Pygame vinyl UI for the round display
- An AS5600 over I2C for tonearm position
- A GPIO rotary encoder for volume
- A dedicated GPIO 22 button service for skin changes and 10-second setup mode entry

Old Pico, Nano, and install experiments are still kept under `archive/` so nothing important was lost.

## Active layout

```text
digital-vinyl-player/
├── assets/          # UI images and skins
├── archive/         # old prototype code kept as backup
├── bin/             # startup, kiosk, and calibration scripts
├── docs/            # project notes
├── logs/            # runtime logs
├── src/ui/          # main Pygame UI
└── systemd/user/    # user services to copy into ~/.config/systemd/user
```

## Runtime flow

1. `spotify.service` launches Chromium in app mode for the configured music provider.
2. `vinyl-ui.service` launches `src/ui/vinyl_ui.py` on the round display.
3. `setup-portal.service` serves a local touchscreen setup page for Wi-Fi connection, captive-portal login, and music-provider sign-in.
4. `back-button.service` watches GPIO `22`: short press cycles vinyl skins and a 10-second hold enters or exits setup mode.
5. `ui-focus-watcher.service` swaps between the browser music window and the vinyl UI based on playback state and the setup-mode flag.
6. `vinyl_ui.py` reads the AS5600 over I2C and sends play/pause when the tonearm moves between parked and active positions.
7. `vinyl_ui.py` reads the GPIO rotary encoder and adjusts PipeWire volume.
8. `vinyl_ui.py` watches the shared skin index so external skin changes appear immediately without restarting the UI.

## Hardware notes

- Default rotary encoder pins are BCM `17` and `27`.
- Default back/setup button pin is BCM `22`.
- Default AS5600 address is `0x36` on I2C bus `1`.
- Default parked thresholds are `15` degrees to enter park and `20` degrees to exit park after applying the configured angle offset.

You can change those values with environment variables before launching the UI:

```bash
export VINYL_MUSIC_PROVIDER=spotify
export VINYL_BACK_BUTTON_PIN=22
export VINYL_BACK_BUTTON_HOLD_SEC=10
export VINYL_SETUP_PORTAL_PORT=8787
export VINYL_ANGLE_OFFSET_DEG=0
export VINYL_PARK_ENTER_DEG=15
export VINYL_PARK_EXIT_DEG=20
export VINYL_ROTARY_A=17
export VINYL_ROTARY_B=27
export VINYL_ROTARY_DIRECTION=1
```

Supported provider values:

- `spotify`
- `apple_music`

`apple_music` support uses `music.apple.com` in Chromium. It is workable as a browser-based option, but Spotify remains the safer default until Apple Music has been field-tested on the target hardware.

## Useful test scripts

- `bin/as5600_read.py` prints the live AS5600 angle.
- `bin/gpio_watch_encoder.py` prints rotary encoder pin changes.
- `bin/back_button_service.py` runs the dedicated GPIO 22 short-press / long-press handler.
- `bin/setup_portal.py` runs the local Wi-Fi and Spotify login setup page on `127.0.0.1`.

Those are meant for calibration on the Pi before enabling services.
