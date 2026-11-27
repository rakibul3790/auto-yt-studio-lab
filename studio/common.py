"""Shared helpers: config loading, paths, logging, ffmpeg wrappers, fonts."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "scripts" / "queue"
DONE_DIR = ROOT / "scripts" / "done"
OUTPUT_DIR = ROOT / "output"
WORK_DIR = ROOT / "work"
MUSIC_DIR = ROOT / "assets" / "music"
LOG_FILE = ROOT / "logs" / "uploads.csv"


def log(msg: str) -> None:
    print(f"[studio] {msg}", flush=True)


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg.setdefault("channel", {})
    cfg.setdefault("video", {})
    cfg.setdefault("shorts", {})
    cfg.setdefault("run", {})
    return cfg


def run(cmd: list[str], cwd: Path | None = None) -> None:
    """Run a command; on failure show its output and stop."""
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.stderr.write(res.stdout[-3000:] + "\n" + res.stderr[-6000:] + "\n")
        raise RuntimeError(f"Command failed: {' '.join(cmd[:4])} ...")


def media_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def require_tools() -> None:
    for tool in ("ffmpeg", "ffprobe", "fc-match"):
        if not shutil.which(tool):
            raise SystemExit(f"'{tool}' is not installed. See README.")


def has_bengali(text: str) -> bool:
    return any("ঀ" <= ch <= "৿" for ch in text)


@lru_cache(maxsize=None)
def font_file(family: str, bold: bool = True) -> str:
    """Find a font file through fontconfig (works on GitHub's Ubuntu runner)."""
    pattern = f"{family}:bold" if bold else family
    out = subprocess.run(["fc-match", "-f", "%{file}", pattern],
                         capture_output=True, text=True).stdout.strip()
    if not out:
        raise SystemExit(f"Font '{family}' not found. Install fonts-noto-core.")
    return out


def font_family_for(text: str) -> str:
    return "Noto Sans Bengali" if has_bengali(text) else "Noto Sans"
