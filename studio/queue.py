"""The script queue: JSON files in scripts/queue/.

A file can hold ONE video (a JSON object) or MANY videos (a JSON list of
objects, e.g. a batch of 10 that Claude wrote). Batches are split into one
file per video at the start of each run.

Files are processed in name order (001-..., 002-..., ...). After a video is
uploaded, its file moves to scripts/done/ with the YouTube link added.
"""
from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .common import DONE_DIR, LOG_FILE, QUEUE_DIR

REQUIRED = ("title", "scenes")


class ScriptError(ValueError):
    pass


def validate(data: dict, name: str) -> None:
    for key in REQUIRED:
        if not data.get(key):
            raise ScriptError(f"{name}: '{key}' is missing")
    if not isinstance(data["scenes"], list):
        raise ScriptError(f"{name}: 'scenes' must be a list")
    for i, sc in enumerate(data["scenes"], 1):
        if not isinstance(sc, dict) or not (str(sc.get("text", "")).strip() or sc.get("hold")):
            raise ScriptError(f"{name}: scene {i} has no 'text'")
        hl = sc.get("highlight", [])
        hl = [hl] if isinstance(hl, str) else hl
        if not isinstance(hl, list):
            raise ScriptError(f"{name}: scene {i} 'highlight' must be a list of words")
        spoken = " ".join(str(sc.get("text", "")).lower().split())
        for ph in hl:
            ph = " ".join(str(ph).lower().split())
            if ph and ph not in spoken:
                raise ScriptError(f"{name}: scene {i} highlight '{ph}' is not in the spoken text")
            if len(ph) > 26:
                raise ScriptError(f"{name}: scene {i} highlight '{ph}' is too long (max about 3 words)")
    if len(data["title"]) > 100:
        raise ScriptError(f"{name}: title is longer than 100 characters")
    if "<" in data["title"] or ">" in data["title"]:
        raise ScriptError(f"{name}: title cannot contain < or >")


def load(path: Path) -> dict:
    data = _read(path)
    if not isinstance(data, dict):
        raise ScriptError(f"{path.name}: expected one video (a JSON object)")
    validate(data, path.name)
    return data


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ScriptError(f"{path.name}: not valid JSON ({e})") from e


def check_file(path: Path) -> list[dict]:
    """Validate a single or batch file without changing anything."""
    data = _read(path)
    items = data if isinstance(data, list) else [data]
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ScriptError(f"{path.name}: item {i} is not an object")
        validate(item, f"{path.name}" + (f" #{i}" if isinstance(data, list) else ""))
    return items


def explode_batches() -> None:
    """Turn every batch file (a list) into one file per video."""
    for path in pending():
        data = _read(path)
        if not isinstance(data, list):
            continue
        for i, item in enumerate(data, 1):
            target = path.with_name(f"{path.stem}-{i:02d}.json")
            target.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        path.unlink()


def pending() -> list[Path]:
    return sorted(p for p in QUEUE_DIR.glob("*.json") if not p.name.startswith("_"))


def mark_done(path: Path, data: dict, result: dict) -> Path:
    """Move a script to scripts/done/ and log the upload."""
    data = dict(data)
    data["result"] = result
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    target = DONE_DIR / path.name
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    path.unlink()

    new_file = not LOG_FILE.exists()
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["uploaded_at_utc", "file", "title", "video_url", "short_url"])
        w.writerow([result.get("uploaded_at"), path.name, data["title"],
                    result.get("video_url", ""), result.get("short_url", "")])
    return target


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def copy_to_failed(path: Path) -> None:
    """Keep a broken script out of the way so the queue keeps moving."""
    bad = QUEUE_DIR / "_failed"
    bad.mkdir(exist_ok=True)
    shutil.move(str(path), bad / path.name)
