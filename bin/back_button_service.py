#!/usr/bin/env python3
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

for system_path in (
    Path("/usr/lib/python3/dist-packages"),
    Path(f"/usr/lib/python{sys.version_info.major}.{sys.version_info.minor}/dist-packages"),
    SRC_ROOT,
):
    if system_path.exists():
        system_path_str = str(system_path)
        if system_path_str not in sys.path:
            sys.path.append(system_path_str)

try:
    from gpiozero import Button
except Exception:
    Button = None

from runtime_control.vinyl_state import (
    ASSETS,
    discover_vinyl_paths,
    is_setup_mode_forced,
    load_saved_vinyl_index,
    save_saved_vinyl_index,
    set_setup_mode_forced,
)


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


load_env_file(REPO_ROOT / ".env")

BACK_BUTTON_PIN_RAW = os.getenv("VINYL_BACK_BUTTON_PIN", "22").strip()
BACK_BUTTON_PIN = int(BACK_BUTTON_PIN_RAW) if BACK_BUTTON_PIN_RAW else None
BACK_BUTTON_HOLD_SEC = float(os.getenv("VINYL_BACK_BUTTON_HOLD_SEC", "10.0"))
BACK_BUTTON_BOUNCE_TIME = float(os.getenv("VINYL_BACK_BUTTON_BOUNCE_TIME", "0.03"))

SPOTIFY_CMD = REPO_ROOT / "bin" / "spotify_cmd.sh"


def log(message):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{stamp} {message}", file=sys.stderr, flush=True)


def vinyl_label(vinyl_path):
    try:
        return str(vinyl_path.relative_to(ASSETS))
    except ValueError:
        return vinyl_path.name


def open_back_button():
    if BACK_BUTTON_PIN is None:
        log("Back button service disabled: VINYL_BACK_BUTTON_PIN is not set.")
        return None

    if Button is None:
        log("Back button service disabled: gpiozero is not installed.")
        return None

    options = [
        {"pull_up": True, "bounce_time": BACK_BUTTON_BOUNCE_TIME, "hold_time": BACK_BUTTON_HOLD_SEC},
        {"pull_up": True, "bounce_time": BACK_BUTTON_BOUNCE_TIME},
        {"pull_up": True},
    ]

    for kwargs in options:
        try:
            button = Button(BACK_BUTTON_PIN, **kwargs)
            button.hold_time = BACK_BUTTON_HOLD_SEC
            if hasattr(button, "hold_repeat"):
                button.hold_repeat = False
            log(
                f"Back button service ready on GPIO {BACK_BUTTON_PIN} "
                f"(hold={BACK_BUTTON_HOLD_SEC:.1f}s, bounce={BACK_BUTTON_BOUNCE_TIME:.3f}s)."
            )
            return button
        except TypeError:
            continue
        except Exception as exc:
            log(f"Back button service disabled: could not open GPIO pin {BACK_BUTTON_PIN} ({exc}).")
            return None

    log(f"Back button service disabled: could not configure GPIO pin {BACK_BUTTON_PIN}.")
    return None


def send_spotify_command(cmd):
    env = os.environ.copy()
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")

    if SPOTIFY_CMD.exists() and os.access(SPOTIFY_CMD, os.X_OK):
        try:
            subprocess.Popen(
                [str(SPOTIFY_CMD), cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
        except Exception as exc:
            log(f"Could not run {SPOTIFY_CMD.name} {cmd} ({exc}).")


def restart_spotify_service():
    try:
        subprocess.run(
            ["systemctl", "--user", "restart", "spotify.service"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        log("Restarted spotify.service for setup mode change.")
    except Exception as exc:
        log(f"Could not restart spotify.service ({exc}).")


def cycle_skin():
    try:
        vinyl_paths = discover_vinyl_paths()
    except Exception as exc:
        log(f"Skin change skipped: {exc}.")
        return

    if len(vinyl_paths) <= 1:
        log("Skin change skipped: only one vinyl skin is available.")
        return

    current_index = load_saved_vinyl_index(len(vinyl_paths))
    next_index = (current_index + 1) % len(vinyl_paths)

    try:
        save_saved_vinyl_index(next_index)
    except Exception as exc:
        log(f"Skin change failed: could not save index ({exc}).")
        return

    log(f"Short press: vinyl skin -> {vinyl_label(vinyl_paths[next_index])}")


def set_setup_mode(enabled, source):
    enabled = bool(enabled)
    if enabled == is_setup_mode_forced():
        return

    try:
        set_setup_mode_forced(enabled)
    except Exception as exc:
        log(f"Setup mode update failed ({exc}).")
        return

    if enabled:
        log(f"Long press via {source}: setup mode enabled.")
        send_spotify_command("pause")
    else:
        log(f"Long press via {source}: setup mode disabled.")
    restart_spotify_service()


def run():
    button = open_back_button()
    if button is None:
        return 1

    state = {"long_fired": False, "pressed_at": 0.0}
    lock = threading.Lock()
    stop_event = threading.Event()

    def handle_press():
        with lock:
            state["long_fired"] = False
            state["pressed_at"] = time.monotonic()

    def handle_hold():
        with lock:
            if state["long_fired"]:
                return
            state["long_fired"] = True

        setup_mode_active = is_setup_mode_forced()
        set_setup_mode(not setup_mode_active, "GPIO 22")

    def handle_release():
        with lock:
            long_fired = state["long_fired"]
            state["long_fired"] = False
            state["pressed_at"] = 0.0

        if long_fired:
            return

        if is_setup_mode_forced():
            log("Short press ignored while setup mode is active.")
            return

        cycle_skin()

    button.when_pressed = handle_press
    button.when_held = handle_hold
    button.when_released = handle_release

    try:
        stop_event.wait()
    except KeyboardInterrupt:
        log("Back button service exiting on keyboard interrupt.")
    finally:
        button.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
