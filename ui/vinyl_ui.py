#!/usr/bin/env python3
import pygame
import sys
import time
import subprocess
from io import BytesIO
import urllib.request
from pathlib import Path
import re
import shutil

# =========================
# EASY TUNING (edit these)
# =========================
SCREEN = 1080
FPS = 60

# Vinyl spin
ANGLE_SPEED = -0.5

# Polling (lower = faster UI updates, more CPU)
POLL_SEC = 0.25

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

PREFERRED_PREFIXES = ("chromium", "chrome")

# --- Volume Overlay (smooth + no flicker) ---
VOL_POLL_SEC = 0.12
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
# =========================

BASE = Path(__file__).resolve().parent
ASSETS = BASE / "ui_assets"

SPOTIFY_CMD = str(Path.home() / "bin" / "spotify_cmd.sh")


def sh(cmd):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return None


def list_players():
    out = sh(["playerctl", "-l"])
    if not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def pick_player(players):
    for p in players:
        pl = p.lower()
        if pl.startswith(PREFERRED_PREFIXES):
            return p
    return players[0] if players else None


def playerctl(player, *args):
    if not player:
        return None
    return sh(["playerctl", "-p", player, *args])


def ctl(player, cmd):
    if not player:
        return
    try:
        subprocess.Popen(["playerctl", "-p", player, cmd],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def smart_spotify(cmd):
    """Use smart play/pause wrapper (playerctl first, xdotool fallback)."""
    if shutil.which(SPOTIFY_CMD):
        subprocess.Popen([SPOTIFY_CMD, cmd],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        # fallback if script missing
        subprocess.Popen(["playerctl", cmd],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def clamp(v, a, b):
    return a if v < a else b if v > b else v


def fmt_time(s):
    s = max(0, int(s))
    return f"{s//60}:{s%60:02d}"


def get_state(player):
    status = playerctl(player, "status")
    if not status:
        return None

    playing = status.lower() == "playing"
    title = playerctl(player, "metadata", "xesam:title") or ""
    artist = (playerctl(player, "metadata", "xesam:artist") or "").strip("[]'\"")

    pos_s = 0.0
    pos = playerctl(player, "position")
    if pos:
        try:
            pos_s = float(pos)
        except ValueError:
            pos_s = 0.0

    dur_s = None
    length = playerctl(player, "metadata", "mpris:length")
    if length:
        try:
            dur_s = int(length) / 1_000_000.0
        except ValueError:
            dur_s = None

    art = playerctl(player, "metadata", "mpris:artUrl") or ""
    return {"playing": playing, "title": title, "artist": artist, "pos": pos_s, "dur": dur_s, "art": art}


def fetch_album(url):
    if not url:
        return None
    try:
        if url.startswith("file://"):
            img = pygame.image.load(url[7:]).convert()
        else:
            with urllib.request.urlopen(url, timeout=5) as r:
                img = pygame.image.load(BytesIO(r.read())).convert()
        return pygame.transform.smoothscale(img, (ALBUM_SIZE, ALBUM_SIZE))
    except Exception:
        return None


# ---------- Volume: PipeWire via wpctl (Chromium stream volume) ----------
_last_stream_id = None
_last_stream_id_t = 0.0
STREAM_REFRESH_SEC = 3.0


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


def get_chromium_volume_percent():
    global _last_stream_id, _last_stream_id_t

    if not have_wpctl():
        return None

    now = time.time()
    if _last_stream_id is None or (now - _last_stream_id_t) > STREAM_REFRESH_SEC:
        _last_stream_id = find_chromium_stream_id()
        _last_stream_id_t = now

    if _last_stream_id is None:
        return None

    out = wpctl("get-volume", _last_stream_id)
    if not out:
        return None

    m = re.search(r"Volume:\s*([0-9.]+)", out)
    if not m:
        return None

    vol_float = float(m.group(1))
    return int(round(vol_float * 100.0))


def smoothstep01(x):
    x = clamp(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def overlay_alpha(now, start_t, end_t):
    if now < start_t:
        return 0

    fade_in_end = start_t + VOL_FADE_IN
    hold_end = end_t - VOL_FADE_OUT

    if now <= fade_in_end:
        x = (now - start_t) / max(0.0001, VOL_FADE_IN)
        return int(255 * smoothstep01(x))

    if now <= hold_end:
        return 255

    if now <= end_t:
        x = (now - hold_end) / max(0.0001, VOL_FADE_OUT)
        return int(255 * (1.0 - smoothstep01(x)))

    return 0


def run():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN, SCREEN), pygame.FULLSCREEN)
    pygame.display.set_caption("Vinyl UI")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    font_title = pygame.font.Font(None, 48)
    font_artist = pygame.font.Font(None, 34)
    font_time = pygame.font.Font(None, 26)

    vinyl = pygame.image.load(ASSETS / "vinyl.png").convert_alpha()
    vinyl = pygame.transform.smoothscale(vinyl, (VINYL_SIZE, VINYL_SIZE))

    play_img = pygame.transform.smoothscale(pygame.image.load(ASSETS / "play.png").convert_alpha(), (BTN_SIZE, BTN_SIZE))
    pause_img = pygame.transform.smoothscale(pygame.image.load(ASSETS / "pause.png").convert_alpha(), (BTN_SIZE, BTN_SIZE))
    next_img = pygame.transform.smoothscale(pygame.image.load(ASSETS / "next.png").convert_alpha(), (BTN_SIZE, BTN_SIZE))
    back_img = pygame.transform.smoothscale(pygame.image.load(ASSETS / "back.png").convert_alpha(), (BTN_SIZE, BTN_SIZE))

    cx = SCREEN // 2
    center = (cx, cx)

    back_r = back_img.get_rect(center=(cx - (BTN_SIZE + BTN_GAP), BTN_Y))
    play_r = play_img.get_rect(center=(cx, BTN_Y))
    next_r = next_img.get_rect(center=(cx + (BTN_SIZE + BTN_GAP), BTN_Y))

    bx = cx - PROG_W // 2

    angle = 0.0
    last_poll = 0.0

    player = None
    last_player_check = 0.0
    PLAYER_CHECK_SEC = 1.0

    state = None
    last_pos = 0.0
    last_pos_t = time.time()

    album = None
    last_art = ""

    # ---- Volume overlay state ----
    overlay_start = -999.0
    overlay_end = -999.0
    overlay_target = 0.0
    overlay_display = 0.0
    last_vol = None
    last_vol_poll = 0.0
    last_trigger = -999.0

    vol_surface_h = 46
    vol_surface = pygame.Surface((VOL_W, vol_surface_h), pygame.SRCALPHA)

    while True:
        now = time.time()
        dt = clock.get_time() / 1000.0

        # player detect
        if now - last_player_check >= PLAYER_CHECK_SEC:
            last_player_check = now
            players = list_players()
            new_player = pick_player(players)
            if new_player != player:
                player = new_player
                state = None
                last_art = ""
                album = None

        # spotify state
        if player and (now - last_poll >= POLL_SEC):
            last_poll = now
            s = get_state(player)
            if s:
                state = s
                last_pos = s["pos"]
                last_pos_t = now
                if s["art"] != last_art:
                    last_art = s["art"]
                    album = fetch_album(last_art)

        playing = bool(state and state["playing"])
        pos = last_pos + (time.time() - last_pos_t if playing else 0.0)

        # volume poll
        if now - last_vol_poll >= VOL_POLL_SEC:
            last_vol_poll = now
            v = get_chromium_volume_percent()
            if v is not None:
                v = float(clamp(v, 0, 150))
                if last_vol is None or abs(v - last_vol) >= VOL_DEADBAND:
                    overlay_target = v
                    if now < overlay_end:
                        overlay_end = now + VOL_OVERLAY_HOLD + VOL_FADE_OUT
                    else:
                        if (now - last_trigger) >= VOL_MIN_RETRIGGER:
                            overlay_start = now
                            overlay_end = now + VOL_FADE_IN + VOL_OVERLAY_HOLD + VOL_FADE_OUT
                            last_trigger = now
                    last_vol = v

        # smooth displayed volume
        if dt > 0:
            k = clamp(VOL_SMOOTH_SPEED * dt, 0.0, 1.0)
            overlay_display = overlay_display + (overlay_target - overlay_display) * k

        # events
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                pygame.quit()
                return
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if back_r.collidepoint(e.pos):
                    ctl(player, "previous")
                elif next_r.collidepoint(e.pos):
                    ctl(player, "next")
                elif play_r.collidepoint(e.pos):
                    smart_spotify("play-pause")

        # draw
        screen.fill((10, 10, 10))

        rot = pygame.transform.rotate(vinyl, angle)
        screen.blit(rot, rot.get_rect(center=center))
        if playing:
            angle = (angle + ANGLE_SPEED) % 360.0

        if album:
            ap = (center[0] + ALBUM_OFFSET_X, center[1] + ALBUM_OFFSET_Y)
            screen.blit(album, album.get_rect(center=ap))

        screen.blit(back_img, back_r)
        screen.blit(next_img, next_r)
        screen.blit(pause_img if playing else play_img, play_r)

        if state:
            title = state["title"] or " "
            artist = state["artist"] or " "

            tx = bx + TEXT_LEFT_PADDING
            title_y = PROG_Y - TITLE_Y_OFFSET
            artist_y = PROG_Y - ARTIST_Y_OFFSET

            t = font_title.render(title, True, (235, 235, 235))
            a = font_artist.render(artist, True, (180, 180, 180))
            screen.blit(t, (tx, title_y))
            screen.blit(a, (tx, artist_y))

            if state["dur"] and state["dur"] > 1:
                frac = clamp(pos / state["dur"], 0.0, 1.0)
                pygame.draw.rect(screen, (90, 90, 90), (bx, PROG_Y, PROG_W, PROG_H))
                pygame.draw.rect(screen, (235, 235, 235), (bx, PROG_Y, int(PROG_W * frac), PROG_H))

                l = font_time.render(fmt_time(pos), True, (200, 200, 200))
                r = font_time.render(fmt_time(state["dur"]), True, (200, 200, 200))
                screen.blit(l, (bx, PROG_Y + TIME_Y_OFFSET))
                screen.blit(r, (bx + PROG_W - r.get_width(), PROG_Y + TIME_Y_OFFSET))

        # volume overlay
        alpha = overlay_alpha(now, overlay_start, overlay_end)
        if alpha > 0:
            vol_surface.fill((0, 0, 0, 0))

            vol_int = int(round(overlay_display))
            txt = font_time.render(f"Volume {vol_int}%", True, (255, 255, 255))
            vol_surface.blit(txt, (8, 0))

            bar_y = 28
            frac = clamp(overlay_display / 100.0, 0.0, 1.0)
            pygame.draw.line(vol_surface, (120, 120, 120, 255), (0, bar_y), (VOL_W, bar_y), VOL_LINE_THICK_BG)
            pygame.draw.line(vol_surface, (255, 255, 255, 255), (0, bar_y), (int(VOL_W * frac), bar_y), VOL_LINE_THICK_FG)

            vol_surface.set_alpha(alpha)
            x = (SCREEN - VOL_W) // 2
            y = VOL_Y
            screen.blit(vol_surface, (x, y))

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    run()
