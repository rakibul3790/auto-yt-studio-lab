"""Daily runner.

    python -m studio.main                 # make + upload the next video(s)
    python -m studio.main --no-upload     # only render (test), keep the queue
    python -m studio.main --validate      # check every script in the queue
    python -m studio.main --file scripts/queue/001-sample.json --no-upload
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import queue
from .common import OUTPUT_DIR, WORK_DIR, load_config, log, require_tools


def music_credit(track: str | None) -> str:
    """The credit line a CC BY music track needs (assets/music/CREDITS.txt)."""
    from .common import MUSIC_DIR
    f = MUSIC_DIR / "CREDITS.txt"
    if not track or not f.exists():
        return ""
    for line in f.read_text(encoding="utf-8").splitlines():
        name, _, credit = line.partition("|")
        if name.strip() == track:
            return "Music: " + credit.strip()
    return ""


def _hashtag(t) -> str:
    t = "".join(ch for ch in str(t).lstrip("#") if ch.isalnum() or ch == "_")
    return f"#{t}" if t else ""


def hashtags_for(data: dict, cfg: dict, shorts: bool) -> list[str]:
    """Script hashtags first, then the channel's, at most 5, no duplicates."""
    raw = list(data.get("hashtags") or []) + list(cfg["channel"].get("default_hashtags") or [])
    if shorts:
        raw.insert(0, "Shorts")
    out, seen = [], set()
    for t in raw:
        h = _hashtag(t)
        if not h or (h.lower() == "#shorts" and not shorts) or h.lower() in seen:
            continue
        seen.add(h.lower())
        out.append(h)
    return out[:5]


def tags_for(data: dict, cfg: dict, shorts: bool) -> list[str]:
    """The script's own topic tags first, then broad channel tags; 15 at most."""
    raw = list(data.get("tags") or []) + list(cfg["channel"].get("default_tags") or [])
    out, seen = [], set()
    for t in raw:
        t = str(t).strip().lstrip("#")
        k = t.lower()
        if not t or k in seen or (k == "shorts" and not shorts):
            continue
        seen.add(k)
        out.append(t)
    return out[:15]


def description_for(data: dict, cfg: dict, shorts: bool = False, credit: str = "") -> str:
    desc = str(data.get("description", "")).strip()
    parts = []
    # The first spoken line is the hook; it leads the description when it adds something
    scenes = data.get("scenes") or []
    hook = str(scenes[0].get("text", "")).strip() if scenes else ""
    if len(hook.split()) >= 6 and hook.lower() not in desc.lower():
        parts.append(hook)
    parts.append(desc)
    footer = str(cfg["channel"].get("description_footer", "") or "").strip()
    if footer:
        parts.append(footer)
    tags = hashtags_for(data, cfg, shorts)
    if tags:
        parts.append(" ".join(tags))
    if credit:
        parts.append(credit)
    return "\n\n".join(p for p in parts if p)


