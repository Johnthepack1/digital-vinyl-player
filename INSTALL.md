# 📀 Digital Vinyl Spotify Player  
## Full Installation Guide

This guide explains how to build and configure the **Digital Vinyl Spotify Player** from a fresh Raspberry Pi OS installation to a fully working, auto-starting system with physical controls.

This project uses **Spotify Web Player in Chromium**, not librespot, for maximum stability.

---

## 1. Hardware Requirements

### Core Components
- Raspberry Pi 5
- Official Raspberry Pi 5 Active Cooler
- microSD card (32 GB or larger recommended)
- HDMI touchscreen display (USB touch input)
- USB speakers or USB DAC

### Physical Controls
- Arduino Nano (or compatible)
- Potentiometer for volume control
- Needle / tonearm sensor  
  (potentiometer, microswitch, or Hall sensor)
- USB cable (Nano → Pi)

---

## 2. Flash Raspberry Pi OS

1. Download **Raspberry Pi Imager**
2. Select:
   - **Raspberry Pi OS (64-bit) with desktop**
3. Open ⚙️ **Advanced Options**
   - Enable SSH
   - Enable auto-login
   - Configure Wi-Fi
   - Set hostname (example: `vinyl`)
4. Flash the SD card and boot the Pi

---

## 3. First Boot Update

Open a terminal on the Pi and run:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot


After reboot, confirm the desktop loads normally.

4. Install Required Packages
sudo apt install -y \
chromium \
playerctl \
python3-pygame \
wmctrl \
unclutter \
pipewire \
wireplumber \
git

What these do

Chromium → Spotify Web Player

playerctl → playback control + metadata

pygame → Vinyl UI

wmctrl → window focus control

PipeWire / WirePlumber → audio routing

5. Clone the Project Repository
cd ~
git clone https://github.com/Johnthepack1/digital-vinyl-player.git
cd digital-vinyl-player

6. Verify Project Structure

You should now have:

digital-vinyl-player/
├── ui/
│   ├── vinyl_ui.py
│   └── ui_assets/
│       ├── vinyl.png
│       ├── play.png
│       ├── pause.png
│       ├── next.png
│       └── back.png
├── nano/
│   └── nano_control.py
├── bin/
│   ├── start_spotify.sh
│   ├── spotify_cmd.sh
│   └── start_vinyl_ui.sh
├── services/
│   ├── spotify.service
│   ├── vinyl-ui.service
│   ├── nano-control.service
│   ├── audio-init.service
│   └── spotify-volume-init.service
├── images/
└── README.md


If files are missing, stop and fix before continuing.

7. Install Helper Scripts

Make scripts executable:

chmod +x bin/*.sh


(Optional but recommended):

mkdir -p ~/bin
cp bin/*.sh ~/bin/

8. Install systemd User Services

Copy service files:

mkdir -p ~/.config/systemd/user
cp services/*.service ~/.config/systemd/user/


Reload systemd:

systemctl --user daemon-reload


Enable services:

systemctl --user enable spotify.service
systemctl --user enable vinyl-ui.service
systemctl --user enable nano-control.service
systemctl --user enable audio-init.service
systemctl --user enable spotify-volume-init.service

9. First Spotify Login (One-Time)

Start Spotify manually once:

systemctl --user start spotify.service


Chromium will open.

Log into Spotify

Play any song once

Confirm audio plays through USB speakers

Spotify credentials are now cached locally.

10. Start the Vinyl UI
systemctl --user start vinyl-ui.service


You should see:

Vinyl UI overlay

Album artwork

Track info

Touch controls

11. Enable Nano Hardware Controls

Plug in the Arduino Nano via USB.

Check device:

ls /dev/ttyUSB*


Confirm service:

systemctl --user status nano-control.service

Expected Behavior

Volume knob controls Spotify stream volume

Needle movement triggers play / pause

No phone required after setup

12. Audio Verification

Check PipeWire routing:

wpctl status


Set system volume once (recommended):

wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.95


From this point on:

System volume stays fixed

Physical knob controls Spotify only

13. Auto-Start Verification

Reboot:

sudo reboot


On boot:

Desktop loads

Spotify starts automatically

Vinyl UI appears on top

Needle control works immediately

14. Thermal & Performance Tuning (Recommended)
Reduce UI load

Edit:

nano ui/vinyl_ui.py


Set:

FPS = 30


Restart UI:

systemctl --user restart vinyl-ui.service

Quiet fan curve

Edit:

sudo nano /boot/firmware/config.txt


Add:

[all]
dtparam=fan_temp0=65
dtparam=fan_temp0_hyst=6


Reboot.

15. Troubleshooting
Vinyl UI disappears
systemctl --user restart vinyl-ui.service

Spotify not responding
systemctl --user restart spotify.service

Nano not detected
groups


Ensure user is in dialout.

View logs
journalctl --user -u vinyl-ui.service -f
journalctl --user -u nano-control.service -f

16. Final Result

You now have:

A self-contained Spotify vinyl player

Physical controls

Auto-start on boot

No cloud APIs

No phone dependency

Stable, reproducible setup
