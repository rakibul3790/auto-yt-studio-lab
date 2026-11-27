"""Automatic quality check for a finished video.

Looks at the real output file, not at what the renderer meant to do:
- size, frame rate, audio stream present
- black frames (blackdetect) and frozen picture (freezedetect)
- loudness (EBU R128: integrated LUFS and true peak) and long silences
- captions inside the safe area (boxes reported by the caption writer)

Errors mean "don't upload this"; warnings are written down for a look.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .common import log


def safe_area(size: tuple[int, int]) -> tuple[float, float, float, float]:
    """Where text may go on a Short: clear of the edges, the top bar and the
    bottom title/description area of the YouTube Shorts player."""
    w, h = size
    return (w * 0.04, h * 0.10, w * 0.96, h * 0.80)


def _ffmpeg_log(args: list[str]) -> str:
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args], capture_output=True, text=True).stderr


def check(path: Path, size: tuple[int, int], fps: int, boxes: list[tuple] | None = None,
          safe: tuple[float, float, float, float] | None = None) -> dict:
    errors, warnings, info = [], [], {}
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True).stdout or "{}")
    streams = probe.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    dur = float(probe.get("format", {}).get("duration", 0) or 0)
    info["duration"] = round(dur, 2)
    if not v:
        errors.append("no video stream")
    else:
        info["size"] = f"{v.get('width')}x{v.get('height')}"
        if (int(v.get("width", 0)), int(v.get("height", 0))) != tuple(size):
            errors.append(f"size is {info['size']}, expected {size[0]}x{size[1]}")
        num, _, den = str(v.get("avg_frame_rate", "0/1")).partition("/")
        rate = float(num) / float(den or 1) if float(den or 1) else 0
        info["fps"] = round(rate, 2)
        if abs(rate - fps) > 0.5:
            errors.append(f"frame rate {rate:.2f}, expected {fps}")
    if not a:
        errors.append("no audio stream")

    # black and frozen picture
    out = _ffmpeg_log(["-i", str(path), "-vf", "blackdetect=d=0.12:pic_th=0.93:pix_th=0.08,"
                       "freezedetect=n=-60dB:d=1.5", "-an", "-f", "null", "-"])
    blacks = [(float(s), float(e)) for s, e in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", out)]
    info["black"] = blacks
    for s, e in blacks:
        (errors if e - s >= 0.25 else warnings).append(f"black picture {s:.2f}-{e:.2f}s")
    fs = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", out)]
    fe = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", out)]
    for k, s in enumerate(fs):
        e = fe[k] if k < len(fe) else dur
        warnings.append(f"picture frozen {s:.2f}-{e:.2f}s")

    # loudness and silence
    if a:
        out = _ffmpeg_log(["-i", str(path), "-vn", "-af", "ebur128=peak=true,silencedetect=n=-45dB:d=0.9",
                           "-f", "null", "-"])
        m = re.findall(r"I:\s+(-?[\d.]+) LUFS", out)
        p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", out)
        lufs = float(m[-1]) if m else None
        peak = float(p[-1]) if p else None
        info["lufs"], info["true_peak"] = lufs, peak
        if lufs is None:
            warnings.append("could not measure loudness")
        elif abs(lufs + 14) > 2:
            errors.append(f"loudness {lufs:.1f} LUFS (target -14)")
        elif abs(lufs + 14) > 1:
            warnings.append(f"loudness {lufs:.1f} LUFS (target -14)")
        if peak is not None and peak > -0.5:
            errors.append(f"true peak {peak:.1f} dBFS (clipping risk)")
        sil = [(float(s), float(e)) for s, e in zip(re.findall(r"silence_start: ([\d.]+)", out),
                                                    re.findall(r"silence_end: ([\d.]+)", out))]
        for s, e in sil:
            warnings.append(f"silence {s:.2f}-{e:.2f}s")

    # captions inside the safe area
    if boxes and safe:
        x0, y0, x1, y1 = safe
        bad = [b for b in boxes if b[0] < x0 or b[1] < y0 or b[2] > x1 or b[3] > y1]
        info["caption_boxes"] = len(boxes)
        if bad:
            errors.append(f"{len(bad)} caption box(es) outside the safe area, e.g. "
                          f"{tuple(round(v) for v in bad[0])}")
    return {"file": path.name, "ok": not errors, "errors": errors, "warnings": warnings, "info": info}


def log_report(r: dict) -> None:
    i = r["info"]
    log(f"Quality check {r['file']}: {'OK' if r['ok'] else 'PROBLEMS'} | {i.get('size')} {i.get('fps')}fps "
        f"{i.get('duration')}s | {i.get('lufs')} LUFS, peak {i.get('true_peak')} dBFS")
    for e in r["errors"]:
        log(f"  ERROR: {e}")
    for w in r["warnings"]:
        log(f"  note: {w}")
