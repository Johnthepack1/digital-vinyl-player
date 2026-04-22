#!/usr/bin/env python3
import argparse
import math
import os
import select
import sys
import time
from dataclasses import dataclass
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


REPO_ROOT = Path(__file__).resolve().parent.parent
load_env_file(REPO_ROOT / ".env")

ARM_PARKED = "PARKED"
ARM_ACTIVE = "ACTIVE"

AS5600_BUS = int(os.getenv("VINYL_I2C_BUS", "1"))
AS5600_ADDR = int(os.getenv("VINYL_AS5600_ADDR", "0x36"), 0)
REG_ANGLE_HI = int(os.getenv("VINYL_AS5600_ANGLE_HI", "0x0E"), 0)
REG_ANGLE_LO = int(os.getenv("VINYL_AS5600_ANGLE_LO", "0x0F"), 0)
ANGLE_OFFSET_DEG = float(os.getenv("VINYL_ANGLE_OFFSET_DEG", "0"))
PARK_ENTER_DEG = float(os.getenv("VINYL_PARK_ENTER_DEG", "15"))
PARK_EXIT_DEG = float(os.getenv("VINYL_PARK_EXIT_DEG", "20"))


@dataclass
class SampleSummary:
    label: str
    center_deg: float
    p95_spread_deg: float
    max_spread_deg: float
    count: int


def read_raw(bus):
    hi = bus.read_byte_data(AS5600_ADDR, REG_ANGLE_HI)
    lo = bus.read_byte_data(AS5600_ADDR, REG_ANGLE_LO)
    return ((hi << 8) | lo) & 0x0FFF


def raw_to_deg(raw):
    return (raw * 360.0) / 4096.0


def normalize_angle(angle, offset_deg):
    return (angle - offset_deg) % 360.0


def signed_angular_delta(angle, reference):
    return ((angle - reference + 180.0) % 360.0) - 180.0


def angular_distance(angle, reference):
    return abs(signed_angular_delta(angle, reference))


def angular_distance_from_zero(angle, offset_deg):
    normalized = normalize_angle(angle, offset_deg)
    return min(normalized, 360.0 - normalized)


def classify_arm_state(angle, current_state, offset_deg, park_enter_deg, park_exit_deg):
    distance = angular_distance_from_zero(angle, offset_deg)
    if current_state == ARM_PARKED:
        return ARM_ACTIVE if distance >= park_exit_deg else ARM_PARKED
    if current_state == ARM_ACTIVE:
        return ARM_PARKED if distance <= park_enter_deg else ARM_ACTIVE
    return ARM_PARKED if distance <= park_enter_deg else ARM_ACTIVE


def circular_mean_deg(angles):
    sin_total = sum(math.sin(math.radians(angle)) for angle in angles)
    cos_total = sum(math.cos(math.radians(angle)) for angle in angles)
    if sin_total == 0.0 and cos_total == 0.0:
        return 0.0
    return math.degrees(math.atan2(sin_total, cos_total)) % 360.0


def percentile(values, fraction):
    if not values:
        return 0.0

    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    index = (len(ordered) - 1) * fraction
    lower = int(math.floor(index))
    upper = int(math.ceil(index))
    if lower == upper:
        return ordered[lower]

    weight = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def summarize_samples(label, angles):
    center = circular_mean_deg(angles)
    deviations = [angular_distance(angle, center) for angle in angles]
    return SampleSummary(
        label=label,
        center_deg=center,
        p95_spread_deg=percentile(deviations, 0.95),
        max_spread_deg=max(deviations) if deviations else 0.0,
        count=len(angles),
    )


def suggest_thresholds(parked, boundary):
    offset_deg = parked.center_deg % 360.0
    boundary_distance = angular_distance(boundary.center_deg, parked.center_deg)
    noise_margin = max(3.0, parked.p95_spread_deg + 2.0)

    park_exit_deg = boundary_distance - max(3.0, noise_margin)
    park_exit_deg = max(noise_margin + 2.0, park_exit_deg)

    hysteresis = max(5.0, noise_margin + 1.0)
    park_enter_deg = max(noise_margin, park_exit_deg - hysteresis)

    if park_enter_deg >= park_exit_deg:
        park_enter_deg = max(noise_margin, park_exit_deg - 5.0)

    warning = None
    if boundary_distance <= noise_margin + 4.0:
        warning = (
            "The ACTIVE boundary sample is too close to the parked noise floor. "
            "Capture a position farther from park and rerun the test."
        )
    elif boundary_distance >= 60.0:
        warning = (
            "The ACTIVE boundary sample is very far from park. "
            "If playback should start sooner, rerun the test and sample the first position "
            "that should count as ACTIVE."
        )

    return {
        "offset_deg": offset_deg,
        "boundary_distance_deg": boundary_distance,
        "noise_margin_deg": noise_margin,
        "park_enter_deg": park_enter_deg,
        "park_exit_deg": park_exit_deg,
        "warning": warning,
    }


def print_live_line(angle, raw, offset_deg, park_enter_deg, park_exit_deg, arm_state, suffix):
    normalized = normalize_angle(angle, offset_deg)
    distance = angular_distance_from_zero(angle, offset_deg)
    text = (
        f"angle={normalized:7.2f} raw_angle={angle:7.2f} raw={raw:4d} "
        f"distance={distance:6.2f} state={arm_state:6s} {suffix}"
    )
    print(text, end="\r", flush=True)
    return len(text)


