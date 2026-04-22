#!/usr/bin/env python3
import os
import time
from pathlib import Path

from smbus2 import SMBus


def load_env_file(path):
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


load_env_file(Path(__file__).resolve().parent.parent / ".env")

ARM_PARKED = "PARKED"
ARM_ACTIVE = "ACTIVE"

AS5600_BUS = int(os.getenv("VINYL_I2C_BUS", "1"))
AS5600_ADDR = int(os.getenv("VINYL_AS5600_ADDR", "0x36"), 0)
REG_ANGLE_HI = int(os.getenv("VINYL_AS5600_ANGLE_HI", "0x0E"), 0)
REG_ANGLE_LO = int(os.getenv("VINYL_AS5600_ANGLE_LO", "0x0F"), 0)
ANGLE_OFFSET_DEG = float(os.getenv("VINYL_ANGLE_OFFSET_DEG", "0"))
ACTIVE_RANGE_START_RAW = os.getenv("VINYL_ACTIVE_RANGE_START_DEG", "").strip()
ACTIVE_RANGE_END_RAW = os.getenv("VINYL_ACTIVE_RANGE_END_DEG", "").strip()
ACTIVE_RANGE_START_DEG = float(ACTIVE_RANGE_START_RAW) if ACTIVE_RANGE_START_RAW else None
ACTIVE_RANGE_END_DEG = float(ACTIVE_RANGE_END_RAW) if ACTIVE_RANGE_END_RAW else None
PARK_ENTER_DEG = float(os.getenv("VINYL_PARK_ENTER_DEG", "15"))
PARK_EXIT_DEG = float(os.getenv("VINYL_PARK_EXIT_DEG", "20"))


def read_raw(bus):
    hi = bus.read_byte_data(AS5600_ADDR, REG_ANGLE_HI)
    lo = bus.read_byte_data(AS5600_ADDR, REG_ANGLE_LO)
    return ((hi << 8) | lo) & 0x0FFF


def raw_to_deg(raw):
    return (raw * 360.0) / 4096.0


def normalize_angle(deg):
    return (deg - ANGLE_OFFSET_DEG) % 360.0


def angular_distance_from_zero(angle):
    angle = normalize_angle(angle)
    return min(angle, 360.0 - angle)


def use_active_range():
    return ACTIVE_RANGE_START_DEG is not None and ACTIVE_RANGE_END_DEG is not None


def angle_in_active_range(angle):
    if not use_active_range():
        return False

    normalized = normalize_angle(angle)
    start = ACTIVE_RANGE_START_DEG % 360.0
    end = ACTIVE_RANGE_END_DEG % 360.0

    if start <= end:
        return start <= normalized <= end
    return normalized >= start or normalized <= end


def classify_arm_state(angle, current_state):
    if use_active_range():
        return ARM_ACTIVE if angle_in_active_range(angle) else ARM_PARKED

    distance = angular_distance_from_zero(angle)
    if current_state == ARM_PARKED:
        return ARM_ACTIVE if distance >= PARK_EXIT_DEG else ARM_PARKED
    if current_state == ARM_ACTIVE:
        return ARM_PARKED if distance <= PARK_ENTER_DEG else ARM_ACTIVE
    return ARM_PARKED if distance <= PARK_ENTER_DEG else ARM_ACTIVE


with SMBus(AS5600_BUS) as bus:
    mode_text = (
        f"play_range={ACTIVE_RANGE_START_DEG:.1f}-{ACTIVE_RANGE_END_DEG:.1f}"
        if use_active_range()
        else f"offset={ANGLE_OFFSET_DEG:.1f} enter={PARK_ENTER_DEG:.1f} exit={PARK_EXIT_DEG:.1f}"
    )
    print(
        "Move tonearm. Ctrl+C to stop.\n"
        f"bus={AS5600_BUS} addr={AS5600_ADDR:#04x} {mode_text}\n"
    )
    arm_state = None
    while True:
        raw = read_raw(bus)
        deg = raw_to_deg(raw)
        norm = normalize_angle(deg)
        distance = angular_distance_from_zero(deg)
        arm_state = classify_arm_state(deg, arm_state)
        print(
            f"angle={norm:7.2f} raw_angle={deg:7.2f} raw={raw:4d} "
            f"distance={distance:6.2f} state={arm_state:6s}",
            end="\r",
            flush=True,
        )
        time.sleep(0.02)
