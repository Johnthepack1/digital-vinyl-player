#!/usr/bin/env python3
import time
import subprocess
import smbus2

# ==============================
# CONFIG
# ==============================

I2C_BUS = 1
AS5600_ADDR = 0x36

# ----- PLAY RANGE (absolute angles) -----
# If the needle arm angle is inside this range -> PLAY
# If outside -> PAUSE
#
# NOTE: These are absolute degrees from the AS5600 (0..360).
# You will tune these after watching DEBUG output.
PLAY_RANGE_START = 60.0
PLAY_RANGE_END   = 140.0

# ----- Hysteresis (recommended) -----
# This prevents chatter right at the boundary.
# Enter PLAY only when inside the "enter" range.
# Exit PLAY only when outside the "exit" range.
#
# If you want "pure switch behavior", set ENTER_PAD=0 and EXIT_PAD=0
ENTER_PAD_DEG = 4.0   # shrink PLAY range a bit for entering (more strict)
EXIT_PAD_DEG  = 6.0   # expand PLAY range a bit for exiting (more forgiving)

READ_INTERVAL = 0.05
TOGGLE_DEBOUNCE = 0.7

SPOTIFY_CTL = "/home/vinyl2/digital-vinyl-player/bin/spotify_ctl.sh"

DEBUG = False
DEBUG_PRINT_SEC = 0.5

# If your sensor/magnet is reversed, set this to True to flip angle
INVERT_ANGLE = False

# ==============================
# I2C / AS5600
# ==============================

bus = smbus2.SMBus(I2C_BUS)

def read_raw_angle():
    # AS5600 RAW ANGLE = registers 0x0E (high) and 0x0F (low), 12-bit
    high = bus.read_byte_data(AS5600_ADDR, 0x0E)
    low  = bus.read_byte_data(AS5600_ADDR, 0x0F)
    return ((high << 8) | low) & 0x0FFF

def raw_to_degrees(raw):
    return (raw * 360.0) / 4096.0

def read_angle_deg():
    a = raw_to_degrees(read_raw_angle())
    if INVERT_ANGLE:
        a = (360.0 - a) % 360.0
    return a

# ==============================
# RANGE HELPERS (handles wrap-around)
# ==============================

def in_wrapped_range(angle, start, end):
    """
    True if angle is inside [start..end], allowing wrap-around.
    Example wrap: start=300, end=40 means [300..360) U [0..40]
    """
    angle %= 360.0
    start %= 360.0
    end   %= 360.0

    if start <= end:
        return (start <= angle <= end)
    else:
        # wrapped case
        return (angle >= start) or (angle <= end)

def shrink_range(start, end, pad):
    """
    Shrink the range inward by pad degrees on both ends.
    """
    return (start + pad) % 360.0, (end - pad) % 360.0

def expand_range(start, end, pad):
    """
    Expand the range outward by pad degrees on both ends.
    """
    return (start - pad) % 360.0, (end + pad) % 360.0

# ==============================
# SPOTIFY CONTROL
# ==============================

def spotify_play():
    subprocess.run([SPOTIFY_CTL, "play"],
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)

def spotify_pause():
    subprocess.run([SPOTIFY_CTL, "pause"],
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)

# ==============================
# MAIN
# ==============================

def main():
    print("pico_control: AS5600 needle -> Spotify play/pause (ABS RANGE mode)")
    print(f"pico_control: PLAY_RANGE = {PLAY_RANGE_START:.1f}° .. {PLAY_RANGE_END:.1f}° (wrapped ok)")
    print(f"pico_control: ENTER_PAD={ENTER_PAD_DEG:.1f}  EXIT_PAD={EXIT_PAD_DEG:.1f}")

    # Precompute hysteresis ranges
    enter_start, enter_end = shrink_range(PLAY_RANGE_START, PLAY_RANGE_END, ENTER_PAD_DEG)
    exit_start,  exit_end  = expand_range(PLAY_RANGE_START, PLAY_RANGE_END, EXIT_PAD_DEG)

    state = None  # "PLAY" or "PARK"
    last_toggle = 0.0
    last_debug = 0.0

    # ---- BOOT BEHAVIOR (this is what you wanted) ----
    # If we boot inside PLAY zone -> force play.
    # If we boot outside PLAY zone -> force pause.
    boot_angle = read_angle_deg()
    boot_in_play = in_wrapped_range(boot_angle, PLAY_RANGE_START, PLAY_RANGE_END)

    if boot_in_play:
        spotify_play()
        state = "PLAY"
        print(f"pico_control: boot angle {boot_angle:.1f}° IN play-zone -> PLAY")
    else:
        spotify_pause()
        state = "PARK"
        print(f"pico_control: boot angle {boot_angle:.1f}° OUT of play-zone -> PARK/PAUSE")

    time.sleep(0.2)

    while True:
        now = time.time()
        angle = read_angle_deg()

        # Debug print
        if DEBUG and (now - last_debug) > DEBUG_PRINT_SEC:
            in_enter = in_wrapped_range(angle, enter_start, enter_end)
            in_exit  = in_wrapped_range(angle, exit_start,  exit_end)
            print(
                f"pico_control: angle={angle:6.1f}°  "
                f"state={state}  "
                f"enter[{enter_start:.1f}..{enter_end:.1f}]={int(in_enter)}  "
                f"exit[{exit_start:.1f}..{exit_end:.1f}]={int(in_exit)}"
            )
            last_debug = now

        # Hysteresis state machine:
        # - To go PLAY: must be inside ENTER range
        # - To go PARK: must be outside EXIT range
        if (now - last_toggle) > TOGGLE_DEBOUNCE:
            if state == "PARK":
                if in_wrapped_range(angle, enter_start, enter_end):
                    spotify_play()
                    state = "PLAY"
                    last_toggle = now
                    print("pico_control: >>> PLAY")
            else:  # state == "PLAY"
                if not in_wrapped_range(angle, exit_start, exit_end):
                    spotify_pause()
                    state = "PARK"
                    last_toggle = now
                    print("pico_control: >>> PARK/PAUSE")

        time.sleep(READ_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("pico_control: exiting")
