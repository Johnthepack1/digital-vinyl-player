# Installation Guide

This document explains how to set up the Digital Vinyl Player from a fresh Raspberry Pi OS install.

This project is designed to run **headless after setup** — no keyboard, mouse, or SSH required once it’s configured. Setup mode handles Wi-Fi and Spotify login using the touchscreen.

---

## 1. Hardware Requirements

- Raspberry Pi (tested on **Raspberry Pi 5**)
- Round 1080×1080 touchscreen (X11 compatible)
- Arduino Nano
- USB speaker or audio output device
- Physical controls:
  - Needle / rotary input
  - Buttons (play, back, UI switch, etc.)
  - Volume knob (potentiometer)
- Stable 5V power supply

---

## 2. Flash Raspberry Pi OS

1. Download **Raspberry Pi OS (32-bit)**  
   (Desktop version required – uses X11)

2. Flash using Raspberry Pi Imager  
   - Enable SSH **optional**
   - Set username (examples below assume `vinyl2`)
   - Enable Wi-Fi **optional** (setup mode can do this later)

3. Boot the Pi and complete first-time setup

---

## 3. System Preparation

Update the system:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
````

Install required packages:

```bash
sudo apt install -y \
  chromium-browser \
  python3 python3-pip python3-venv \
  python3-pygame \
  python3-flask \
  python3-serial \
  nmcli network-manager \
  xdotool wmctrl \
  onboard \
  playerctl \
  pipewire wireplumber \
  git curl
```

---

## 4. Clone the Repository

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/digital-vinyl-player.git
cd digital-vinyl-player
```

(Replace `YOUR_USERNAME` with your GitHub username.)

---

## 5. Python Dependencies

Install Python dependencies:

```bash
pip3 install --user flask pyserial
```

---

## 6. Audio Setup

Ensure PipeWire is running and set default volume:

```bash
systemctl --user enable --now pipewire wireplumber
wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.95
```

(Optional) Test audio:

```bash
speaker-test -c 2
```

---

## 7. Arduino Nano Setup

1. Flash the Arduino Nano with the control firmware
   (needle position, buttons, volume)

2. Confirm the Nano appears as a serial device:

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

3. Update the serial port in:

```
nano/nano_control.py
```

---

## 8. systemd User Services

This project relies on **systemd user services** (not root services).

Enable all services:

```bash
systemctl --user daemon-reload

systemctl --user enable --now \
  vinyl-ui.service \
  spotify.service \
  wifi-setup.service \
  nano-control.service \
  chromium-mem-watchdog.timer \
  audio-init.service
```

Check status:

```bash
systemctl --user status vinyl-ui.service spotify.service
```

---

## 9. First Boot Behavior

On boot:

* Spotify launches in Chromium (background)
* Vinyl UI launches and stays on top
* Hardware controls are active
* No keyboard or mouse is required

---

## 10. Setup Mode (Wi-Fi + Spotify Login)

Setup mode is used **only when needed**.

### Enter setup mode

* Hold the **physical back button** for **7+ seconds**

Setup mode will:

* Stop the vinyl UI
* Open a local Wi-Fi setup page
* Open Spotify login
* Show an on-screen keyboard
* Use 620×620 windows centered on the round screen

### Exit setup mode

* Tap **Done** on the Wi-Fi setup page
  OR
* Reboot after setup completes

Normal mode resumes automatically.

---

## 11. Chromium Memory Watchdog

Chromium is monitored for memory usage.

* If memory stays too high for too long:

  * Spotify is restarted automatically
* Cooldown prevents restart loops
* No user interaction required

Settings are adjustable in:

```
bin/chromium_mem_watchdog.sh
```

---

## 12. Common Issues

### Spotify won’t play after reboot

* Wait ~10 seconds after boot
* Autoplay simulates a user gesture
* If needed:

```bash
systemctl --user restart spotify.service
```

### Vinyl UI not visible

```bash
systemctl --user restart vinyl-ui.service
```

### Setup mode not appearing

```bash
rm -f ~/.vinyl/setup_complete
touch ~/.vinyl/force_setup
reboot
```

---

## 13. Designed Behavior

* No keyboard or mouse required after setup
* Safe to power off normally
* Designed to recover automatically
* Intended to run unattended

---

## Notes

This project evolved through real use, testing, crashes, and fixes.
It’s designed to feel intentional — not like a computer in disguise.

If you’re installing this, expect to tweak hardware and wiring based on your build. The software is flexible, but the physical side matters.

---

## Author

Built by **John Turner**
Engineering student focused on embedded systems, robotics, and hands-on design.


Just say what’s next.
```
