"""Voice test: alternate voices video by video for a set number of days.

config.yaml -> voice_test: enabled, days, voices [{label, voice, rate, pitch}]
Every uploaded video is written to logs/voice-test.csv, and the next video takes
the next voice in the list, so a new day carries on where the last day stopped.
"""
from __future__ import annotations

import copy
import csv
from datetime import datetime, timezone

from .common import ROOT, log

TEST_LOG = ROOT / "logs" / "voice-test.csv"
FIELDS = ["date_utc", "time_utc", "script", "title", "voice_label", "voice", "url"]


def _rows() -> list[dict]:
    if not TEST_LOG.exists():
        return []
    with open(TEST_LOG, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _voices(cfg: dict) -> list[dict]:
    return [v for v in ((cfg.get("voice_test") or {}).get("voices") or []) if v.get("voice")]


def find(cfg: dict, label: str) -> dict | None:
    """A voice from the test list by its label or voice name (any case, part of it)."""
    label = label.strip().lower()
    for v in _voices(cfg):
        if label in str(v.get("label", "")).lower() or label in v["voice"].lower():
            return v
    return None


def test_running(cfg: dict) -> bool:
    vt = cfg.get("voice_test") or {}
    if not vt.get("enabled") or len(_voices(cfg)) < 2:
        return False
    limit = int(vt.get("days", 10) or 0)
    if limit <= 0:                     # 0 = keep alternating for good
        return True
    days = {r["date_utc"] for r in _rows()} | {_today()}
    return len(days) <= limit


def next_voice(cfg: dict) -> dict | None:
    """The voice the next video should use while the test runs, else None."""
    if not test_running(cfg):
        return None
    voices = _voices(cfg)
    return voices[len(_rows()) % len(voices)]


def apply(cfg: dict, v: dict | None) -> dict:
    """A copy of cfg that speaks with voice v (cfg itself if v is None)."""
    if not v:
        return cfg
    out = copy.deepcopy(cfg)
    ch = out.setdefault("channel", {})
    ch["voice"] = v["voice"]
    ch["voice_rate"] = str(v.get("rate", "+0%"))
    ch["voice_pitch"] = str(v.get("pitch", "+0Hz"))
    log(f"Voice: {v.get('label') or v['voice']}")
    return out


def record(v: dict, script: str, title: str, url: str) -> None:
    new = not TEST_LOG.exists()
    TEST_LOG.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    with open(TEST_LOG, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({"date_utc": now.strftime("%Y-%m-%d"), "time_utc": now.strftime("%H:%M"),
                    "script": script, "title": title, "voice_label": v.get("label", ""),
                    "voice": v["voice"], "url": url})
