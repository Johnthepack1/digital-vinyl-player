#!/usr/bin/env python3
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from io import BytesIO
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO_ROOT = BASE.parent.parent
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

import pygame

try:
    from gpiozero import RotaryEncoder
except Exception:
    RotaryEncoder = None

try:
    import smbus2
except Exception:
    smbus2 = None

from runtime_control.vinyl_state import discover_vinyl_paths, load_saved_vinyl_index, save_saved_vinyl_index


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


load_env_file(Path(__file__).resolve().parents[2] / ".env")

# =========================
# EASY TUNING (edit these)
# =========================
SCREEN = 1080
FPS = 30

# Vinyl spin
ANGLE_SPEED = -0.9

# Polling
POLL_SEC = 0.25
TONEARM_POLL_SEC = 0.05
PLAYER_CHECK_SEC = 1.0

# Sizes
VINYL_SIZE = int(1080 * 1.25)
ALBUM_SIZE = 335
BTN_SIZE = 65
PROG_W = 575
PROG_H = 8

# Positions
ALBUM_OFFSET_X = -395
ALBUM_OFFSET_Y = 20

BTN_GAP = 55
BTN_Y = int(SCREEN * 0.90)

PROG_Y = int(SCREEN * 0.83)

TEXT_LEFT_PADDING = 0
TITLE_Y_OFFSET = 70
ARTIST_Y_OFFSET = 35
TIME_Y_OFFSET = 10

PREFERRED_PREFIXES = ("chromium.instance", "chromium", "chrome", "spotify")

ARM_PARKED = "PARKED"
ARM_ACTIVE = "ACTIVE"
SPOTIFY_PLAYING = "PLAYING"
SPOTIFY_PAUSED = "PAUSED"
SCREEN_VINYL = "VINYL"
SCREEN_KIOSK = "KIOSK"

# Volume overlay
VOL_POLL_SEC = 0.25
VOL_DEADBAND = 1
VOL_OVERLAY_HOLD = 0.9
VOL_FADE_IN = 0.18
VOL_FADE_OUT = 0.35
VOL_W = 360
VOL_Y = int(SCREEN * 0.10)
VOL_LINE_THICK_BG = 2
VOL_LINE_THICK_FG = 3
VOL_SMOOTH_SPEED = 10.0
VOL_MIN_RETRIGGER = 0.35

# GPIO rotary encoder
ROTARY_A = int(os.getenv("VINYL_ROTARY_A", "17"))
ROTARY_B = int(os.getenv("VINYL_ROTARY_B", "27"))
ROTARY_STEP_PERCENT = int(os.getenv("VINYL_VOLUME_STEP_PERCENT", "3"))
ROTARY_DIRECTION = int(os.getenv("VINYL_ROTARY_DIRECTION", "1"))
ROTARY_BOUNCE_TIME = float(os.getenv("VINYL_ROTARY_BOUNCE_TIME", "0.002"))

# AS5600 tonearm position
AS5600_BUS = int(os.getenv("VINYL_I2C_BUS", "1"))
AS5600_ADDR = int(os.getenv("VINYL_AS5600_ADDR", "0x36"), 0)
AS5600_ANGLE_HI = int(os.getenv("VINYL_AS5600_ANGLE_HI", "0x0E"), 0)
AS5600_ANGLE_LO = int(os.getenv("VINYL_AS5600_ANGLE_LO", "0x0F"), 0)
ANGLE_OFFSET_DEG = float(os.getenv("VINYL_ANGLE_OFFSET_DEG", "0"))
ACTIVE_RANGE_START_RAW = os.getenv("VINYL_ACTIVE_RANGE_START_DEG", "").strip()
ACTIVE_RANGE_END_RAW = os.getenv("VINYL_ACTIVE_RANGE_END_DEG", "").strip()
ACTIVE_RANGE_START_DEG = float(ACTIVE_RANGE_START_RAW) if ACTIVE_RANGE_START_RAW else None
ACTIVE_RANGE_END_DEG = float(ACTIVE_RANGE_END_RAW) if ACTIVE_RANGE_END_RAW else None
PARK_ENTER_DEG = float(os.getenv("VINYL_PARK_ENTER_DEG", "15"))
PARK_EXIT_DEG = float(os.getenv("VINYL_PARK_EXIT_DEG", "20"))
TONEARM_STABLE_SEC = float(os.getenv("VINYL_TONEARM_STABLE_SEC", "0.25"))
DEBUG_STATUS_SEC = float(os.getenv("VINYL_DEBUG_STATUS_SEC", "1.0"))
# =========================

