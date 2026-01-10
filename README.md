![Digital Vinyl Player](images/IMG_4927.jpeg)

Digital Vinyl Player

This is a Raspberry Pi–based Spotify player designed to look and behave like a physical vinyl record player.

I built this as a personal engineering project and kept refining it until it reached a point where it felt solid, reliable, and a finished product. It boots straight into a custom vinyl-style UI, plays Spotify in the background, and is controlled with real hardware (needle, buttons, volume knob).

This isn’t meant to feel like a computer; it’s meant to feel like a vinyl record player.

What it does

Runs Spotify using Chromium - tried other methods, but this was most reliable

Displays a custom round “vinyl record” UI, which can switch with a press of a button

Uses physical controls via an Arduino Nano

Supports a round touchscreen

Has a built-in Wi-Fi + Spotify login setup mode, so no need for keyboard/mouse or SSH

Automatically recovers if Chromium starts using too much memory

Starts and runs without a keyboard/mouse or phone

Once it’s set up, you can power it on and listen to your favorite music.

How it works

The Pi boots into the graphical session

Spotify starts in the background (Chromium)

The vinyl UI starts and stays on top

Physical controls interact with Spotify

A watchdog monitors Chromium memory and restarts it if needed

Setup mode

Setup mode is only used when Wi-Fi or Spotify login is needed.

Opens a local Wi-Fi setup page

Opens Spotify’s login page

Uses an on-screen keyboard for touch input

Temporarily disables the vinyl UI so setup windows stay visible

Restores normal mode when finished

Setup mode can be triggered by holding the physical back button for 7+ seconds.

Hardware

Raspberry Pi (tested on Pi 5)

Round 1080×1080 touchscreen

Arduino Nano (needle position, buttons, volume)

External USB speaker

Software

Raspberry Pi OS (X11 / LXDE)

Chromium (Spotify Web Player)

Python (UI + hardware control)

Flask (Wi-Fi setup interface)

systemd user services

nmcli for network management

Onboard for on-screen keyboard

Reliability

This project is designed to run unattended.

A systemd watchdog monitors Chromium’s memory usage. If it grows too large for too long, Spotify is restarted automatically with a cooldown to avoid loops. This keeps the system responsive without needing a reboot.

Project structure
digital-vinyl-player/
├── ui/                  # Vinyl UI (Pygame)
├── nano/                # Arduino Nano control logic
├── setup/               # Wi-Fi + Spotify setup UI
├── bin/                 # Startup, setup, watchdog scripts
├── systemd/             # User service files
└── README.md

Why I built this

I'm an old soul, but I also love new technology, and music has always been a big part of my life. I liked the idea of mixing old with new, such as a record player with modern streaming.

I enjoy designing something, building it, then refining it over time. This project gave me a lot of reasons to learn new skills and solve many problems, from hardware and wiring to software, UI behavior, and mostly reliability. It evolved as I tested it, broke it, fixed it, and made it better.

This player is something I actually use every day, and honestly, it’s just cool.

Author

Built by John Turner
Engineering student focused on embedded systems, robotics, and hands-on design.
