import hashlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ASSETS = REPO_ROOT / "assets" / "ui_assets"
SKIN_INDEX_PATH = ASSETS / ".vinyl_skin_index"
LEGACY_SKIN_INDEX_PATH = ASSETS / ".skin_index"
RUNTIME_DIR = REPO_ROOT / "runtime"
SETUP_MODE_FLAG = RUNTIME_DIR / "setup_mode.flag"


def _file_signature(path):
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_vinyl_paths():
    paths = []
    seen_signatures = set()
    for name in ("vinyl.png", "vinyl1.png", "vinyl4.png"):
        path = ASSETS / name
        if path.is_file():
            signature = _file_signature(path)
            if signature not in seen_signatures:
                paths.append(path)
                seen_signatures.add(signature)

    skin_dir = ASSETS / "vinyl_skins"
    if skin_dir.exists():
        for path in sorted(skin_dir.glob("*.png")):
            signature = _file_signature(path)
            if signature not in seen_signatures:
                paths.append(path)
                seen_signatures.add(signature)

    if not paths:
        raise FileNotFoundError(f"No vinyl artwork found under {ASSETS}")

    return paths


def load_saved_vinyl_index(total):
    if total <= 0:
        return 0

    for path in (SKIN_INDEX_PATH, LEGACY_SKIN_INDEX_PATH):
        try:
            if path.exists():
                return int(path.read_text().strip() or "0") % total
        except Exception:
            pass

    return 0


def _write_text_atomically(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f"{path.name}.tmp"
    tmp_path.write_text(text)
    tmp_path.replace(path)


def save_saved_vinyl_index(index):
    text = f"{int(index)}\n"
    _write_text_atomically(SKIN_INDEX_PATH, text)

    if LEGACY_SKIN_INDEX_PATH.exists():
        try:
            _write_text_atomically(LEGACY_SKIN_INDEX_PATH, text)
        except Exception:
            pass


def is_setup_mode_forced():
    return SETUP_MODE_FLAG.exists()


def set_setup_mode_forced(enabled):
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if enabled:
        _write_text_atomically(SETUP_MODE_FLAG, "1\n")
    elif SETUP_MODE_FLAG.exists():
        SETUP_MODE_FLAG.unlink()
