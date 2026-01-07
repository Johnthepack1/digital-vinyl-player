#!/usr/bin/env python3
import time
import re
import shutil
import subprocess
import serial

# =========================
# CONFIG (product-safe defaults)
# =========================
SERIAL_PORT = "/dev/ttyUSB0"   # confirmed CH341 on your Pi
BAUD = 115200                  # keep since volume works

# Debounce times (seconds)
NEEDLE_DEBOUNCE = 0.35

# Volume behavior (Chromium stream volume)
VOL_DEADBAND = 1               # ignore tiny % changes
VOL_MIN = 0.00                 # 0%
VOL_MAX = 1.50                 # allow up to 150% (PipeWire supports >100)

STREAM_REFRESH_SEC = 3.0       # rescan wpctl status for Chromium stream

# Use the smart command wrapper (playerctl first, xdotool fallback)
SPOTIFY_CMD = "/home/vinyl2/bin/spotify_cmd.sh"

DEBUG_PRINT_RX = False         # set True if you want RX: logs
# =========================

_last_stream_id = None
_last_stream_id_t = 0.0

_last_needle_action = 0.0
_last_volume = None


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def sh(cmd):
    """Run command quietly; never crash the service."""
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except Exception:
        pass


def sh_out(cmd):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return ""


def clamp(n, lo, hi):
    return lo if n < lo else hi if n > hi else n


def find_chromium_stream_id():
    """
    Parse `wpctl status` and return the Stream ID for Chromium (int), or None.
    Looks for a line like: '83. Chromium'
    """
    out = sh_out(["wpctl", "status"])
    if not out:
        return None

    in_streams = False
    for line in out.splitlines():
        s = line.strip()
        if s in ("Streams:", "└─ Streams:"):
            in_streams = True
            continue

        if in_streams:
            m = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
            if not m:
                continue
            sid = int(m.group(1))
            name = m.group(2).strip().lower()
            if "chromium" in name or "chrome" in name:
                return sid

    return None


def get_cached_chromium_stream_id():
    global _last_stream_id, _last_stream_id_t
    now = time.time()
    if _last_stream_id is None or (now - _last_stream_id_t) > STREAM_REFRESH_SEC:
        _last_stream_id = find_chromium_stream_id()
        _last_stream_id_t = now
    return _last_stream_id


def set_chromium_volume_percent(percent: int):
    """Set Chromium stream volume via wpctl, percent 0..100."""
    global _last_volume
    percent = int(clamp(percent, 0, 100))

    if _last_volume is not None and abs(percent - _last_volume) < VOL_DEADBAND:
        return

    sid = get_cached_chromium_stream_id()
    if sid is None:
        # Chromium stream doesn't exist yet (Spotify not playing)
        return

    vol = clamp(percent / 100.0, VOL_MIN, VOL_MAX)
    sh(["wpctl", "set-volume", str(sid), f"{vol:.2f}"])
    _last_volume = percent


def needle_play():
    global _last_needle_action
    now = time.time()
    if now - _last_needle_action < NEEDLE_DEBOUNCE:
        return
    sh([SPOTIFY_CMD, "play"])
    _last_needle_action = now


def needle_pause():
    global _last_needle_action
    now = time.time()
    if now - _last_needle_action < NEEDLE_DEBOUNCE:
        return
    sh([SPOTIFY_CMD, "pause"])
    _last_needle_action = now


def needle_toggle():
    global _last_needle_action
    now = time.time()
    if now - _last_needle_action < NEEDLE_DEBOUNCE:
        return
    sh([SPOTIFY_CMD, "play-pause"])
    _last_needle_action = now


def parse_and_handle_line(line: str):
    """
    Supported Arduino lines (examples):
      VOL:73
      VOL=73
      V:73
      NEEDLE_ON / NEEDLE_OFF
      ARM_ON / ARM_OFF
      PLAY / PAUSE / TOGGLE
      NEEDLE:1 / NEEDLE:0
      ARM:1 / ARM:0
      N:1 / N:0
    """
    line = line.strip()
    if not line:
        return

    if DEBUG_PRINT_RX:
        print(f"RX: {line}", flush=True)

    u = line.upper()

    # Volume formats
    m = re.match(r"^(VOL|V)\s*[:=]\s*(\d{1,3})\s*$", u)
    if m:
        v = int(m.group(2))
        set_chromium_volume_percent(v)
        return

    # Needle / play control formats
    if u in ("NEEDLE_ON", "ARM_ON", "PLAY", "START", "ON"):
        needle_play()
        return

    if u in ("NEEDLE_OFF", "ARM_OFF", "PAUSE", "STOP", "OFF"):
        needle_pause()
        return

    if u in ("TOGGLE", "PLAY_PAUSE", "NEEDLE_TOGGLE"):
        needle_toggle()
        return

    # Numeric formats: NEEDLE:1, ARM:0, N:1
    m = re.match(r"^(NEEDLE|ARM|N)\s*[:=]\s*([01])\s*$", u)
    if m:
        if m.group(2) == "1":
            needle_play()
        else:
            needle_pause()
        return


def main():
    if not have("wpctl"):
        print("ERROR: wpctl not found.", flush=True)
        return
    if not have("playerctl"):
        print("ERROR: playerctl not found.", flush=True)
        return
    if not shutil.which(SPOTIFY_CMD):
        print(f"ERROR: {SPOTIFY_CMD} not found or not executable.", flush=True)
        return

    # Keep trying until Nano is present
    while True:
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
            print(f"Connected to {SERIAL_PORT} @ {BAUD}", flush=True)
            break
        except Exception as e:
            print(f"Waiting for Nano on {SERIAL_PORT}: {e}", flush=True)
            time.sleep(1.0)

    while True:
        try:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode(errors="ignore").strip()
            if not line:
                continue
            parse_and_handle_line(line)
        except Exception as e:
            print(f"Serial loop error: {e}", flush=True)
            time.sleep(0.2)


if __name__ == "__main__":
    main()
