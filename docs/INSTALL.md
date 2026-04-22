# Pi-Only Install

These steps assume Raspberry Pi OS Desktop on a Raspberry Pi 5 with X11 and auto-login enabled.

## 1. Install system packages

```bash
sudo apt update
sudo apt install -y \
  chromium \
  i2c-tools \
  onboard \
  playerctl \
  python3-lgpio \
  python3-full \
  python3-venv \
  wmctrl \
  xdotool \
  pipewire pipewire-pulse wireplumber
```

## 2. Enable I2C and hardware access

```bash
sudo raspi-config nonint do_i2c 0
sudo usermod -aG gpio,i2c "$USER"
```

Log out and back in after changing groups.

## 3. Create the virtual environment

```bash
cd ~/digital-vinyl-player
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Verify the hardware

Check that the AS5600 appears on I2C:

```bash
i2cdetect -y 1
./venv/bin/python bin/as5600_read.py
```

Check the rotary encoder pins:

```bash
./venv/bin/python bin/gpio_watch_encoder.py
```

## 5. Test the UI manually

```bash
source venv/bin/activate
python src/ui/vinyl_ui.py
```

Useful environment overrides while calibrating:

```bash
export VINYL_MUSIC_PROVIDER=spotify
export VINYL_BACK_BUTTON_PIN=22
export VINYL_BACK_BUTTON_HOLD_SEC=10
export VINYL_SETUP_PORTAL_PORT=8787
export VINYL_ROTARY_A=17
export VINYL_ROTARY_B=27
export VINYL_ROTARY_DIRECTION=1
export VINYL_ANGLE_OFFSET_DEG=0
export VINYL_PARK_ENTER_DEG=15
export VINYL_PARK_EXIT_DEG=20
```

For the user services, you can also place those values in `~/digital-vinyl-player/.env`.

You can also test the button handler on its own:

```bash
source venv/bin/activate
python bin/back_button_service.py
```

You can also test the local setup portal:

```bash
source venv/bin/activate
python bin/setup_portal.py
xdg-open http://127.0.0.1:8787/
```

## 6. Install the user services

```bash
mkdir -p ~/.config/systemd/user
cp systemd/user/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now \
  audio-init.service \
  setup-portal.service \
  spotify.service \
  back-button.service \
  vinyl-ui.service \
  ui-focus-watcher.service
```

## 7. Service checks

```bash
systemctl --user status setup-portal.service
systemctl --user status spotify.service
systemctl --user status back-button.service
systemctl --user status vinyl-ui.service
systemctl --user status ui-focus-watcher.service
journalctl --user -u spotify.service -f
```

Runtime logs are also written to `logs/` inside the repo.