ASSETS = REPO_ROOT / "assets" / "ui_assets"
BIN_DIR = REPO_ROOT / "bin"
SPOTIFY_CMD = BIN_DIR / "spotify_cmd.sh"

_last_stream_id = None
_last_stream_id_t = 0.0
STREAM_REFRESH_SEC = 3.0


def log(message):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{stamp} {message}", file=sys.stderr, flush=True)


def sh(cmd):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return None


def clamp(value, lower, upper):
    return lower if value < lower else upper if value > upper else value


def fmt_time(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def list_players():
    out = sh(["playerctl", "-l"])
    if not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def pick_player(players):
    lowered = [(player, player.lower()) for player in players]
    for prefix in PREFERRED_PREFIXES:
        for player, lowered_name in lowered:
            if lowered_name.startswith(prefix):
                return player
    return players[0] if players else None


def playerctl(player, *args):
    if not player:
        return None
    return sh(["playerctl", "-p", player, *args])


def ctl(player, cmd):
    if not player:
        return
    try:
        subprocess.Popen(
            ["playerctl", "-p", player, cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def smart_spotify(cmd):
    env = os.environ.copy()
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus")

    if SPOTIFY_CMD.exists() and os.access(SPOTIFY_CMD, os.X_OK):
        subprocess.Popen(
            [str(SPOTIFY_CMD), cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        return

    if cmd == "browser-back":
        try:
            subprocess.Popen(
                ["xdotool", "key", "Alt_L+Left"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
        except Exception:
            pass
        return

    player = pick_player(list_players())
    args = ["playerctl"]
    if player:
        args.extend(["-p", player])
    args.append(cmd)
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)


def get_state(player):
    status = playerctl(player, "status")
    if not status:
        return None

    playing = status.lower() == "playing"
    title = playerctl(player, "metadata", "xesam:title") or ""
    artist = (playerctl(player, "metadata", "xesam:artist") or "").strip("[]'\"")

    pos_seconds = 0.0
    pos = playerctl(player, "position")
    if pos:
        try:
            pos_seconds = float(pos)
        except ValueError:
            pos_seconds = 0.0

    duration_seconds = None
    length = playerctl(player, "metadata", "mpris:length")
    if length:
        try:
            duration_seconds = int(length) / 1_000_000.0
        except ValueError:
            duration_seconds = None

    art = playerctl(player, "metadata", "mpris:artUrl") or ""
    return {
        "playing": playing,
        "title": title,
        "artist": artist,
        "pos": pos_seconds,
        "dur": duration_seconds,
        "art": art,
    }


def fetch_album(url):
    if not url:
        return None
    try:
        if url.startswith("file://"):
            image = pygame.image.load(url[7:]).convert()
        else:
            with urllib.request.urlopen(url, timeout=5) as response:
                image = pygame.image.load(BytesIO(response.read())).convert()
        return pygame.transform.smoothscale(image, (ALBUM_SIZE, ALBUM_SIZE))
    except Exception:
        return None


def wpctl(*args):
    return sh(["wpctl", *map(str, args)])


def have_wpctl():
    return shutil.which("wpctl") is not None


def find_chromium_stream_id():
    out = wpctl("status")
    if not out:
        return None

    in_streams = False
    for line in out.splitlines():
        stripped = line.strip()
        if stripped in ("Streams:", "└─ Streams:"):
            in_streams = True
            continue

        if not in_streams:
            continue

        match = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
        if not match:
            continue

        stream_id = int(match.group(1))
        name = match.group(2).strip().lower()
        if "chromium" in name or "chrome" in name or "spotify" in name:
            return stream_id

    return None


def resolve_volume_target(force_refresh=False):
    global _last_stream_id, _last_stream_id_t

    if not have_wpctl():
        return None

    now = time.time()
    if force_refresh or _last_stream_id is None or (now - _last_stream_id_t) > STREAM_REFRESH_SEC:
        _last_stream_id = find_chromium_stream_id()
        _last_stream_id_t = now

    if _last_stream_id is not None:
        return str(_last_stream_id)
    return "@DEFAULT_AUDIO_SINK@"


def parse_wpctl_volume(output):
    if not output:
        return None

    match = re.search(r"Volume:\s*([0-9.]+)", output)
    if not match:
        return None

    return int(round(float(match.group(1)) * 100.0))


def get_audio_volume_percent():
    target = resolve_volume_target()
    if target is None:
        return None
    return parse_wpctl_volume(wpctl("get-volume", target))


def set_audio_volume_percent(volume):
    target = resolve_volume_target(force_refresh=True)
    if target is None:
        return
    wpctl("set-volume", target, f"{clamp(int(volume), 0, 100) / 100.0:.2f}")


def smoothstep01(value):
    value = clamp(value, 0.0, 1.0)
    return value * value * (3 - 2 * value)


def overlay_alpha(now, start_t, end_t):
    if now < start_t:
        return 0

    fade_in_end = start_t + VOL_FADE_IN
    hold_end = end_t - VOL_FADE_OUT

    if now <= fade_in_end:
        factor = (now - start_t) / max(0.0001, VOL_FADE_IN)
        return int(255 * smoothstep01(factor))

    if now <= hold_end:
        return 255

    if now <= end_t:
        factor = (now - hold_end) / max(0.0001, VOL_FADE_OUT)
        return int(255 * (1.0 - smoothstep01(factor)))

    return 0


def load_scaled_image(path, size):
    return pygame.transform.smoothscale(pygame.image.load(path).convert_alpha(), size)


def load_vinyl_surface(vinyl_path):
    return load_scaled_image(vinyl_path, (VINYL_SIZE, VINYL_SIZE))


def vinyl_label(vinyl_path):
    try:
        return str(vinyl_path.relative_to(ASSETS))
    except ValueError:
        return vinyl_path.name


def open_tonearm_bus():
    if smbus2 is None:
        log("AS5600 disabled: smbus2 is not installed.")
        return None

    try:
        bus = smbus2.SMBus(AS5600_BUS)
        log(f"AS5600 ready on I2C bus {AS5600_BUS} address {AS5600_ADDR:#04x}.")
        return bus
    except Exception as exc:
        log(f"AS5600 disabled: could not open I2C bus {AS5600_BUS} ({exc}).")
        return None


def read_angle_deg(bus):
    if bus is None:
        return None

    try:
        hi = bus.read_byte_data(AS5600_ADDR, AS5600_ANGLE_HI)
        lo = bus.read_byte_data(AS5600_ADDR, AS5600_ANGLE_LO)
        raw = ((hi << 8) | lo) & 0x0FFF
        return raw * 360.0 / 4096.0
    except Exception:
        return None


def normalize_arm_angle(angle):
    return (angle - ANGLE_OFFSET_DEG) % 360.0


def angular_distance_from_zero(angle):
    angle = normalize_arm_angle(angle)
    return min(angle, 360.0 - angle)


def use_active_range():
    return ACTIVE_RANGE_START_DEG is not None and ACTIVE_RANGE_END_DEG is not None


def angle_in_active_range(angle):
    if angle is None or not use_active_range():
        return False

    normalized = normalize_arm_angle(angle)
    start = ACTIVE_RANGE_START_DEG % 360.0
    end = ACTIVE_RANGE_END_DEG % 360.0

    if start <= end:
        return start <= normalized <= end
    return normalized >= start or normalized <= end


def classify_arm_state(angle, current_state):
    if angle is None:
        return current_state

    if use_active_range():
        return ARM_ACTIVE if angle_in_active_range(angle) else ARM_PARKED

    distance = angular_distance_from_zero(angle)
    if current_state == ARM_PARKED:
        return ARM_ACTIVE if distance >= PARK_EXIT_DEG else ARM_PARKED
    if current_state == ARM_ACTIVE:
        return ARM_PARKED if distance <= PARK_ENTER_DEG else ARM_ACTIVE
    return ARM_PARKED if distance <= PARK_ENTER_DEG else ARM_ACTIVE


def arm_and_spotify_in_sync(arm_state, spotify_state):
    if arm_state == ARM_PARKED:
        return spotify_state == SPOTIFY_PAUSED
    if arm_state == ARM_ACTIVE:
        return spotify_state == SPOTIFY_PLAYING
    return False


def spotify_state_name(state):
    return SPOTIFY_PLAYING if state and state["playing"] else SPOTIFY_PAUSED


def screen_mode_name(spotify_state):
    return SCREEN_VINYL if spotify_state == SPOTIFY_PLAYING else SCREEN_KIOSK


def format_status_line(angle, arm_state, spotify_state, screen_mode, volume):
    angle_text = "NA" if angle is None else f"{normalize_arm_angle(angle):0.1f}"
    raw_text = "NA" if angle is None else f"{angle:0.1f}"
    volume_text = "NA" if volume is None else str(int(round(volume)))
    arm_text = arm_state or "UNKNOWN"
    return f"angle={angle_text} raw={raw_text} arm={arm_text} spotify={spotify_state} screen={screen_mode} volume={volume_text}"


def open_rotary_encoder():
    if RotaryEncoder is None:
        log("Rotary encoder disabled: gpiozero is not installed.")
        return None

    try:
        rotary = RotaryEncoder(ROTARY_A, ROTARY_B, pull_up=True, max_steps=0, bounce_time=ROTARY_BOUNCE_TIME)
        log(f"Rotary encoder ready on GPIO {ROTARY_A}/{ROTARY_B}.")
        return rotary
    except TypeError:
        try:
            rotary = RotaryEncoder(ROTARY_A, ROTARY_B, max_steps=0, bounce_time=ROTARY_BOUNCE_TIME)
            log(f"Rotary encoder ready on GPIO {ROTARY_A}/{ROTARY_B}.")
            return rotary
        except TypeError:
            try:
                rotary = RotaryEncoder(ROTARY_A, ROTARY_B, max_steps=0)
                log(f"Rotary encoder ready on GPIO {ROTARY_A}/{ROTARY_B}.")
                return rotary
            except Exception as exc:
                log(f"Rotary encoder disabled: could not open GPIO pins {ROTARY_A}/{ROTARY_B} ({exc}).")
                return None
        except Exception as exc:
            log(f"Rotary encoder disabled: could not open GPIO pins {ROTARY_A}/{ROTARY_B} ({exc}).")
            return None
    except Exception as exc:
        log(f"Rotary encoder disabled: could not open GPIO pins {ROTARY_A}/{ROTARY_B} ({exc}).")
        return None


def create_display():
    try:
        return pygame.display.set_mode((SCREEN, SCREEN), pygame.FULLSCREEN)
    except pygame.error:
        return pygame.display.set_mode((SCREEN, SCREEN))


def run():
    pygame.init()
    screen = create_display()
    pygame.display.set_caption("Vinyl UI")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    font_title = pygame.font.Font(None, 48)
    font_artist = pygame.font.Font(None, 34)
    font_time = pygame.font.Font(None, 26)

    vinyl_paths = discover_vinyl_paths()
    vinyl_index = load_saved_vinyl_index(len(vinyl_paths))
    active_vinyl_path = vinyl_paths[vinyl_index]
    vinyl = load_vinyl_surface(active_vinyl_path)
    last_vinyl_mtime = active_vinyl_path.stat().st_mtime if active_vinyl_path.exists() else 0.0
    last_vinyl_check = 0.0
    vinyl_check_sec = 0.2

    play_img = load_scaled_image(ASSETS / "play.png", (BTN_SIZE, BTN_SIZE))
    pause_img = load_scaled_image(ASSETS / "pause.png", (BTN_SIZE, BTN_SIZE))
    next_img = load_scaled_image(ASSETS / "next.png", (BTN_SIZE, BTN_SIZE))
    back_img = load_scaled_image(ASSETS / "back.png", (BTN_SIZE, BTN_SIZE))

    cx = SCREEN // 2
    center = (cx, cx)

    back_r = back_img.get_rect(center=(cx - (BTN_SIZE + BTN_GAP), BTN_Y))
    play_r = play_img.get_rect(center=(cx, BTN_Y))
    next_r = next_img.get_rect(center=(cx + (BTN_SIZE + BTN_GAP), BTN_Y))
    bx = cx - PROG_W // 2

    spin_angle = 0.0
    last_poll = 0.0
    last_angle = None

    player = None
    last_player_check = 0.0

    state = None
    last_pos = 0.0
    last_pos_t = time.time()
    album = None
    last_art = ""

    overlay_start = -999.0
    overlay_end = -999.0
    overlay_target = 0.0
    overlay_display = 0.0
    last_vol = None
    last_vol_poll = 0.0
    last_trigger = -999.0

    vol_surface = pygame.Surface((VOL_W, 46), pygame.SRCALPHA)

    tonearm_bus = open_tonearm_bus()
    rotary = open_rotary_encoder()
    last_tonearm_poll = 0.0
    arm_state = None
    arm_candidate_state = None
    arm_candidate_since = 0.0
    startup_sync_pending = False
    last_rotary_steps = rotary.steps if rotary else 0
    last_status_line = None
    last_debug_log = 0.0

    def note_volume_change(value, now):
        nonlocal overlay_end, overlay_start, overlay_target, last_trigger, last_vol

        value = float(clamp(int(value), 0, 100))
        overlay_target = value
        if now < overlay_end:
            overlay_end = now + VOL_OVERLAY_HOLD + VOL_FADE_OUT
        elif (now - last_trigger) >= VOL_MIN_RETRIGGER:
            overlay_start = now
            overlay_end = now + VOL_FADE_IN + VOL_OVERLAY_HOLD + VOL_FADE_OUT
            last_trigger = now
        last_vol = value

    def cycle_skin():
        nonlocal active_vinyl_path, last_vinyl_mtime, vinyl, vinyl_index
        vinyl_index = (vinyl_index + 1) % len(vinyl_paths)
        active_vinyl_path = vinyl_paths[vinyl_index]
        vinyl = load_vinyl_surface(active_vinyl_path)
        last_vinyl_mtime = active_vinyl_path.stat().st_mtime if active_vinyl_path.exists() else 0.0
        try:
            save_saved_vinyl_index(vinyl_index)
        except Exception as exc:
            log(f"Could not save skin index ({exc}).")
        log(f"Vinyl skin -> {vinyl_label(active_vinyl_path)}")

    def apply_arm_state(new_arm_state, angle):
        nonlocal arm_state, arm_candidate_state, arm_candidate_since

        if new_arm_state is None or new_arm_state == arm_state:
            return

        arm_state = new_arm_state
        arm_candidate_state = None
        arm_candidate_since = 0.0

        cmd = "pause" if new_arm_state == ARM_PARKED else "play"
        log(
            f"Arm state -> {new_arm_state} at angle={normalize_arm_angle(angle):.1f} "
            f"raw={angle:.1f}; sending {cmd}."
        )
        smart_spotify(cmd)

    def adopt_initial_arm_state(new_arm_state, angle):
        nonlocal arm_state, arm_candidate_state, arm_candidate_since, startup_sync_pending

        arm_state = new_arm_state
        arm_candidate_state = None
        arm_candidate_since = 0.0
        startup_sync_pending = True
        log(
            f"Arm state initialized -> {new_arm_state} at angle={normalize_arm_angle(angle):.1f} "
            f"raw={angle:.1f}."
        )

    def handle_pointer_down(pos):
        if back_r.collidepoint(pos):
            ctl(player, "previous")
        elif next_r.collidepoint(pos):
            ctl(player, "next")
        elif play_r.collidepoint(pos):
            smart_spotify("play-pause")

    try:
        while True:
            now = time.time()
            dt = clock.get_time() / 1000.0
            current_volume = None

            if now - last_vinyl_check >= vinyl_check_sec:
                last_vinyl_check = now
                # The dedicated GPIO button service writes the selected skin index.
                selected_index = load_saved_vinyl_index(len(vinyl_paths))
                if selected_index != vinyl_index:
                    vinyl_index = selected_index
                    active_vinyl_path = vinyl_paths[vinyl_index]
                    vinyl = load_vinyl_surface(active_vinyl_path)
                    last_vinyl_mtime = active_vinyl_path.stat().st_mtime if active_vinyl_path.exists() else 0.0
                    log(f"Vinyl skin -> {vinyl_label(active_vinyl_path)}")
                try:
                    if active_vinyl_path.exists():
                        mtime = active_vinyl_path.stat().st_mtime
                        if mtime != last_vinyl_mtime:
                            vinyl = load_vinyl_surface(active_vinyl_path)
                            last_vinyl_mtime = mtime
                except Exception:
                    pass

            if now - last_player_check >= PLAYER_CHECK_SEC:
                last_player_check = now
                new_player = pick_player(list_players())
                if new_player != player:
                    player = new_player
                    state = None
                    last_art = ""
                    album = None

            if player and (now - last_poll >= POLL_SEC):
                last_poll = now
                new_state = get_state(player)
                if new_state:
                    state = new_state
                    last_pos = new_state["pos"]
                    last_pos_t = now
                    if new_state["art"] != last_art:
                        last_art = new_state["art"]
                        album = fetch_album(last_art)

            if tonearm_bus and (now - last_tonearm_poll) >= TONEARM_POLL_SEC:
                last_tonearm_poll = now
                last_angle = read_angle_deg(tonearm_bus)
                if last_angle is not None:
                    next_arm_state = classify_arm_state(last_angle, arm_state)
                    if arm_state is not None and next_arm_state == arm_state:
                        arm_candidate_state = None
                        arm_candidate_since = 0.0
                    elif arm_candidate_state != next_arm_state:
                        arm_candidate_state = next_arm_state
                        arm_candidate_since = now
                    elif (now - arm_candidate_since) >= TONEARM_STABLE_SEC:
                        if arm_state is None:
                            adopt_initial_arm_state(next_arm_state, last_angle)
                        else:
                            apply_arm_state(next_arm_state, last_angle)

            if rotary:
                steps = rotary.steps
                if steps != last_rotary_steps:
                    delta = steps - last_rotary_steps
                    last_rotary_steps = steps
                    current_volume = get_audio_volume_percent()
                    if current_volume is None and last_vol is not None:
                        current_volume = int(round(last_vol))
                    if current_volume is not None:
                        new_volume = clamp(
                            current_volume + (delta * ROTARY_STEP_PERCENT * ROTARY_DIRECTION),
                            0,
                            100,
                        )
                        if new_volume != current_volume:
                            set_audio_volume_percent(new_volume)
                            note_volume_change(new_volume, now)
                            log(f"Volume step={delta} volume={int(new_volume)}")

            spotify_state = spotify_state_name(state)
            screen_mode = screen_mode_name(spotify_state)
            playing = spotify_state == SPOTIFY_PLAYING
            pos = last_pos + (time.time() - last_pos_t if playing else 0.0)

            if startup_sync_pending and arm_state is not None:
                if arm_and_spotify_in_sync(arm_state, spotify_state):
                    startup_sync_pending = False
                elif arm_state == ARM_PARKED and spotify_state == SPOTIFY_PLAYING:
                    log("Startup sync: arm is PARKED while Spotify is PLAYING; sending pause.")
                    smart_spotify("pause")
                    startup_sync_pending = False
                elif arm_state == ARM_ACTIVE and spotify_state == SPOTIFY_PAUSED:
                    log("Startup sync: arm is ACTIVE while Spotify is PAUSED; sending play.")
                    smart_spotify("play")
                    startup_sync_pending = False

            if now - last_vol_poll >= VOL_POLL_SEC:
                last_vol_poll = now
                current_volume = get_audio_volume_percent()
                if current_volume is not None:
                    current_volume = float(clamp(current_volume, 0, 100))
                    if last_vol is None or abs(current_volume - last_vol) >= VOL_DEADBAND:
                        note_volume_change(current_volume, now)

            if dt > 0:
                factor = clamp(VOL_SMOOTH_SPEED * dt, 0.0, 1.0)
                overlay_display = overlay_display + (overlay_target - overlay_display) * factor

            status_volume = current_volume if current_volume is not None else last_vol
            status_line = format_status_line(last_angle, arm_state, spotify_state, screen_mode, status_volume)
            if status_line != last_status_line or (now - last_debug_log) >= DEBUG_STATUS_SEC:
                log(status_line)
                last_status_line = status_line
                last_debug_log = now

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return
                    if event.key == pygame.K_TAB and len(vinyl_paths) > 1:
                        cycle_skin()
                if event.type == pygame.FINGERDOWN:
                    handle_pointer_down((int(event.x * screen.get_width()), int(event.y * screen.get_height())))
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    handle_pointer_down(event.pos)

            screen.fill((10, 10, 10))

            rotated_vinyl = pygame.transform.rotate(vinyl, spin_angle)
            screen.blit(rotated_vinyl, rotated_vinyl.get_rect(center=center))
            if playing:
                spin_angle = (spin_angle + ANGLE_SPEED) % 360.0

            if album:
                album_pos = (center[0] + ALBUM_OFFSET_X, center[1] + ALBUM_OFFSET_Y)
                screen.blit(album, album.get_rect(center=album_pos))

            screen.blit(back_img, back_r)
            screen.blit(next_img, next_r)
            screen.blit(pause_img if playing else play_img, play_r)

            if state:
                title = state["title"] or " "
                artist = state["artist"] or " "

                tx = bx + TEXT_LEFT_PADDING
                title_y = PROG_Y - TITLE_Y_OFFSET
                artist_y = PROG_Y - ARTIST_Y_OFFSET

                title_surface = font_title.render(title, True, (235, 235, 235))
                artist_surface = font_artist.render(artist, True, (180, 180, 180))
                screen.blit(title_surface, (tx, title_y))
                screen.blit(artist_surface, (tx, artist_y))

                if state["dur"] and state["dur"] > 1:
                    frac = clamp(pos / state["dur"], 0.0, 1.0)
                    pygame.draw.rect(screen, (90, 90, 90), (bx, PROG_Y, PROG_W, PROG_H))
                    pygame.draw.rect(screen, (235, 235, 235), (bx, PROG_Y, int(PROG_W * frac), PROG_H))

                    left_time = font_time.render(fmt_time(pos), True, (200, 200, 200))
                    right_time = font_time.render(fmt_time(state["dur"]), True, (200, 200, 200))
                    screen.blit(left_time, (bx, PROG_Y + TIME_Y_OFFSET))
                    screen.blit(right_time, (bx + PROG_W - right_time.get_width(), PROG_Y + TIME_Y_OFFSET))

            alpha = overlay_alpha(now, overlay_start, overlay_end)
            if alpha > 0:
                vol_surface.fill((0, 0, 0, 0))
                vol_int = int(round(overlay_display))
                text = font_time.render(f"Volume {vol_int}%", True, (255, 255, 255))
                vol_surface.blit(text, (8, 0))

                bar_y = 28
                frac = clamp(overlay_display / 100.0, 0.0, 1.0)
                pygame.draw.line(vol_surface, (120, 120, 120, 255), (0, bar_y), (VOL_W, bar_y), VOL_LINE_THICK_BG)
                pygame.draw.line(vol_surface, (255, 255, 255, 255), (0, bar_y), (int(VOL_W * frac), bar_y), VOL_LINE_THICK_FG)

                vol_surface.set_alpha(alpha)
                screen.blit(vol_surface, ((SCREEN - VOL_W) // 2, VOL_Y))

            pygame.display.flip()
            clock.tick(FPS)
    finally:
        if rotary is not None:
            rotary.close()
        if tonearm_bus is not None:
            tonearm_bus.close()
        pygame.quit()


if __name__ == "__main__":
    run()
