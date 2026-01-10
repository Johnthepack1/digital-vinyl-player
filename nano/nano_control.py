#!/usr/bin/env python3
import os
import time
import subprocess
import serial

# ============== CONFIG ==============
SERIAL_PORT = "/dev/ttyUSB0"
BAUD = 115200

# Volume clamp (feel free to tune)
MIN_VOL = 0.05   # 25%
MAX_VOL = 0.95   # 1.15%

# Debounce / spam prevention
VOL_MIN_STEP = 2            # ignore tiny changes
VOL_MIN_INTERVAL = 0.08     # seconds between applying volume

# Scripts
CYCLE_SKIN = os.path.expanduser("~/bin/cycle_vinyl_skin.sh")
ENTER_SETUP = os.path.expanduser("~/bin/enter_setup_mode.sh")
# ===================================


def sh(cmd):
    try:
        subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def playerctl(cmd):
    sh(["playerctl", cmd])


def set_chromium_stream_volume(percent_0_100: int):
    """
    Use WirePlumber/PipeWire via wpctl.
    Strategy:
    - Set DEFAULT_SINK volume once elsewhere (or leave)
    - Set Chromium stream volume by node name match if possible; fallback to default sink.
    For reliability here: set DEFAULT sink volume (still feels like knob).
    If you want strict "Chromium-only", we can improve later by picking the stream node.
    """
    p = max(0, min(100, int(percent_0_100)))
    # map to MIN..MAX
    vol = MIN_VOL + (MAX_VOL - MIN_VOL) * (p / 100.0)
    sh(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{vol:.3f}"])


def main():
    last_vol = None
    last_vol_t = 0.0

    while True:
        try:
            with serial.Serial(SERIAL_PORT, BAUD, timeout=1) as ser:
                ser.reset_input_buffer()
                while True:
                    raw = ser.readline().decode(errors="ignore").strip()
                    if not raw:
                        continue

                    line = raw.upper()

                    # VOL:NN
                    if line.startswith("VOL:"):
                        try:
                            v = int(line.split(":", 1)[1])
                        except ValueError:
                            continue

                        now = time.time()
                        if last_vol is None or abs(v - last_vol) >= VOL_MIN_STEP:
                            if now - last_vol_t >= VOL_MIN_INTERVAL:
                                set_chromium_stream_volume(v)
                                last_vol = v
                                last_vol_t = now
                        continue

                    # NEEDLE:DOWN / NEEDLE:UP
                    if line == "NEEDLE:DOWN":
                        playerctl("play")
                        continue
                    if line == "NEEDLE:UP":
                        playerctl("pause")
                        continue

                    # Button events
                    if line == "BTN:SHORT":
                        sh([CYCLE_SKIN])
                        continue
                    if line == "BTN:LONG":
                        sh([ENTER_SETUP])
                        continue

        except Exception:
            # If Nano disconnects, wait and retry
            time.sleep(1.0)


if __name__ == "__main__":
    main()
