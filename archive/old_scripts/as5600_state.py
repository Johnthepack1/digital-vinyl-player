#!/usr/bin/env python3
import time
from smbus2 import SMBus

AS5600_ADDR = 0x36
RAW_ANGLE_HI = 0x0C
RAW_ANGLE_LO = 0x0D

# ====== SET THESE ======
PLAY_START_DEG = 60.0
PLAY_END_DEG   = 220.0
# =======================

def read_angle_deg(bus) -> float:
    hi = bus.read_byte_data(AS5600_ADDR, RAW_ANGLE_HI)
    lo = bus.read_byte_data(AS5600_ADDR, RAW_ANGLE_LO)
    raw = ((hi << 8) | lo) & 0x0FFF
    return raw * 360.0 / 4096.0

def in_play_zone(angle: float) -> bool:
    a = angle % 360.0
    s = PLAY_START_DEG % 360.0
    e = PLAY_END_DEG   % 360.0
    # normal zone
    if s <= e:
        return s <= a <= e
    # wrap-around zone (e.g., 300..40)
    return a >= s or a <= e

def main():
    with SMBus(1) as bus:
        last = None
        while True:
            try:
                ang = read_angle_deg(bus)
                state = "Playing" if in_play_zone(ang) else "Paused"
                if state != last:
                    print(state, flush=True)
                    last = state
                time.sleep(0.05)
            except Exception:
                # don't crash if i2c glitches
                time.sleep(0.2)

if __name__ == "__main__":
    main()