def uploads_today(cfg: dict) -> int:
    """Queue videos already uploaded today, by the Bangladesh calendar day (UTC+6).

    Counts rows of logs/uploads.csv written by the daily runner (bare script names,
    not test files that start with _ and not ready-*/ uploads)."""
    import csv
    from datetime import datetime, timedelta, timezone
    from .common import LOG_FILE
    if not LOG_FILE.exists():
        return 0
    tz = timezone(timedelta(hours=6))
    today = datetime.now(tz).date()
    n = 0
    with open(LOG_FILE, encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) < 2 or "/" in row[1] or row[1].startswith("_") or not row[1].endswith(".json"):
                continue
            try:
                t = datetime.strptime(row[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if t.astimezone(tz).date() == today:
                n += 1
    return n


def process(path: Path, cfg: dict, upload: bool, voice: str | None = None) -> None:
    from . import render, visuals, voices, youtube   # heavy imports only when rendering

    data = queue.load(path)
    # Voice: a voice asked for by name (not counted in the test), else the voice test's turn
    test_voice = None
    if voice:
        chosen = voices.find(cfg, voice)
        if chosen is None:
            chosen = {"label": voice, "voice": voice}
        cfg = voices.apply(cfg, chosen)
    else:
        test_voice = voices.next_voice(cfg)
        cfg = voices.apply(cfg, test_voice)
    slug = path.stem
    work = WORK_DIR / slug
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    vcfg, scfg = cfg["video"], cfg["shorts"]

    short_only = str(data.get("format", "")).lower() == "short"

    # ---- main 16:9 video (skipped for "format": "short" scripts)
    main_mp4 = thumb = None
    credit = ""
    if not short_only:
        size = (int(vcfg.get("width", 1920)), int(vcfg.get("height", 1080)))
        main_mp4 = OUTPUT_DIR / f"{slug}.mp4"
        info = render.render(data, cfg, work, main_mp4, size)
        credit = music_credit(info.get("music"))
        if len(info.get("chapters") or []) >= 3:       # YouTube chapters (first one must be 0:00)
            ch = info["chapters"]
            lines = [f"{'0:00' if k == 0 else f'{int(t0 // 60)}:{int(t0 % 60):02d}'} {name}" for k, (t0, name) in enumerate(ch)]
            data = {**data, "description": str(data.get("description", "")).rstrip() + "\n\nChapters\n" + "\n".join(lines)}
        if data.get("thumbnail_spec") and info.get("first_image"):     # a ready drawn thumbnail
            thumb = OUTPUT_DIR / f"{slug}-thumb.jpg"
            shutil.copy(info["first_image"], thumb)
        else:
            thumb = visuals.thumbnail(data, info["first_image"], OUTPUT_DIR / f"{slug}-thumb.jpg")

    # ---- 9:16 Short (always for "format": "short", else optional)
    short_mp4 = None
    if short_only or data.get("shorts", scfg.get("enabled", False)):
        short_mp4 = OUTPUT_DIR / f"{slug}-short.mp4"
        sinfo = render.render(data, cfg, work, short_mp4, (1080, 1920),
                              max_seconds=float(scfg.get("max_seconds", 180)) - 1)
        credit = credit or music_credit(sinfo.get("music"))

    if not upload:
        log(f"Test render done (not uploaded): {main_mp4 or short_mp4}")
        return

    result = {"uploaded_at": queue.now_utc()}
    if short_only:
        st = data.get("short_title") or data["title"]
        if "#shorts" not in st.lower() and len(st) <= 92:
            st += " #Shorts"
        sid = youtube.upload(short_mp4, st, description_for(data, cfg, shorts=True, credit=credit), tags_for(data, cfg, True), cfg)
        result["short_id"] = sid
        result["short_url"] = f"https://youtube.com/shorts/{sid}"
        short_mp4 = None                      # already uploaded
    else:
        vid = youtube.upload(main_mp4, data["title"], description_for(data, cfg, credit=credit), tags_for(data, cfg, False), cfg, thumb)
        result["video_id"] = vid
        result["video_url"] = f"https://youtu.be/{vid}"
    if short_mp4:
        st = data.get("short_title") or data["title"]
        if "#shorts" not in st.lower() and len(st) <= 92:
            st += " #Shorts"
        try:
            sid = youtube.upload(short_mp4, st, description_for(data, cfg, shorts=True, credit=credit), tags_for(data, cfg, True), cfg)
            result["short_id"] = sid
            result["short_url"] = f"https://youtube.com/shorts/{sid}"
        except Exception as e:  # main video is already up: don't upload it twice
            log(f"Short upload failed: {e}")
            result["short_error"] = str(e)[:300]
    queue.mark_done(path, data, result)
    if test_voice:
        voices.record(test_voice, path.name, data["title"],
                      result.get("short_url") or result.get("video_url", ""))
    shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Auto YT Studio")
    ap.add_argument("--count", type=int, default=None, help="videos to make now")
    ap.add_argument("--no-upload", action="store_true", help="render only")
    ap.add_argument("--validate", action="store_true", help="check queue files")
    ap.add_argument("--file", type=Path, help="process just this script file")
    ap.add_argument("--voice", help="use this voice (a label from voice_test, or a voice name)")
    args = ap.parse_args()

    cfg = load_config()

    if args.validate:
        files = [args.file] if args.file else queue.pending()
        bad = videos = 0
        for f in files:
            try:
                for d in queue.check_file(f):
                    videos += 1
                    log(f"OK   {f.name}: {d['title']} ({len(d['scenes'])} scenes)")
            except queue.ScriptError as e:
                bad += 1
                log(f"FAIL {e}")
        log(f"{videos} video(s) ready, {bad} file(s) with problems")
        return 1 if bad else 0

    if not args.file:
        queue.explode_batches()
    files = [args.file] if args.file else queue.pending()

    require_tools()
    if not files:
        log("The queue is empty: add new script files to scripts/queue/")
        return 2 if cfg["run"].get("fail_when_queue_empty", True) else 0

    from . import youtube

    upload = not args.no_upload
    if upload and not youtube.credentials_present():
        log("YouTube secrets are not set yet, so this is a TEST run (no upload).")
        upload = False

    count = args.count or int(cfg["run"].get("videos_per_run", 1))
    cap = int(cfg["run"].get("max_uploads_per_day", 0) or 0)
    if upload and cap:
        already = uploads_today(cfg)
        left = max(0, cap - already)
        if left == 0:
            log(f"Already {already} video(s) uploaded today (Bangladesh time), the daily "
                f"limit is {cap}. Nothing to do this run.")
            return 0
        if count > left:
            log(f"{already} uploaded today, limit {cap}: making {left} now instead of {count}.")
            count = left
    done = 0
    for f in files:
        if done >= count:
            break
        try:
            log(f"=== {f.name} ===")
            process(f, cfg, upload, args.voice)
            done += 1
        except queue.ScriptError as e:
            log(f"Skipping broken script: {e}")
            queue.copy_to_failed(f)
        except Exception as e:
            if str(e).startswith("Quality check failed"):
                # a broken render is never uploaded; park the script and make the next one
                print(f"::warning title=Quality check failed::{f.name}: {e}. Moved to "
                      "scripts/queue/_failed, the next script is made instead.", flush=True)
                queue.copy_to_failed(f)
                continue
            if "uploadLimitExceeded" not in str(e):
                raise
            # YouTube's daily upload cap for this channel is used up. The script
            # stays in the queue and goes up on the next run; nothing is lost.
            print("::error title=YouTube daily upload limit reached::"
                  f"{f.name} was rendered but YouTube refused the upload because "
                  "the channel has used its daily upload allowance. It stays in "
                  "the queue and will upload on the next run.", flush=True)
            return 1
    log(f"Finished: {done} video(s)")
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
