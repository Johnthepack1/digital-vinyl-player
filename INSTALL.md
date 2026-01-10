
# Installation Guide

This guide documents **everything required** to install, run, and recover the Digital Vinyl Player exactly as built.

This project is designed to:
- Boot directly into a vinyl-style UI
- Run Spotify in the background
- Be controlled only with physical hardware
- Recover automatically if something goes wrong
- Never require a keyboard, mouse, or SSH after setup

---

## System Overview

This project runs entirely using **systemd user services**.  
No root services are required once the system is installed.

Core components:
- Chromium (Spotify Web Player)
- Pygame-based Vinyl UI
- Arduino Nano for physical controls
- Flask-based Wi-Fi + Spotify setup mode
- Watchdog for long-term reliability

---

## 1. Hardware Requirements

- Raspberry Pi (tested on **Pi 5**)
- Round 1080×1080 touchscreen (X11)
- Arduino Nano
- Physical controls:
  - Needle / rotary input
  - Buttons (play, back, UI switch)
  - Volume potentiometer
- USB audio device or speakers
- Reliable 5V power supply

---

## 2. Raspberry Pi OS

- Raspberry Pi OS **32-bit Desktop**
- X11 / LXDE (Wayland not used)
- Auto-login enabled (recommended)

Update system:
```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```
## Required Packages
```bash
sudo apt install -y \
  chromium-browser \
  python3 python3-pip python3-venv \
  python3-pygame \
  python3-flask \
  python3-serial \
  network-manager \
  nmcli \
  xdotool wmctrl \
  onboard \
  playerctl \
  pipewire wireplumber \
  git curl
```
## Clone Repository
```bash
cd ~
git clone https://github.com/YOUR_USERNAME/digital-vinyl-player.git
cd digital-vinyl-player
```
##Python Dependencies
```bash
pip3 install --user flask pyserial
```
## Audio Initialization
Audio is handled by PipeWire.

```bash
systemctl --user enable --now pipewire wireplumber
```
Default volume is set at boot using a user service.

## Arduino Nano
The Arduino Nano handles:
Needle position
Buttons
Volume input

Firmware communicates with the Pi over serial.

## Confirm serial device:

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```
Update port in:

```bash
nano/nano_control.py
```
## Project Structure
```bash
digital-vinyl-player/
├── ui/                      # Vinyl UI (Pygame)
│   └── vinyl_ui.py
├── nano/                    # Arduino Nano logic
│   └── nano_control.py
├── setup/                   # Wi-Fi + Spotify setup
│   └── app.py               # Flask server
├── bin/                     # All control scripts
│   ├── start_vinyl_ui.sh
│   ├── start_spotify.sh
│   ├── spotify_autoplay.sh
│   ├── setup_mode.sh
│   ├── enter_setup_mode.sh
│   ├── exit_setup_mode.sh
│   └── chromium_mem_watchdog.sh
├── systemd/                 # Reference service files
├── logs/
├── README.md
└── INSTALL.md
```
## systemd User Services (FULL LIST)
All services live in:
```bash
~/.config/systemd/user/
vinyl-ui.service
```
Purpose:
Runs the Pygame vinyl UI and keeps it on top.

```bash
Description=Vinyl UI Overlay
ExecStart=~/bin/start_vinyl_ui.sh
Restart=always
spotify.service
```
Purpose:
Launches Chromium with Spotify Web Player and keeps it running.

```bash

Description=Spotify (Chromium)
ExecStart=~/bin/start_spotify.sh
ExecStartPost=~/bin/spotify_autoplay.sh
Restart=always
nano-control.service
```
Purpose:
Handles all physical controls via Arduino Nano.

```ini
Description=Nano Hardware Controls
ExecStart=python3 ~/digital-vinyl-player/nano/nano_control.py
Restart=always
wifi-setup.service
```
Purpose:
Runs the local Wi-Fi setup web server.

```ini
Description=Local Wi-Fi setup server
ExecStart=python3 ~/setup/app.py
Restart=always
chromium-mem-watchdog.service
```
Purpose:
Monitors Chromium memory usage and restarts Spotify if needed.

```ini
Description=Chromium Memory Watchdog
Type=oneshot
ExecStart=~/bin/chromium_mem_watchdog.sh
chromium-mem-watchdog.timer
```
Purpose:
Runs the watchdog on a schedule.

```ini
OnBootSec=60
OnUnitActiveSec=120
audio-init.service
```
Purpose:
Sets default system volume on boot.

```ini
ExecStart=wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.95
```
## Enable All Services
```bash
systemctl --user daemon-reload
systemctl --user enable --now \
  vinyl-ui.service \
  spotify.service \
  nano-control.service \
  wifi-setup.service \
  chromium-mem-watchdog.timer \
  audio-init.service
```
Check status:

```bash
systemctl --user status vinyl-ui.service spotify.service
```
## Boot Behavior
On power-up:

Audio initializes

Spotify launches in Chromium

Vinyl UI starts and stays on top

Physical controls become active

System runs unattended

## Setup Mode (Wi-Fi + Spotify Login)
Enter setup mode
Hold Back button for 7+ seconds

What happens
Vinyl UI stops

Wi-Fi setup page opens (620×620)

Spotify login window opens (620×620)

On-screen keyboard enabled

Touchscreen only

Exit setup mode
Tap Done

Vinyl UI + Spotify restart automatically

## Reliability Features
Chromium memory watchdog with cooldown

Spotify auto-restarts if it crashes

UI restarts automatically

Designed for long unattended runs

## Recovery Commands
Force setup mode:

```bash
rm -f ~/.vinyl/setup_complete
touch ~/.vinyl/force_setup
reboot
```
Restart UI:

```bash
systemctl --user restart vinyl-ui.service
```
Restart Spotify:

```bash
systemctl --user restart spotify.service
```


Author
Built by John Turner
Engineering student focused on embedded systems, robotics, and hands-on design.