def wait_for_enter(bus, prompt, offset_deg, park_enter_deg, park_exit_deg, poll_sec):
    print(prompt)
    arm_state = None
    width = 0

    while True:
        raw = read_raw(bus)
        angle = raw_to_deg(raw)
        arm_state = classify_arm_state(angle, arm_state, offset_deg, park_enter_deg, park_exit_deg)
        width = max(
            width,
            print_live_line(
                angle,
                raw,
                offset_deg,
                park_enter_deg,
                park_exit_deg,
                arm_state,
                "press Enter to capture",
            ),
        )

        ready, _, _ = select.select([sys.stdin], [], [], poll_sec)
        if ready:
            sys.stdin.readline()
            print(" " * width, end="\r", flush=True)
            return


def capture_samples(bus, label, duration_sec, offset_deg, park_enter_deg, park_exit_deg, poll_sec):
    print(f"Capturing {label} for {duration_sec:.1f}s...")
    end_at = time.monotonic() + duration_sec
    arm_state = None
    width = 0
    angles = []

    while time.monotonic() < end_at:
        raw = read_raw(bus)
        angle = raw_to_deg(raw)
        arm_state = classify_arm_state(angle, arm_state, offset_deg, park_enter_deg, park_exit_deg)
        angles.append(angle)

        remaining = max(0.0, end_at - time.monotonic())
        width = max(
            width,
            print_live_line(
                angle,
                raw,
                offset_deg,
                park_enter_deg,
                park_exit_deg,
                arm_state,
                f"{label} {remaining:4.1f}s left",
            ),
        )
        time.sleep(poll_sec)

    print(" " * width, end="\r", flush=True)
    print(f"{label} capture complete.")
    return angles


def print_summary(summary, reference_deg=None):
    print(
        f"{summary.label}: center={summary.center_deg:0.2f} deg, "
        f"p95 spread={summary.p95_spread_deg:0.2f} deg, "
        f"peak spread={summary.max_spread_deg:0.2f} deg, "
        f"samples={summary.count}"
    )

    if reference_deg is not None:
        distance = angular_distance(summary.center_deg, reference_deg)
        normalized = normalize_angle(summary.center_deg, reference_deg)
        print(
            f"{summary.label}: distance from parked={distance:0.2f} deg, "
            f"normalized={normalized:0.2f} deg"
        )


def main():
    parser = argparse.ArgumentParser(description="Guided AS5600 parked-zone tester")
    parser.add_argument(
        "--capture-sec",
        type=float,
        default=2.0,
        help="Seconds to sample each position (default: 2.0)",
    )
    parser.add_argument(
        "--poll-sec",
        type=float,
        default=0.02,
        help="Sensor polling interval in seconds (default: 0.02)",
    )
    args = parser.parse_args()

    print("AS5600 Zone Test")
    print(
        f"bus={AS5600_BUS} addr={AS5600_ADDR:#04x} "
        f"current_offset={ANGLE_OFFSET_DEG:.1f} current_enter={PARK_ENTER_DEG:.1f} current_exit={PARK_EXIT_DEG:.1f}"
    )
    print("This test samples two positions:")
    print("1. Fully parked")
    print("2. The first position that should count as ACTIVE")
    print("")

    with SMBus(AS5600_BUS) as bus:
        wait_for_enter(
            bus,
            "Move the tonearm to its fully parked position, then press Enter.",
            ANGLE_OFFSET_DEG,
            PARK_ENTER_DEG,
            PARK_EXIT_DEG,
            args.poll_sec,
        )
        parked_angles = capture_samples(
            bus,
            "parked",
            args.capture_sec,
            ANGLE_OFFSET_DEG,
            PARK_ENTER_DEG,
            PARK_EXIT_DEG,
            args.poll_sec,
        )

        wait_for_enter(
            bus,
            "Move the tonearm to the first position that should count as ACTIVE, then press Enter.",
            ANGLE_OFFSET_DEG,
            PARK_ENTER_DEG,
            PARK_EXIT_DEG,
            args.poll_sec,
        )
        boundary_angles = capture_samples(
            bus,
            "active-boundary",
            args.capture_sec,
            ANGLE_OFFSET_DEG,
            PARK_ENTER_DEG,
            PARK_EXIT_DEG,
            args.poll_sec,
        )

    parked_summary = summarize_samples("parked", parked_angles)
    boundary_summary = summarize_samples("active-boundary", boundary_angles)
    suggestion = suggest_thresholds(parked_summary, boundary_summary)

    print("")
    print("Sample Summary")
    print("--------------")
    print_summary(parked_summary)
    print_summary(boundary_summary, reference_deg=parked_summary.center_deg)
    print("")
    print("Suggested Starting Point")
    print("------------------------")
    print(f"VINYL_ANGLE_OFFSET_DEG={suggestion['offset_deg']:.1f}")
    print(f"VINYL_PARK_ENTER_DEG={suggestion['park_enter_deg']:.1f}")
    print(f"VINYL_PARK_EXIT_DEG={suggestion['park_exit_deg']:.1f}")
    print("")
    print(
        f"Parked noise margin: {suggestion['noise_margin_deg']:.1f} deg, "
        f"ACTIVE boundary distance: {suggestion['boundary_distance_deg']:.1f} deg"
    )

    if suggestion["warning"]:
        print("")
        print(f"Warning: {suggestion['warning']}")


if __name__ == "__main__":
    main()
