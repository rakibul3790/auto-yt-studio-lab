"""Professional Shorts renderer ("style": "pro", 1080x1920).

What it does differently from the plain photo style:

- Every scene is cut into beats (studio/director.py, or the "beats" a script
  written with the MindBlip director skill carries), so the picture changes every
  2-3 seconds, on a word.
- Real stock VIDEO first (Pexels portrait clips, then Pixabay), photos only as a
  fallback, each shot with its own camera move (push in, pull out, pans, tilts,
  snap "punch" zoom with a small shake), a light colour grade and a vignette.
- Numbers and comparisons become animated graphics (count-up, growing bars) and a
  twist line can become a kinetic title card.
- Varied transitions on the idea changes (whip pan with motion blur, zoom, slide,
  white flash, glitch, fade), hard cuts inside an idea.
- Captions pop in word by word exactly when each word is spoken (Montserrat
  ExtraBold, thick outline and soft shadow); the key words land on a yellow pill
  that pops in behind them.
- Sound design (whoosh, swish, pop, riser, impact, glitch, ticks), music picked by
  mood and ducked under the voice, the whole mix loudness-normalised for YouTube
  (-14 LUFS, true peak -1.5 dB).
- An automatic quality check at the end (studio/qc.py).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import cards, director, framing, qc, shotpick, tts, visuals
from .common import MUSIC_DIR, ROOT, log, media_duration, run

FONT_DIR = ROOT / "assets" / "fonts"
FONT = FONT_DIR / "Montserrat.ttf"          # Montserrat ExtraBold
ASS_FONT = "Montserrat ExtraBold"
ASS_K = 0.628     # libass draws Montserrat at about 0.628 x the size PIL uses (measured)
SR = 48000
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p"]

TRANSITION_LEN = {"cut": 0.0, "whip_left": 0.22, "whip_right": 0.22, "zoom": 0.30, "slide_up": 0.26,
                  "flash": 0.30, "glitch": 0.20, "fade": 0.45}
XFADE = {"whip_left": "slideleft", "whip_right": "slideright", "zoom": "circleopen", "slide_up": "slideup",
         "flash": "fadewhite", "glitch": "pixelize", "fade": "fade"}
MOOD_TRACKS = {
    "mysterious": ["investigations.mp3", "sneaky-snitch.mp3", "hitman.mp3", "spy-glass.mp3", "sneaky-adventure.mp3"],
    "quirky": ["fluffing-a-duck.mp3", "pixel-peeker-polka---faster.mp3", "monkeys-spinning-monkeys.mp3",
               "scheming-weasel-faster.mp3", "quirky-dog.mp3", "merry-go.mp3"],
    "upbeat": ["life-of-riley.mp3", "carefree.mp3", "funkorama.mp3", "hep-cats.mp3", "daily-beetle.mp3"],
    "calm": ["wallpaper.mp3", "local-forecast---elevator.mp3", "wholesome.mp3", "bossa-antigua.mp3", "carefree.mp3"],
    "epic": ["inspired.mp3", "hitman.mp3", "investigations.mp3", "spy-glass.mp3"],
}
YELLOW = (255, 214, 10)
MIN_SHOT = 0.7


def _seed(*parts) -> int:
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def _font(px: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), max(int(px), 8))


# =================================================================== render
def render(data: dict, cfg: dict, work: Path, out_file: Path, size: tuple[int, int],
           max_seconds: float | None = None) -> dict:
    vcfg = cfg["video"]
    fps = int(vcfg.get("fps", 30))
    w, h = size
    work.mkdir(parents=True, exist_ok=True)
    data = _with_follow(data, cfg)
    data = director.plan(data)
    data = _feelings(data)
    data["_keep"] = str(vcfg.get("pro_framing", "")).lower() == "keep"
    data["_fit_style"] = str(vcfg.get("pro_fit_style", "box")).lower()
    data["_gen_used"] = []
    (work / "plan.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    visuals.reset_clips()
    _USED.clear()
    shotpick._USED.clear()
    shotpick.BANNED.clear()
    shotpick.STRICT_FILL = data["_fit_style"] == "refill"
    data.pop("_gen_used", None)
    data["_gen_used"] = []

    # ---- voice, scene by scene, with the time of every word
    whole_cfg = data.get("eleven_whole", vcfg.get("eleven_whole", False))
    if str(cfg["channel"].get("voice", "")).startswith("elevenlabs:") and not data.get("voice_cache"):
        # a paid voice that fails must never cost the day's video: fall back to the free voice
        reason = ""
        if not os.environ.get("ELEVENLABS_API_KEY", "").strip():
            reason = "ELEVENLABS_API_KEY is not set"
        elif whole_cfg:
            try:
                tag0 = re.sub(r"[^A-Za-z0-9]", "", str(cfg["channel"].get("voice", "")))[:24]
                _eleven_whole({**data, "scenes": data["scenes"]}, cfg, work, tag0,
                              _pct(data.get("voice_rate", cfg["channel"].get("voice_rate", "+0%"))),
                              str(data.get("voice_pitch", cfg["channel"].get("voice_pitch", "+0Hz"))))
            except Exception as e:
                reason = f"{type(e).__name__}: {e}"
        if reason:
            fb = str(cfg["channel"].get("voice_fallback") or "en-US-AndrewNeural")
            print(f"::warning title=ElevenLabs voice not used::{reason}. This video uses the free "
                  f"voice {fb} instead.", flush=True)
            log(f"ElevenLabs failed ({reason}); falling back to {fb}")
            cfg = {**cfg, "channel": {**cfg["channel"], "voice": fb,
                                      "voice_rate": cfg["channel"].get("voice_fallback_rate", "+0%")}}
            data = {**data, "voice_rate": cfg["channel"]["voice_rate"]}
    voice_tag = re.sub(r"[^A-Za-z0-9]", "", str(cfg["channel"].get("voice", "")))[:24]
    data["_voice"] = str(cfg["channel"].get("voice", ""))
    v3 = (work / "voice_v3.txt").exists() or bool(data.get("voice_cache"))
    # a v3 read (or a ready-made one) keeps its own breaths, laughs and timing: no trims, no gaps
    pause = float(data.get("scene_pause", 0.0 if v3 else vcfg.get("pro_scene_pause", 0.12)))
    words: list[dict] = []            # absolute times
    scene_t: list[tuple[float, float]] = []
    parts: list[Path] = []
    t0 = 0.0
    edge = str(cfg["channel"].get("voice", "")).split(":")[0] not in ("kokoro", "chatterbox") and not v3
    base_rate = _pct(data.get("voice_rate", cfg["channel"].get("voice_rate", "+0%")))
    base_pitch = str(data.get("voice_pitch", cfg["channel"].get("voice_pitch", "+0Hz")))
    eleven = str(cfg["channel"].get("voice", "")).startswith("elevenlabs:") and bool(whole_cfg)
    # lines already made (a paid voice) can ride along with the script, so only new lines cost
    cache_dir = Path(str(data.get("voice_cache", "")))
    if data.get("voice_cache") and cache_dir.is_dir():
        for f in cache_dir.iterdir():
            if f.name.startswith(f"pro_{voice_tag}_") and not (work / f.name).exists():
                shutil.copy(f, work / f.name)
        log(f"Voice lines reused from {cache_dir}")
    if eleven and data.get("voice_patch"):
        _voice_patch(data, cfg, work, voice_tag, base_rate, base_pitch)
    if eleven:
        _eleven_whole(data, cfg, work, voice_tag, base_rate, base_pitch)
    n_sc = len(data["scenes"])
    for i, sc in enumerate(data["scenes"]):
        text = str(sc.get("text", "")).strip()
        # delivery: each scene may speed up or slow down a little ("rate": "-8%") and hold
        # a longer or shorter beat after it ("pause": 0.4), so the narration has rhythm
        rate = max(-30, min(30, base_rate + (0 if eleven else _pct(sc.get("rate", "+0%")))))
        scenes = data["scenes"]
        scfg = {**cfg, "channel": {**cfg["channel"], "voice_rate": f"{rate:+d}%", "voice_pitch": base_pitch,
                                   "_prev_text": " ".join(str(x.get("text", "")) for x in scenes[max(i - 2, 0):i]),
                                   "_next_text": str(scenes[i + 1].get("text", "")) if i + 1 < len(scenes) else ""}}
        rtag = f"r{rate:+d}{re.sub(r'[^0-9+-]', '', base_pitch)}"
        audio = work / f"pro_{voice_tag}_{rtag}_{i:02d}.mp3"
        meta = audio.with_suffix(".json")
        if audio.exists() and meta.exists():
            dur, wl = json.loads(meta.read_text(encoding="utf-8"))
        else:
            dur, wl = tts.speak_words(text, audio, scfg)
            meta.write_text(json.dumps([dur, wl], ensure_ascii=False), encoding="utf-8")
        trim0 = 0.0
        if edge and wl:                    # cut the voice engine's own silence at both ends
            trim0 = max(float(wl[0][0]) - 0.03, 0.0)
            end = min(float(wl[-1][1]) + 0.09, dur)
            wl = [(a - trim0, b - trim0, t) for a, b, t in wl]
            dur = max(end - trim0, 0.3)
        try:
            gap = float(sc.get("pause", pause))
        except (TypeError, ValueError):
            gap = pause
        # the last line holds longer, so the ending breathes instead of cutting off
        length = dur + max(0.0, min(gap, 2.2 if i == n_sc - 1 else 1.2))
        if max_seconds and t0 + length > max_seconds:
            log(f"Stopping at scene {i} to stay under {max_seconds}s")
            break
        part = work / f"pro_{voice_tag}_{i:02d}.wav"
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{trim0:.3f}", "-i", str(audio), "-af",
             f"atrim=0:{dur:.3f},afade=t=out:st={max(dur - 0.04, 0):.3f}:d=0.04,apad=whole_dur={length:.3f}",
             "-t", f"{length:.3f}", "-ar", str(SR), "-ac", "1", str(part)])
        parts.append(part)
        hi = _highlight_mask(sc, [x[2] for x in wl])
        for k, (s, e, tok) in enumerate(wl):
            words.append({"t0": t0 + s, "t1": t0 + e, "tok": tok, "scene": i, "k": k, "hi": hi[k]})
        scene_t.append((t0, t0 + length))
        t0 += length
    if not parts:
        raise RuntimeError("No scenes fit into the video")
    total = t0
    scenes = data["scenes"][:len(parts)]
    voice = work / f"pro_voice_{voice_tag}.wav"
    lst = work / "pro_voice_list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst.name,
         "-c", "copy", voice.name], cwd=work)

    # ---- lab test switches (config video.pro_banned_*): banned transitions become cuts
    banned_tr = {str(t) for t in (vcfg.get("pro_banned_transitions") or [])}
    banned_sfx = {str(k) for k in (vcfg.get("pro_banned_sfx") or [])}
    for sc in scenes:
        for b in sc.get("beats") or []:
            if b.get("transition") in banned_tr:
                b["transition"] = "cut"

    # ---- shots (beats) on the timeline
    shots = _shots(scenes, scene_t, words, total)
    log(f"Pro render: {len(shots)} shots over {total:.1f}s, mood {data['music_mood']}")

    # ---- picture: one clip per shot, joined with transitions
    tag = f"{w}x{h}"
    seg_files, first_img = [], None
    data.pop("_prev_src", None)
    for n, sh in enumerate(shots):
        d_out = shots[n + 1]["d"] if n + 1 < len(shots) else 0.0
        seg = work / f"pro_seg{n:02d}_{tag}.mp4"
        _render_shot(sh, n, data, size, fps, sh["len"] + d_out,
                     shots[n + 1]["tr"] if n + 1 < len(shots) else "cut", seg, work)
        seg_files.append(seg)
    pictures = work / f"pro_pictures_{tag}.mp4"
    _join(shots, seg_files, pictures, work)
    first_img = work / f"pro_first_{tag}.jpg"
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.6", "-i", str(pictures), "-frames:v", "1", str(first_img)])
    shutil.copy(first_img, first_img.with_name(first_img.stem + "_bg.jpg"))

    # ---- captions
    hidden = [(s["start"], s["end"]) for s in shots if s["beat"].get("shot") == "text"]
    ass, boxes, pops = write_captions(words, size, work / f"pro_captions_{tag}.ass", hidden)

    # ---- sound: effects + music + voice, loudness-normalised
    events = [e for e in _sfx_events(shots, pops) if e[0] not in banned_sfx]
    if banned_sfx:
        log(f"Lab switches: no {', '.join(sorted(banned_sfx))} sounds; transitions off: {', '.join(sorted(banned_tr)) or 'none'}")
    sfx = _write_sfx(events, total, work / f"pro_sfx_{tag}.wav", voice,
                     float(vcfg.get("pro_sfx_volume", 0.45)))
    track = _pick_music(data)
    gains = data.get("music_gains") or [MOOD_GAIN.get(str(sc.get("look", "")), 1.0) for sc in scenes]
    curve = [(a, b, float(g)) for (a, b), g in zip(scene_t, gains)]
    mix = _mix_audio(voice, sfx, track, total, float(data.get("music_volume", vcfg.get("music_volume", 0.06))),
                     work, tag, curve)

    # ---- final: burn captions, add the mix
    vf = (f"ass={ass.name}:fontsdir={FONT_DIR.resolve()},"
          f"fade=t=out:st={max(total - 0.6, 0):.3f}:d=0.6,format=yuv420p")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", pictures.name, "-i", mix.name,
         "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-map", "1:a", "-t", f"{total:.3f}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2", "-r", str(fps),
         "-movflags", "+faststart", str(out_file.resolve())], cwd=work)
    log(f"Rendered {out_file.name} ({total:.1f}s, {tag})")

    if str(os.environ.get("STUDIO_EXPORT_SOURCES", vcfg.get("export_sources", ""))).lower() in ("1", "true", "yes"):
        try:
            export_sources(out_file, data, shots, seg_files, pictures, voice, sfx, mix, ass, words, track,
                           size, fps, total, work, tag)
        except Exception as e:          # the video itself is fine: don't lose it over the extras
            log(f"Source export failed: {type(e).__name__}: {e}")

    report = qc.check(out_file, size, fps, boxes, qc.safe_area(size))
    if data.get("_keep"):
        _framecheck_sheet(shots, work, out_file.with_suffix(".framecheck.jpg"))
        checked = [s for s in shots if (s.get("framecheck") or {}).get("checked")]
        report["info"]["framecheck"] = {"checked": len(checked),
                                        "refit": sum(1 for s in shots if (s.get("framecheck") or {}).get("refit")),
                                        "modes": [(s.get("plan") or {}).get("mode") for s in shots]}
        report["info"]["framecheck"]["replaced"] = [f"{s['start']:.1f}s {s.get('replaced')}" for s in shots
                                                    if s.get("replaced")]
        for s in shots:
            if s.get("covered"):
                report["warnings"].append(f"refill: no footage filled the screen at {s['start']:.1f}s, "
                                          f"shown full screen centred on the subject")
        for s in checked:
            if s["framecheck"]["cut"]:
                report["warnings"].append(f"framecheck: subject still cut at {s['start']:.1f}s "
                                          f"({s['framecheck']['where']})")
    out_file.with_suffix(".qc.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    qc.log_report(report)
    strict = str(os.environ.get("STUDIO_QC_STRICT", vcfg.get("qc_strict", True))).lower() not in ("0", "false", "no")
    if report["errors"] and strict:
        raise RuntimeError("Quality check failed: " + "; ".join(report["errors"]))
    return {"duration": total, "first_image": first_img, "music": track.name if track else None,
            "chapters": [], "qc": report, "plan": data}


def _feelings(data: dict) -> dict:
    """A scene's "look" (excited, sad, angry, whisper) goes to its beats; angry shakes.
    The part that says "follow" gets the FOLLOW FOR MORE end card and holds a moment."""
    scenes = data["scenes"]
    for sc in scenes:
        look = sc.get("look")
        for k, b in enumerate(sc.get("beats") or []):
            if look and not b.get("look"):
                b["look"] = look
            if b.get("look") == "angry" and k == 0:
                b.setdefault("shake", True)
    if scenes:
        last = scenes[-1]
        toks = str(last.get("text", "")).split()
        k = next((i for i, t in enumerate(toks) if t.lower().strip(".,!?").startswith("follow")), None)
        beats = last.setdefault("beats", [])
        if k is not None and not any(b.get("shot") == "text" and "FOLLOW" in str(b.get("text", "")).upper()
                                     for b in beats):
            beats[:] = [b for b in beats if int(b.get("at_word", 0)) == 0 or int(b.get("at_word", 0)) <= k - 3]
            q = (beats[0].get("query") if beats else None) or last.get("visual") or data.get("title", "")
            card = {"at_word": k, "shot": "text", "text": "FOLLOW FOR MORE", "query": q, "camera": "drift",
                    "transition": "flash" if k else "cut", "sfx": ["shimmer"]}
            if k == 0:
                beats[:] = [card]
            else:
                beats.append(card)
            last.setdefault("pause", 1.4)
    return data


def _with_follow(data: dict, cfg: dict) -> dict:
    """Every Short ends on a clear follow line, unless the script already asks for it."""
    line = str(cfg["video"].get("follow_line", "") or "").strip()
    scenes = data.get("scenes") or []
    if not line or not scenes or data.get("follow") is False:     # "follow": false = loop ending
        return data
    if any("follow" in str(sc.get("text", "")).lower() for sc in scenes[-2:]):
        return data
    data = {**data, "scenes": [dict(sc) for sc in scenes]}
    last = data["scenes"][-1]
    text = str(last.get("text", "")).rstrip()
    if text and text[-1] not in ".!?…":
        text += "..."
    last["text"] = f"{text} {line}".strip()
    say = str(last.get("say") or text).rstrip()
    if say and say[-1] not in ".!?…]":
        say += "..."
    last["say"] = f"{say} [chuckles] {line}".strip()
    return data


def _eleven_whole(data: dict, cfg: dict, work: Path, voice_tag: str, base_rate: int, base_pitch: str) -> None:
    """One ElevenLabs read of the whole script (natural flow, nothing from the next line
    leaks in), cut into one file per scene in the silence between sentences. The files
    are the cache the scene loop reads, so the account is charged once per script."""
    scenes = data["scenes"]
    rtag = f"r{base_rate:+d}{re.sub(r'[^0-9+-]', '', base_pitch)}"
    names = [work / f"pro_{voice_tag}_{rtag}_{i:02d}.mp3" for i in range(len(scenes))]
    if all(n.exists() and n.with_suffix(".json").exists() for n in names):
        return
    texts = [str(sc.get("text", "")).strip() for sc in scenes]
    full = " ".join(texts)
    whole = work / f"pro_{voice_tag}_{rtag}_whole.mp3"
    meta = whole.with_suffix(".json")
    if whole.exists() and meta.exists():
        dur, wl = json.loads(meta.read_text(encoding="utf-8"))
    else:
        ch = {**cfg["channel"], "voice_rate": f"{base_rate:+d}%"}
        ch.pop("_prev_text", None)
        ch.pop("_next_text", None)
        dur = wl = None
        if str(ch.get("eleven_model", "")) == "eleven_v3":
            # v3 reads the feelings written into the script ("say", with [laughs], [sighs]...);
            # the word times come from the free whisper model, matched to the clean text
            say = " ".join(str(sc.get("say") or sc.get("text", "")).strip() for sc in scenes)
            try:
                tts.eleven_v3(say, ch["voice"].split(":", 1)[1], ch, whole)
                dur = tts.media_duration(whole)
                wl = tts.align_words(full, tts.heard_words(whole), dur)
                (work / "voice_v3.txt").write_text(say, encoding="utf-8")
                log(f"ElevenLabs v3: whole script with feelings in one read ({len(say)} characters)")
            except Exception as e:      # v3 not available: the older model reads the clean text
                print(f"::warning title=ElevenLabs v3 not used::{type(e).__name__}: {e}. "
                      f"Using eleven_multilingual_v2 instead.", flush=True)
                dur = wl = None
        if wl is None:
            dur, wl = tts.speak_words(full, whole, {**cfg, "channel": ch})
        meta.write_text(json.dumps([dur, wl], ensure_ascii=False), encoding="utf-8")
    counts = [len(t.split()) for t in texts]
    if len(wl) != sum(counts):
        raise RuntimeError(f"ElevenLabs word count {len(wl)} does not match the script ({sum(counts)})")
    k, spans = 0, []
    for c in counts:
        spans.append((k, k + c))
        k += c
    cuts = [0.0]
    for i in range(len(scenes) - 1):
        a_end = float(wl[spans[i][1] - 1][1])
        b_start = float(wl[spans[i + 1][0]][0])
        cuts.append(a_end + max(b_start - a_end, 0.0) * 0.5)
    cuts.append(float(dur))
    for i, (a, b) in enumerate(zip(cuts, cuts[1:])):
        lo, hi = spans[i]
        seg = [(float(x) - a, float(y) - a, t) for x, y, t in wl[lo:hi]]
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(whole), "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
             "-af", "afade=t=in:d=0.015", "-c:a", "libmp3lame", "-q:a", "2", str(names[i])])
        names[i].with_suffix(".json").write_text(json.dumps([b - a, seg], ensure_ascii=False), encoding="utf-8")
    log(f"ElevenLabs: whole script in one read ({dur:.1f}s), cut into {len(scenes)} lines")


def _voice_patch(data: dict, cfg: dict, work: Path, voice_tag: str, base_rate: int, base_pitch: str) -> None:
    """Lab: keep the paid whole read up to a scene and read only the new ending again
    (one short ElevenLabs v3 call), joined in the pause before that scene. The word times
    of the joined read are taken again, so captions and graphics follow the new ending."""
    p = data.get("voice_patch") or {}
    i0 = int(p.get("from_scene", len(data["scenes"]) - 1))
    rtag = f"r{base_rate:+d}{re.sub(r'[^0-9+-]', '', base_pitch)}"
    whole = work / f"pro_{voice_tag}_{rtag}_whole.mp3"
    meta = whole.with_suffix(".json")
    flag = work / "voice_patch.done"
    if flag.exists() or not (whole.exists() and meta.exists()):
        return
    scenes = data["scenes"]
    texts = [str(sc.get("text", "")).strip() for sc in scenes]
    old_dur, old_wl = json.loads(meta.read_text(encoding="utf-8"))
    words = " ".join(texts).split()
    if len(old_wl) == len(words) and old_wl and old_wl[-1][2] == words[-1]:
        log("Voice: the cached read already has this ending, nothing to read again")
        return
    k0 = sum(len(t.split()) for t in texts[:i0])
    prev_end, start = float(old_wl[k0 - 1][1]), float(old_wl[k0][0])
    cut = prev_end + max(start - prev_end, 0.0) * 0.5
    say = " ".join(str(sc.get("say") or sc.get("text", "")).strip() for sc in scenes[i0:])
    ch = cfg["channel"]
    take = work / "pro_patch_take.mp3"
    if not take.exists():
        tts.eleven_v3(say, str(ch["voice"]).split(":", 1)[1], ch, take)
    log(f"ElevenLabs v3: new ending read from scene {i0} ({len(say)} characters billed): {say}")
    # the new take without its own silence at the start and end
    clean = work / "pro_patch_clean.wav"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(take), "-af",
         "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03,"
         "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.12,areverse",
         "-ar", "44100", "-ac", "1", str(clean)])

    def _mean_db(args: list[str]) -> float | None:
        r = subprocess.run(["ffmpeg", "-hide_banner", *args, "-af", "volumedetect", "-f", "null", "-"],
                           capture_output=True, text=True)
        m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
        return float(m.group(1)) if m else None
    ref = _mean_db(["-ss", f"{max(start - 0.05, 0):.3f}", "-i", str(whole)])
    new = _mean_db(["-i", str(clean)])
    gain = max(-6.0, min(6.0, (ref - new))) if ref is not None and new is not None else 0.0
    gap = max(start - 0.04 - cut, 0.05)
    joined = work / "pro_patch_joined.mp3"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(whole), "-i", str(clean), "-filter_complex",
         f"[0:a]atrim=0:{cut:.3f},aresample=44100,aformat=channel_layouts=mono,"
         f"afade=t=out:st={max(cut - 0.08, 0):.3f}:d=0.08,apad=pad_dur={gap:.3f}[a];"
         f"[1:a]aresample=44100,aformat=channel_layouts=mono,volume={gain:.2f}dB,afade=t=in:d=0.01[b];"
         f"[a][b]concat=n=2:v=0:a=1[o]", "-map", "[o]", "-c:a", "libmp3lame", "-q:a", "2", str(joined)])
    shutil.move(str(joined), str(whole))
    dur = tts.media_duration(whole)
    wl = tts.align_words(" ".join(texts), tts.heard_words(whole), dur)
    meta.write_text(json.dumps([dur, wl], ensure_ascii=False), encoding="utf-8")
    for f in work.glob(f"pro_{voice_tag}_{rtag}_[0-9]*.*"):     # the per-line cuts are made again
        f.unlink()
    flag.write_text(say, encoding="utf-8")
    log(f"Voice: old read kept to {cut:.2f}s, new ending joined ({gain:+.1f} dB), now {dur:.2f}s")


def _pct(v) -> int:
    m = re.match(r"\s*([+-]?\d+)", str(v or "0"))
    return int(m.group(1)) if m else 0


# ===================================================================== shots
def _shots(scenes: list[dict], scene_t: list[tuple[float, float]], words: list[dict], total: float) -> list[dict]:
    raw = []
    for i, sc in enumerate(scenes):
        sw = [x for x in words if x["scene"] == i]
        for b in sc["beats"]:
            k = int(b.get("at_word", 0))
            if k <= 0 or not sw:
                start = scene_t[i][0]
            else:
                start = sw[min(k, len(sw) - 1)]["t0"] - 0.05
            tr = b.get("transition", "cut") if raw else "cut"
            tr = tr if tr in TRANSITION_LEN else "cut"
            raw.append({"start": max(start, 0.0), "beat": b, "scene": i, "tr": tr,
                        "wts": [x["t0"] for x in sw], "wte": [x["t1"] for x in sw]})
    raw[0]["start"] = 0.0
    # drop shots that would be too short to read
    shots = [raw[0]]
    for r in raw[1:]:
        if r["start"] - shots[-1]["start"] < MIN_SHOT:
            if r["beat"].get("shot") != "clip" and shots[-1]["beat"].get("shot") == "clip" and len(shots) > 1:
                shots[-1] = {**r, "start": shots[-1]["start"]}    # keep the graphic, not the filler
            continue
        shots.append(r)
    if len(shots) > 1 and total - shots[-1]["start"] < MIN_SHOT:
        shots.pop()
    # the transition is centred on the cut word: the change starts d/2 before it
    for n, s in enumerate(shots):
        s["d"] = TRANSITION_LEN[s["tr"]] if n else 0.0
        s["b"] = s["start"] - s["d"] / 2 if n else 0.0
    for n, s in enumerate(shots):
        s["end"] = shots[n + 1]["start"] if n + 1 < len(shots) else total
        nb = shots[n + 1]["b"] if n + 1 < len(shots) else total
        s["len"] = nb - s["b"]
    return shots


def _join(shots: list[dict], files: list[Path], out: Path, work: Path) -> None:
    """Chain the shots: hard cuts by concat, styled transitions by xfade."""
    if len(files) == 1:
        shutil.copy(files[0], out)
        return
    args, fc, last, offset = [], [], "i0", 0.0
    for n, f in enumerate(files):
        args += ["-i", str(f)]
        fc.append(f"[{n}:v]settb=AVTB,setpts=PTS-STARTPTS[i{n}]")    # one timebase for concat + xfade
    for n in range(1, len(files)):
        offset += shots[n - 1]["len"]
        tr = shots[n]["tr"]
        if tr == "cut" or shots[n]["d"] <= 0:
            fc.append(f"[{last}][i{n}]concat=n=2:v=1:a=0,settb=AVTB[x{n}]")
        else:
            fc.append(f"[{last}][i{n}]xfade=transition={XFADE[tr]}:duration={shots[n]['d']:.3f}"
                      f":offset={offset:.3f}[x{n}]")
        last = f"x{n}"
    script = work / "pro_join.txt"
    script.write_text(";\n".join(fc), encoding="utf-8")
    run(["ffmpeg", "-y", "-loglevel", "error", *args, "-filter_complex_script", str(script),
         "-map", f"[{last}]", *ENC, str(out)])


# =================================================================== footage
_USED: set[str] = set()


def pexels_video(query: str, subject: str | None, pick: int, out: Path) -> tuple[Path, float, float] | None:
    """A free portrait stock clip from Pexels (no credit needed). Returns (file, start, duration)."""
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key or not query:
        return None
    meta = out.with_suffix(".meta.json")
    if out.exists() and meta.exists() and out.stat().st_size > 10000:
        m = json.loads(meta.read_text())
        _USED.add(m["id"])
        return out, m["start"], m["dur"]
    need = visuals.subject_words(query, subject)
    try:
        found = []
        for q in dict.fromkeys([query, " ".join(need)] if need else [query]):
            if not q:
                continue
            for orient in ("portrait", "landscape"):
                r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": key},
                                 timeout=30, params={"query": q, "orientation": orient, "per_page": 30})
                if r.status_code != 200:
                    log(f"Pexels video error {r.status_code} for '{q}'")
                    break
                for v in r.json().get("videos", []):
                    vid = f"px{v.get('id')}"
                    slug = re.sub(r"[-/]", " ", str(v.get("url", "")).rsplit("/video/", 1)[-1])
                    tags = slug + " " + " ".join(str(t) for t in (v.get("tags") or []))
                    if need and not visuals.tags_match(tags, need):
                        continue
                    if not 3 <= float(v.get("duration") or 0) <= 90 or vid in _USED:
                        continue
                    files = [f for f in v.get("video_files", []) if f.get("link") and (f.get("height") or 0) >= 720
                             and (f.get("file_type") or "").endswith("mp4")]
                    portrait = [f for f in files if f["height"] > f["width"]]
                    pool = portrait or files
                    if not pool:
                        continue
                    best = min(pool, key=lambda f: abs(f["height"] - (1920 if f["height"] > f["width"] else 1080)))
                    found.append((vid, float(v["duration"]), best, orient))
                if len([f for f in found if f[3] == "portrait"]) >= 4:
                    break
            if found:
                break
        if not found:
            return None
        found.sort(key=lambda f: f[3] != "portrait")         # portrait first
        vid, dur, f, _ = found[:6][pick % len(found[:6])]
        data = requests.get(f["link"], timeout=180)
        data.raise_for_status()
        out.write_bytes(data.content)
        start = round(min(1.0, dur * 0.1), 2)
        meta.write_text(json.dumps({"id": vid, "start": start, "dur": dur}))
        _USED.add(vid)
        log(f"Pexels clip for '{query}' ({f['width']}x{f['height']}, {dur:.0f}s, {vid})")
        return out, start, dur
    except Exception as e:
        log(f"Pexels video failed for '{query}': {type(e).__name__}")
        return None


def footage(beat: dict, n: int, title: str, size: tuple[int, int], work: Path, keep: bool = False) -> dict:
    """Best available picture for a shot: Pexels clip, Pixabay clip, stock photo, drawn slide."""
    ready = str(beat.get("src") or "").strip()
    if ready and Path(ready).is_file():          # a picture made for this beat (assets/gen/...)
        log(f"Shot {n}: using the prepared picture {ready}")
        return {"kind": "img", "src": Path(ready), "id": f"gen:{Path(ready).name}", "_gen": True}
    query = str(beat.get("query") or "").strip()
    subject = beat.get("subject")
    pick = _seed(title, n, query) % 3 + int(beat.get("alt", 0))
    stem = work / f"pro_ai{n:02d}{'r' * int(beat.get('_repick', 0))}"
    chosen = shotpick.pick(query, subject, stem)
    if keep and subject and framing.available() and not (chosen or {}).get("box"):
        # the footage doesn't show the subject (a sloth "swimming" came back as plain jungle):
        # try the beat's other wordings, then the subject alone, before settling for scenery
        alts = [str(q) for q in (beat.get("alt_query") or []) if str(q).strip()] + [str(subject)]
        for i, q in enumerate(dict.fromkeys(alts)):
            got = shotpick.pick(q, subject, stem.with_name(f"{stem.name}_alt{i}"))
            if got and got.get("box"):
                log(f"Shot {n}: no {subject} in the footage for '{query}', using '{q}' instead")
                chosen = got
                break
    if chosen and chosen["kind"] == "vid":
        return {"kind": "vid", "src": chosen["src"], "start": chosen["start"],
                "dur": chosen.get("dur") or media_duration(chosen["src"]),
                "content": chosen.get("content"), "box": chosen.get("box"), "id": chosen.get("id")}
    if chosen and keep:
        return {"kind": "img", "src": chosen["src"], "content": chosen.get("content"), "box": chosen.get("box"),
                "id": chosen.get("id")}
    if chosen:
        img = work / f"pro_img{n:02d}.jpg"
        w, h = size
        visuals._cover(Image.open(chosen["src"]).convert("RGB"), (w * 2, h * 2)).save(img, quality=92)
        return {"kind": "img", "src": img}
    got = pexels_video(query, subject, pick, work / f"pro_px{n:02d}.mp4")
    if got:
        return {"kind": "vid", "src": got[0], "start": got[1], "dur": got[2]}
    clip = visuals.pixabay_video(query, pick, work / f"pro_pb{n:02d}.mp4", subject)
    if clip is not None:
        return {"kind": "vid", "src": clip, "start": visuals.CLIP_START.get(str(clip), 0.0),
                "dur": media_duration(clip)}
    img = work / f"pro_img{n:02d}.jpg"
    if not img.exists():
        photo = visuals.stock_photo(query, True, _seed(title, n), subject)
        w, h = size
        if photo is not None:
            visuals._cover(photo, (w * 2, h * 2)).save(img, quality=92)
        else:
            visuals._gradient((w * 2, h * 2), "#0f2027", "#2c5364", _seed(title, n)).save(img, quality=92)
    return {"kind": "img", "src": img}


# ------------------------------------------------------------------ camera
def _camera(move: str, frames: int, fps: int, shake: bool) -> tuple[str, str, str]:
    """zoompan expressions (zoom, x, y) for a camera move over `frames` frames."""
    n = max(frames - 1, 1)
    p = f"min(on/{n},1)"
    e = f"({p}*{p}*(3-2*{p}))"                    # smooth in-out
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if move == "push_in":
        z, x, y = f"1.02+0.16*{e}", cx, cy
    elif move == "pull_out":
        z, x, y = f"1.18-0.16*{e}", cx, cy
    elif move == "pan_left":
        z, x, y = "1.16", f"(iw-iw/zoom)*(1-{e})", cy
    elif move == "pan_right":
        z, x, y = "1.16", f"(iw-iw/zoom)*{e}", cy
    elif move == "tilt_up":
        z, x, y = "1.16", cx, f"(ih-ih/zoom)*(1-{e})"
    elif move == "tilt_down":
        z, x, y = "1.16", cx, f"(ih-ih/zoom)*{e}"
    elif move == "punch":
        k = max(int(fps * 0.28), 2)
        z = (f"if(lt(on,{k}),1.34-0.26*(1-pow(1-on/{k},3)),"
             f"1.08+0.07*min((on-{k})/{max(n - k, 1)},1))")
        x, y = cx, cy
    elif move == "static":
        z, x, y = "1.04", cx, cy
    else:   # drift: slow push with a gentle sideways float
        z, x, y = f"1.06+0.06*{e}", f"(iw-iw/zoom)*(0.35+0.3*{e})", cy
    if shake:
        x = f"({x})+14*sin(on*2.7)*exp(-on/7)"
        y = f"({y})+11*cos(on*3.1)*exp(-on/7)"
    return z, x, y


GRADE = "eq=contrast=1.06:saturation=1.12:gamma=0.98,unsharp=5:5:0.35:5:5:0,vignette=angle=PI/5"
# the feeling of a part ("look" on a scene or beat) changes the picture, so the screen follows the voice
LOOKS = {
    "excited": ",eq=saturation=1.25:contrast=1.06:brightness=0.02",
    "sad": ",eq=saturation=0.5:brightness=-0.01:contrast=0.97,colorbalance=bs=0.10:bm=0.06,vignette=angle=PI/4",
    "angry": ",eq=saturation=1.3:contrast=1.14,colorbalance=rs=0.16:rm=0.10:bs=-0.08,vignette=angle=PI/4",
    "whisper": ",eq=saturation=0.8:gamma=1.08,vignette=angle=PI/4",
}
MOOD_GAIN = {"sad": 0.45, "whisper": 0.6, "angry": 1.25, "excited": 1.15}
BRIGHTEN = ",eq=gamma=1.45:brightness=0.04:saturation=1.05"      # for a clip that came out too dark
DARK_YAVG = 42                                                     # mean brightness (0-255) below this is too dark


def _fx(tr_in: str, tr_out: str, length: float) -> list[str]:
    """Motion blur / glitch on the edges of a shot that touch a styled transition."""
    f = []
    if tr_in in ("whip_left", "whip_right"):
        f.append("gblur=sigma=38:sigmaV=0.01:steps=2:enable='lt(t,0.13)'")
    if tr_out in ("whip_left", "whip_right"):
        f.append(f"gblur=sigma=38:sigmaV=0.01:steps=2:enable='gte(t,{length - 0.13:.3f})'")
    if tr_in == "slide_up":
        f.append("gblur=sigma=0.01:sigmaV=34:steps=2:enable='lt(t,0.12)'")
    if tr_out == "slide_up":
        f.append(f"gblur=sigma=0.01:sigmaV=34:steps=2:enable='gte(t,{length - 0.12:.3f})'")
    if tr_in == "glitch":
        f.append("rgbashift=rh=-16:bh=16:gv=6:enable='lt(t,0.22)'")
        f.append("noise=alls=35:allf=t:enable='lt(t,0.18)'")
    if tr_out == "glitch":
        f.append(f"rgbashift=rh=14:bh=-14:enable='gte(t,{length - 0.12:.3f})'")
    if tr_in == "flash":
        f.append("eq=brightness=0.18:enable='lt(t,0.08)'")
    return f


def _render_shot(sh: dict, n: int, data: dict, size: tuple[int, int], fps: int, length: float,
                 tr_out: str, out: Path, work: Path, bright: bool = False) -> None:
    if data.get("_keep"):
        return _render_keep(sh, n, data, size, fps, length, tr_out, out, work, bright)
    w, h = size
    beat = sh["beat"]
    kind = beat.get("shot", "clip")
    frames = max(int(round(length * fps)), 2)
    src = footage(beat, n, data["title"], size, work)
    sh["src"] = src
    camera = beat.get("camera") or ("drift" if kind in ("number", "compare", "text") else "push_in")
    shake = bool(beat.get("shake")) or ("impact" in (beat.get("sfx") or []) and camera == "punch")
    z, x, y = _camera(camera, frames, fps, shake)
    up = 1.5 if camera in ("punch", "push_in", "pull_out", "drift") else 1.25
    sw, shh = int(w * up) // 2 * 2, int(h * up) // 2 * 2
    inputs: list[str] = []
    chain = ""
    if src["kind"] == "vid":
        st = min(src["start"], max(src["dur"] - length - 0.1, 0.0))     # room for the whole shot
        avail = max(src["dur"] - st, 0.5)
        slow = min(max(length / avail, 1.0), 1.6) if avail < length else 1.0
        loop = avail * slow < length
        inputs += [*(["-stream_loop", "-1"] if loop else []), "-ss", f"{st:.2f}", "-i", str(src["src"])]
        chain = f"[0:v]setpts={slow:.3f}*(PTS-STARTPTS),fps={fps},"
    else:
        inputs += ["-loop", "1", "-framerate", str(fps), "-i", str(src["src"])]
        chain = "[0:v]"
    chain += (f"scale={sw}:{shh}:force_original_aspect_ratio=increase,crop={sw}:{shh},setsar=1,"
              f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={w}x{h}:fps={fps},{GRADE}{LOOKS.get(beat.get('look'), '')}"
              f"{BRIGHTEN if bright else ''}")
    if kind in ("number", "compare", "text"):
        chain += ",gblur=sigma=16,eq=brightness=-0.08:saturation=0.8,colorlevels=romin=0.09:gomin=0.09:bomin=0.1:romax=0.8:gomax=0.8:bomax=0.82"
    fx = _fx(sh["tr"], tr_out, length)
    if fx:
        chain += "," + ",".join(fx)
    if kind in ("number", "compare", "text"):
        ov_dir, oy = _graphic_frames(beat, kind, size, fps, length, work / f"pro_gfx{n:02d}")
        sh["gfx"] = (ov_dir, oy)
        inputs += ["-framerate", str(fps), "-i", str(ov_dir / "%04d.png")]
        chain += f"[bg];[bg][1:v]overlay=0:{oy}:eof_action=repeat"
    chain += ",format=yuv420p[v]"
    script = work / f"pro_shot{n:02d}.txt"
    script.write_text(chain, encoding="utf-8")
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex_script", str(script),
         "-map", "[v]", "-an", "-frames:v", str(frames), "-r", str(fps), *ENC, str(out)])
    # a clip that came out too dark would fail the black-picture check: render it once more, brighter
    if not bright and kind == "clip":
        y = _mean_luma(out)
        if y is not None and y < DARK_YAVG:
            log(f"Shot {n} is too dark (brightness {y:.0f}), brightening it")
            _render_shot(sh, n, data, size, fps, length, tr_out, out, work, bright=True)



# ============================================================ whole-subject framing (lab)
# mindblip-studio core/motion.md: never crop off heads or feet. Every source is shown so the
# whole subject stays on screen: a 9:16 window that holds it ("fill"), or the picture whole
# and smaller over a blurred copy of itself ("fit"). Camera moves stay gentle (5-8 %) and
# never push the subject out. A card shot floats a framed picture over a dimmed background.
def _probe_wh(path: Path) -> tuple[int, int]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "csv=p=0:s=x", str(path)],
                         capture_output=True, text=True).stdout.strip().splitlines()
    try:
        a, b = out[0].split("x")[:2]
        return int(a), int(b)
    except Exception:
        im = Image.open(path)
        return im.size


def _ensure_framing(src: dict, subject: str | None) -> dict:
    """Content area and keep-box for a source that came without them (older fallbacks)."""
    if src.get("content"):
        return src
    path = Path(src["src"])
    imgs = []
    if src["kind"] == "vid":
        for k in (0.3, 1.8, 3.3):
            im = shotpick._frame_at(path, float(src.get("start", 0.0)) + k)
            if im is not None:
                imgs.append(im)
    else:
        im = Image.open(path).convert("RGB")
        im.thumbnail((960, 960))
        imgs = [im]
    if not imgs:
        return {**src, "content": (0.0, 0.0, 1.0, 1.0), "box": None}
    fr = shotpick._framing(imgs, subject)
    return {**src, "content": fr["content"], "box": fr["box"]}


def _wide_framing(src: dict, subject: str | None) -> dict:
    """Re-find the subject with a wider net (every box close to the best one), so a second
    animal half in the frame or a partly found body is kept whole too."""
    if src.get("_wide") or not subject or not framing.available():
        return src
    path = Path(src["src"])
    imgs = []
    if src["kind"] == "vid":
        for k in (0.3, 1.8, 3.3):
            im = shotpick._frame_at(path, float(src.get("start", 0.0)) + k)
            if im is not None:
                imgs.append(im)
    else:
        im = Image.open(path).convert("RGB")
        im.thumbnail((960, 960))
        imgs = [im]
    content = src.get("content") or (0.0, 0.0, 1.0, 1.0)
    boxes = [framing.to_content(framing.wide_box(framing.find_boxes(im, str(subject))), content) for im in imgs]
    wide = framing.union([b for b in boxes if b] + [src.get("box")])
    return {**src, "box": wide if wide else src.get("box"), "_wide": True}


def _even(v: float) -> int:
    return max(int(v) // 2 * 2, 2)


def _safe_camera(move: str, frames: int, fps: int, p: dict, shake: bool) -> tuple[str, str, str]:
    """Gentle zoompan expressions that keep the whole (padded) subject in view."""
    n = max(frames - 1, 1)
    e = f"(min(on/{n},1)*min(on/{n},1)*(3-2*min(on/{n},1)))"
    zm = max(1.0, min(float(p.get("zmax", 1.0)), 1.08))
    fx, fy = p.get("focus", (0.5, 0.5))
    wb = p.get("wbox") or (0.0, 0.0, 1.0, 1.0)
    if zm < 1.01:
        move = "hold"
    if move == "push_in":
        z = f"1+{zm - 1:.4f}*{e}"
    elif move == "pull_out":
        z = f"{zm:.4f}-{zm - 1:.4f}*{e}"
    elif move in ("punch", "settle"):          # settle & hold: arrives bigger, settles in ~8 frames
        k = max(int(fps * 0.28), 2)
        z = f"if(lt(on,{k}),{zm:.4f}-{zm - 1:.4f}*(1-pow(1-on/{k},3)),1+0.01*min((on-{k})/{max(n - k, 1)},1))"
    elif move in ("pan_left", "pan_right", "tilt_up", "tilt_down"):
        z = f"{zm:.4f}"
    elif move == "drift":
        z = f"1+{min(zm - 1, 0.04):.4f}*{e}"
    else:                                      # static / hold
        z = f"1+{min(zm - 1, 0.01):.4f}*{e}"
    # the view may slide only as far as the subject stays inside it
    lx = f"max(0,{wb[2]:.4f}*iw-iw/zoom)"
    ux = f"min({wb[0]:.4f}*iw,iw-iw/zoom)"
    ly = f"max(0,{wb[3]:.4f}*ih-ih/zoom)"
    uy = f"min({wb[1]:.4f}*ih,ih-ih/zoom)"
    cx = f"max({lx},min({ux},{fx:.4f}*iw-iw/zoom/2))"
    cy = f"max({ly},min({uy},{fy:.4f}*ih-ih/zoom/2))"
    x, y = cx, cy
    if move == "pan_left":
        x = f"max({lx},min({ux},{ux}-({ux}-({lx}))*{e}))"
    elif move == "pan_right":
        x = f"max({lx},min({ux},{lx}+({ux}-({lx}))*{e}))"
    elif move == "tilt_up":
        y = f"max({ly},min({uy},{uy}-({uy}-({ly}))*{e}))"
    elif move == "tilt_down":
        y = f"max({ly},min({uy},{ly}+({uy}-({ly}))*{e}))"
    if shake:
        x = f"max(0,min(iw-iw/zoom,({x})+8*sin(on*2.7)*exp(-on/7)))"
        y = f"max(0,min(ih-ih/zoom,({y})+6*cos(on*3.1)*exp(-on/7)))"
    return z, x, y


def _framed(src: dict, p: dict, size: tuple[int, int], fps: int, frames: int, camera: str, shake: bool,
            inputs: list[str], work: Path, tag: str) -> str:
    """Filter graph from [0:v] (already timed) to [base]: the source framed by plan p."""
    W, H = size
    x, y, cw, ch = p["crop"]
    x, y, cw, ch = int(x), int(y), _even(cw), _even(ch)
    up = 1.5
    z, xe, ye = _safe_camera(camera, frames, fps, p, shake)
    if p["mode"] == "fill":
        return (f"[0:v]crop={cw}:{ch}:{x}:{y},scale={_even(W * up)}:{_even(H * up)},setsar=1,"
                f"zoompan=z='{z}':x='{xe}':y='{ye}':d=1:s={W}x{H}:fps={fps}[base]")
    # fit: the window whole and smaller, on a blurred, dimmed copy of the picture
    sw, shh = p["show"]
    top = framing.fit_top(p, size)
    left = (W - sw) // 2
    if p.get("style", "box") == "blend":
        return _framed_blend(src, p, size, fps, frames, z, xe, ye, inputs, work, tag, sw, shh, top, left)
    r = int(min(sw, shh) * 0.035)
    mask = work / f"pro_fitmask_{tag}.png"
    m = Image.new("L", (sw, shh), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, sw - 1, shh - 1), r, fill=255)
    m.save(mask)
    shadow = work / f"pro_fitshadow_{tag}.png"
    sd = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sd).rounded_rectangle((left, top + 14, left + sw, top + shh + 14), r, fill=(0, 0, 0, 170))
    sd.filter(ImageFilter.GaussianBlur(22)).save(shadow)
    k = len([a for a in inputs if a == "-i"])
    inputs += ["-loop", "1", "-i", str(mask), "-loop", "1", "-i", str(shadow)]
    cx0, cy0, cx1, cy1 = src.get("content") or (0, 0, 1, 1)
    sw0, sh0 = src["_wh"]
    bx, by, bw, bh = int(cx0 * sw0), int(cy0 * sh0), _even((cx1 - cx0) * sw0), _even((cy1 - cy0) * sh0)
    bgw, bgh = _even(W * 1.08), _even(H * 1.08)
    fz = f"zoompan=z='{z}':x='{xe}':y='{ye}':d=1:s={sw}x{shh}:fps={fps}"
    return (f"[0:v]split=2[sa][sb];"
            f"[sa]crop={bw}:{bh}:{bx}:{by},scale={W // 4}:{H // 4}:force_original_aspect_ratio=increase,"
            f"crop={W // 4}:{H // 4},gblur=sigma=7,scale={bgw}:{bgh},"
            f"crop={W}:{H}:x='(iw-ow)*min(t/{max(frames / fps, 0.5):.2f},1)':y='(ih-oh)/2',"
            f"eq=brightness=-0.13:saturation=0.8,setsar=1[bgv];"
            f"[sb]crop={cw}:{ch}:{x}:{y},scale={_even(sw * up)}:{_even(shh * up)},setsar=1,{fz},format=rgba[fg0];"
            f"[{k}:v]format=gray,scale={sw}:{shh}[mk];[fg0][mk]alphamerge[fg];"
            f"[bgv][{k + 1}:v]overlay=0:0[bs];[bs][fg]overlay={left}:{top}:shortest=0[base]")


def _framed_blend(src: dict, p: dict, size: tuple[int, int], fps: int, frames: int, z: str, xe: str, ye: str,
                  inputs: list[str], work: Path, tag: str, sw: int, shh: int, top: int, left: int) -> str:
    """Fit, blended: the whole picture melts into a soft, bright, blurred extension of
    itself at its edges, so there is no box and no dark band, only the picture, taller.
    The extension slowly drifts the other way to the picture (gentle parallax)."""
    W, H = size
    x, y, cw, ch = p["crop"]
    x, y, cw, ch = int(x), int(y), _even(cw), _even(ch)
    up = 1.5
    # soft edges only in the room around the subject, never over it
    wb = p.get("wbox") or (0.0, 0.0, 1.0, 1.0)
    room_v = min(wb[1], 1 - wb[3]) * shh
    room_h = min(wb[0], 1 - wb[2]) * sw
    fv = int(max(40, min(shh * 0.18, 200, room_v * 2.0)))
    fh = int(max(30, min(sw * 0.10, 120, room_h * 2.0))) if sw < W - 4 else 0
    mask = work / f"pro_fitblend_{tag}.png"
    a = np.full((shh, sw), 255.0, dtype=np.float32)
    if fv > 0:
        ramp = np.linspace(0.0, 1.0, fv, dtype=np.float32) ** 1.6
        a[:fv, :] *= ramp[:, None]
        a[shh - fv:, :] *= ramp[::-1][:, None]
    if fh > 0:
        ramp = np.linspace(0.0, 1.0, fh, dtype=np.float32) ** 1.6
        a[:, :fh] *= ramp[None, :]
        a[:, sw - fh:] *= ramp[::-1][None, :]
    Image.fromarray(a.clip(0, 255).astype(np.uint8), "L").save(mask)
    k = len([q for q in inputs if q == "-i"])
    inputs += ["-loop", "1", "-i", str(mask)]
    fz = f"zoompan=z='{z}':x='{xe}':y='{ye}':d=1:s={sw}x{shh}:fps={fps}"
    # the extension: the picture's own edge colours smeared outwards and blurred into a
    # smooth glow, so the screen continues the photo instead of showing a box or a band
    q = 4
    pw, ph, pl, pt = _even(sw / q), _even(shh / q), _even(left / q), _even(top / q)
    W4, H4 = _even(W / q), _even(H / q)
    pt = min(pt, H4 - ph)
    pl = min(pl, W4 - pw)
    return (f"[0:v]split=3[sa][sb][sc];"
            f"[sa]crop={cw}:{ch}:{x}:{y},scale={pw}:{ph},setsar=1,"
            f"pad={W4}:{H4}:{pl}:{pt},"
            f"fillborders=left={pl}:right={W4 - pl - pw}:top={pt}:bottom={H4 - pt - ph}:mode=smear,"
            f"gblur=sigma=26:sigmaV=9,setsar=1[sm];"
            f"[sc]crop={cw}:{ch}:{x}:{y},scale={W4}:{H4}:force_original_aspect_ratio=increase,"
            f"crop={W4}:{H4},gblur=sigma=12,setsar=1[cv];"
            f"[sm][cv]blend=all_mode=normal:all_opacity=0.45,scale={W}:{H}:flags=bicubic,"
            f"eq=brightness=-0.05:saturation=1.06,vignette=angle=0.5,setsar=1[bgv];"
            f"[sb]crop={cw}:{ch}:{x}:{y},scale={_even(sw * up)}:{_even(shh * up)},setsar=1,{fz},format=rgba[fg0];"
            f"[{k}:v]format=gray,scale={sw}:{shh}[mk];[fg0][mk]alphamerge[fg];"
            f"[bgv][fg]overlay={left}:{top}:shortest=0[base]")


def _card_overlay(beat: dict, n: int, size: tuple[int, int], fps: int, work: Path, used: set,
                  bg_box: tuple | None) -> tuple[Path, int, int] | None:
    """Settle-and-hold frames of the floating card, and where they go on the screen."""
    W, H = size
    spec = beat.get("card") or {}
    q = str(spec.get("query") or "").strip()
    if not q:
        return None
    subj = spec.get("subject") or beat.get("subject")
    ready = str(spec.get("src") or "").strip()
    if ready and Path(ready).is_file():          # a picture made for this card (assets/gen/...)
        log(f"Card {n}: using the prepared picture {ready}")
        box = spec.get("box")
        got = {"kind": "img", "src": Path(ready), "box": tuple(box) if box else None}
    else:
        got = shotpick.pick(q, subj, work / f"pro_card{n:02d}", photos_only=True) or \
            shotpick.pick(q, subj, work / f"pro_cardv{n:02d}")
    if not got:
        log(f"Card {n}: no picture for '{q}', showing the background only")
        return None
    if got["kind"] == "vid":
        img = shotpick._frame_at(Path(got["src"]), float(got.get("start", 0.0)) + 0.6, 1600)
    else:
        img = Image.open(got["src"]).convert("RGB")
    if img is None:
        return None
    content = got.get("content") or (0.0, 0.0, 1.0, 1.0)
    cx0, cy0, cx1, cy1 = content
    img = img.crop((int(cx0 * img.width), int(cy0 * img.height), int(cx1 * img.width), int(cy1 * img.height)))
    style = str(spec.get("style") or "rounded")
    pic = cards.crop_for(img, got.get("box"), style)
    max_w, max_h = int(W * float(spec.get("width", 0.72))), int(H * 0.40)
    head = None
    if bg_box:                                   # where the background subject's head is
        head = ((bg_box[0] + bg_box[2]) / 2, bg_box[1])
    tail = None
    cy = int(H * float(spec.get("y", 0.33)))
    if style == "bubble" and head:
        tail = (head[0] - W / 2, head[1] - cy)
    card = cards.style_card(pic, style, max_w, max_h, str(spec.get("caption") or ""), seed=n, tail_to=tail)
    d, mx, my = cards.settle_frames(card, fps, work / f"pro_cardfx{n:02d}")
    fw, fh = card.width + 2 * mx, card.height + 2 * my
    return d, int(W / 2 - fw / 2), int(cy - fh / 2)


def _render_keep(sh: dict, n: int, data: dict, size: tuple[int, int], fps: int, length: float,
                 tr_out: str, out: Path, work: Path, bright: bool = False, force_fit: bool = False) -> None:
    w, h = size
    beat = sh["beat"]
    kind = beat.get("shot", "clip")
    frames = max(int(round(length * fps)), 2)
    prev = data.get("_prev_src")
    if prev and ((kind == "card" and beat.get("bg", "prev") == "prev")
                 or (kind in ("number", "compare", "text") and beat.get("bg") == "prev")):
        src = dict(prev)
        if src["kind"] == "vid":                 # the background carries on from the shot before
            src["start"] = float(src.get("start", 0.0)) + float(data.get("_prev_len", 0.0))
    else:
        src = footage(beat, n, data["title"], size, work, keep=True)
    src = _ensure_framing(src, beat.get("subject"))
    if kind != "card":
        src = _wide_framing(src, beat.get("subject"))
    src["_wh"] = _probe_wh(Path(src["src"]))
    sh["src"] = src
    camera = beat.get("camera") or ("drift" if kind in ("number", "compare", "text", "card") else "push_in")
    shake = bool(beat.get("shake")) and camera == "punch"
    blend = data.get("_fit_style", "box") == "blend"
    p = framing.plan(*src["_wh"], src.get("content") or (0, 0, 1, 1), src.get("box"), size, 1.06, force_fit,
                     1.22 if blend else 1.0)
    p["style"] = data.get("_fit_style", "box")
    refill = p["style"] == "refill"
    if refill and p["mode"] == "fit":
        # Rakib: never the shrunk picture on a blurred box. A shot of its own gets other
        # footage (or a prepared picture); a blurred background behind a graphic or card
        # is simply shown full screen around the subject.
        if kind in ("clip", "photo") and not beat.get("_cover"):
            return _refill(sh, n, data, size, fps, length, tr_out, out, work, bright, src,
                           "would only fit shrunk")
        p = {**framing.cover_plan(*src["_wh"], src.get("content") or (0, 0, 1, 1), src.get("box"), size),
             "style": "refill"}
    if refill and beat.get("_cover") and kind in ("clip", "photo"):
        sh["covered"] = True
    sh["plan"] = {k: v for k, v in p.items() if k in ("mode", "zmax")}
    inputs: list[str] = []
    if src["kind"] == "vid":
        st = min(float(src.get("start", 0.0)), max(float(src["dur"]) - length - 0.1, 0.0))
        avail = max(float(src["dur"]) - st, 0.5)
        slow = min(max(length / avail, 1.0), 1.6) if avail < length else 1.0
        loop = avail * slow < length
        inputs += [*(["-stream_loop", "-1"] if loop else []), "-ss", f"{st:.2f}", "-i", str(src["src"])]
        pre = f"setpts={slow:.3f}*(PTS-STARTPTS),fps={fps}"
    else:
        inputs += ["-loop", "1", "-framerate", str(fps), "-i", str(src["src"])]
        pre = "null"
    graph = _framed(src, p, size, fps, frames, camera, shake, inputs, work, f"{n:02d}")
    graph = graph.replace("[0:v]", f"[0:v]{pre},", 1)
    chain = f"{graph};[base]{GRADE}{LOOKS.get(beat.get('look'), '')}{BRIGHTEN if bright else ''}"
    if kind in ("number", "compare", "text"):
        chain += ",gblur=sigma=5,eq=brightness=-0.12:saturation=0.85"
    if kind == "card":
        chain += ",gblur=sigma=6,eq=brightness=-0.17:saturation=0.75"
    fx = _fx(sh["tr"], tr_out, length)
    if fx:
        chain += "," + ",".join(fx)
    chain += "[bg0]"
    last = "bg0"
    overlays = []
    if kind in ("number", "compare", "text"):
        mk = _marks(sh)
        ov_dir, oy = _graphic_frames(beat, kind, size, fps, length, work / f"pro_gfx{n:02d}", mk)
        sh["gfx"] = (ov_dir, oy)
        if mk.get("keys") or mk.get("left1") is not None:
            sh["sfx_times"] = [(k, sh.get("b", sh["start"]) + t, g) for k, t, g in
                               _gfx_sounds(beat, kind, mk, fps, length)]
        overlays.append((ov_dir, 0, oy))
    if kind == "card":
        bg_box = framing.on_screen(p, src.get("box"), *src["_wh"], src.get("content") or (0, 0, 1, 1), size)
        got = _card_overlay(beat, n, size, fps, work, set(), bg_box)
        if got:
            overlays.append(got)
    tag = beat.get("tag") or {}
    if tag.get("title"):
        overlays.append(cards.tag_frames(str(tag["title"]), str(tag.get("sub") or ""), size, fps,
                                         work / f"pro_tag{n:02d}"))
    for d, ox, oy in overlays:
        k = len([a for a in inputs if a == "-i"])
        inputs += ["-framerate", str(fps), "-i", str(d / "%04d.png")]
        chain += f";[{last}][{k}:v]overlay={ox}:{oy}:eof_action=repeat[o{k}]"
        last = f"o{k}"
    chain += f";[{last}]format=yuv420p[v]"
    script = work / f"pro_shot{n:02d}.txt"
    script.write_text(chain, encoding="utf-8")
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex_script", str(script),
         "-map", "[v]", "-an", "-frames:v", str(frames), "-r", str(fps), *ENC, str(out)])
    if not bright and kind == "clip":
        yv = _mean_luma(out)
        if yv is not None and yv < DARK_YAVG:
            log(f"Shot {n} is too dark (brightness {yv:.0f}), brightening it")
            return _render_keep(sh, n, data, size, fps, length, tr_out, out, work, True, force_fit)
    # framecheck: is the whole subject on screen on the first and last frame?
    region = (0.0, 0.0, 1.0, 1.0)
    if p["mode"] == "fit":                       # in fit the picture is the panel, not the screen
        sw, shh = p["show"]
        top, left = framing.fit_top(p, size), (w - sw) // 2
        region = (left / w, top / h, (left + sw) / w, (top + shh) / h)
    fc = _framecheck(out, beat, length, size, work, n, region) if kind in ("clip", "photo") else None
    if fc is not None:
        sh["framecheck"] = {**fc, "mode": p["mode"], "refit": force_fit or bool(beat.get("_repick"))}
        if refill and fc["cut"] and not beat.get("_cover"):
            return _refill(sh, n, data, size, fps, length, tr_out, out, work, bright, src,
                           f"cut at the {fc['where']}")
        if refill:
            pass
        elif fc["cut"] and not force_fit and src.get("box"):
            log(f"Framecheck: shot {n} cuts the {beat.get('subject')} ({fc['where']}), showing it whole instead")
            return _render_keep(sh, n, data, size, fps, length, tr_out, out, work, bright, True)
        if not refill and fc["cut"] and not beat.get("_repick") and src.get("id"):
            # still cut with the whole picture shown: the source itself cuts the subject
            log(f"Framecheck: shot {n} footage cuts the {beat.get('subject')} itself ({fc['where']}), "
                f"choosing other footage")
            shotpick.BANNED.add(src["id"])
            sh["beat"] = {**beat, "_repick": 1}
            return _render_keep(sh, n, data, size, fps, length, tr_out, out, work, bright, False)
    if beat.get("hook"):
        _hook_twist(out, size, fps, frames, work, n, beat.get("hook"))
    data["_prev_src"] = {k: v for k, v in src.items() if k != "_wh"}
    data["_prev_len"] = length


def _hook_twist(seg: Path, size: tuple[int, int], fps: int, frames: int, work: Path, n: int, spec) -> None:
    """The opening snaps in like an owl's head: the picture starts turned and zoomed in,
    whips round to straight with one small overshoot, motion-blurred, through a short white
    flash. Only the first ~0.6 s are touched; the subject stays whole once it settles."""
    w, h = size
    spec = spec if isinstance(spec, dict) else {}
    a0 = float(spec.get("angle", -0.38))                  # radians at the first frame
    k = min(int(float(spec.get("seconds", 0.6)) * fps), frames - 1)
    d = work / f"pro_hook{n:02d}"
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("*.png"):
        old.unlink()
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(seg), "-frames:v", str(k), str(d / "src%04d.png")])

    T = k / fps

    def ang(t: float) -> float:                           # fades to exactly straight by T
        return a0 * math.exp(-t * 6.0) * math.cos(t * 10.0) * max(1 - t / T, 0.0)

    def zoom(t: float, a: float) -> float:                # and exactly to the shot's own zoom
        need = math.cos(abs(a)) + (h / w) * math.sin(abs(a)) + 0.02
        return max(1.0 + 0.55 * math.exp(-t * 5.0) * max(1 - t / T, 0.0) ** 2, need)

    for i in range(k):
        img = Image.open(d / f"src{i + 1:04d}.png").convert("RGB")
        acc = None
        subs = 4
        for j in range(subs):                             # motion blur: the turn within one frame
            t = (i + j / subs) / fps
            a = ang(t)
            z = zoom(t, a)
            big = img.resize((int(w * z) // 2 * 2, int(h * z) // 2 * 2), Image.BICUBIC)
            rot = big.rotate(math.degrees(a), resample=Image.BICUBIC)
            x0, y0 = (rot.width - w) // 2, (rot.height - h) // 2
            fr = np.asarray(rot.crop((x0, y0, x0 + w, y0 + h)), np.float32)
            acc = fr if acc is None else acc + fr
        fr = acc / subs
        flash = max(0.0, 0.6 - i * 0.2)                 # white flash on the first frames
        if flash > 0:
            fr = fr * (1 - flash) + 255 * flash
        Image.fromarray(np.clip(fr, 0, 255).astype(np.uint8)).save(d / f"{i:04d}.png", compress_level=1)
    tmp = seg.with_name(seg.stem + "_hook.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(d / "%04d.png"), "-i", str(seg),
         "-filter_complex", f"[0:v]format=yuv420p,setsar=1[a];[1:v]trim=start_frame={k},setpts=PTS-STARTPTS,"
         f"format=yuv420p,setsar=1[b];[a][b]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-an",
         "-frames:v", str(frames), "-r", str(fps), *ENC, str(tmp)])
    shutil.move(str(tmp), str(seg))
    log(f"Shot {n}: hook twist on the first {k} frames")


def _gen_image(beat: dict, data: dict) -> str | None:
    """The prepared picture for a beat: its own "gen", else an unused one of the script's
    gen_pool for the same subject (pictures made in advance, kept in the repo)."""
    used = data.setdefault("_gen_used", [])
    own = str(beat.get("gen") or "").strip()
    if own and Path(own).is_file() and own not in used:
        used.append(own)
        return own
    pool = (data.get("gen_pool") or {}).get(str(beat.get("subject") or ""), [])
    for g in pool:
        if Path(str(g)).is_file() and str(g) not in used:
            used.append(str(g))
            return str(g)
    return None


def _refill(sh: dict, n: int, data: dict, size: tuple[int, int], fps: int, length: float, tr_out: str,
            out: Path, work: Path, bright: bool, src: dict, why: str) -> None:
    """The footage doesn't show the whole subject full screen: other footage (twice), then a
    prepared picture, and only then the screen centred on the subject (flagged in the QC)."""
    beat = sh["beat"]
    rp = int(beat.get("_repick", 0))
    subj = beat.get("subject")
    if src.get("id") and not src.get("_gen") and rp < 2:
        log(f"Refill: shot {n} footage {src['id']} {why} ({subj}), choosing other footage")
        shotpick.BANNED.add(src["id"])
        sh["beat"] = {**beat, "_repick": rp + 1}
        sh["replaced"] = f"other footage ({why})"
        return _render_keep(sh, n, data, size, fps, length, tr_out, out, work, bright, False)
    if not src.get("_gen"):
        g = _gen_image(beat, data)
        if g:
            log(f"Refill: shot {n} {why}, using the prepared picture {g}")
            sh["beat"] = {**beat, "src": g, "_repick": 3}
            sh["replaced"] = f"prepared picture {Path(g).name} ({why})"
            return _render_keep(sh, n, data, size, fps, length, tr_out, out, work, bright, False)
    log(f"Refill: shot {n} {why} and nothing else fits, showing it full screen around the {subj}")
    sh["beat"] = {**beat, "_cover": True}
    return _render_keep(sh, n, data, size, fps, length, tr_out, out, work, bright, False)


def _marks(sh: dict) -> dict:
    """Times (seconds from the start of this shot's clip) of the words a graphic waits for."""
    wts, beat = sh.get("wts") or [], sh["beat"]
    if not wts:
        return {}
    at = lambda k: max(wts[min(int(k), len(wts) - 1)] - sh.get("b", sh["start"]), 0.0)
    wte = sh.get("wte") or wts
    b0 = sh.get("b", sh["start"])

    def ref(k, edge="start") -> float:
        lst = wte if edge == "end" else wts
        return max(lst[min(int(k), len(lst) - 1)] - b0, 0.0)
    m = {}
    rk = ((beat.get("compare") or {}).get("right") or {}).get("at_word")
    if rk is not None:
        m["right"] = at(rk)
    ek = (beat.get("number") or {}).get("end_word")
    if ek is not None:
        m["end"] = at(ek)
    keys = (beat.get("number") or {}).get("keys")
    if keys:      # [[word, value, "start"|"end"], ...]: the count is at that value on that word
        m["keys"] = sorted((ref(k[0], k[2] if len(k) > 2 else "start"), float(k[1])) for k in keys)
        m["end"] = m["keys"][-1][0]
    for side in ("left", "right"):
        sp = (beat.get("compare") or {}).get(side) or {}
        if sp.get("land_word") is not None:
            m[side + "0"] = ref(sp.get("from_word", 0))
            m[side + "1"] = ref(sp["land_word"], sp.get("land_edge", "end"))
    return m


def _framecheck(seg: Path, beat: dict, length: float, size: tuple[int, int], work: Path, n: int,
                region: tuple = (0.0, 0.0, 1.0, 1.0)) -> dict | None:
    """First and last frame of a shot: the subject must not touch any edge of the picture
    (the screen, or the panel in fit mode), found with the wide net so a partly found or
    second animal counts too. Frames are kept for the framecheck sheet."""
    subj = beat.get("subject")
    a, b = work / f"pro_fc{n:02d}a.jpg", work / f"pro_fc{n:02d}b.jpg"
    for t, f in ((0.04, a), (max(length - 0.12, 0.05), b)):
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(seg), "-frames:v", "1",
             "-vf", "scale=540:-2", str(f)])
    if not subj or not framing.available():
        return {"cut": False, "where": "", "checked": False}
    where = []
    for f, name in ((a, "first"), (b, "last")):
        if not f.exists():
            continue
        im = Image.open(f).convert("RGB")
        kb = framing.wide_box(framing.find_boxes(im, str(subj)))
        edges = framing.cut_edges(kb, region)
        if edges:
            where.append(f"{name}: " + "+".join(edges))
    return {"cut": bool(where), "where": "; ".join(where), "checked": True}


def _framecheck_sheet(shots: list[dict], work: Path, out: Path) -> None:
    """One picture: first and last frame of every shot, marked OK or CUT."""
    rows = []
    for n, sh in enumerate(shots):
        a, b = work / f"pro_fc{n:02d}a.jpg", work / f"pro_fc{n:02d}b.jpg"
        if not a.exists() or not b.exists():
            continue
        rows.append((n, sh, Image.open(a).convert("RGB"), Image.open(b).convert("RGB")))
    if not rows:
        return
    tw, th = 270, 480
    per = 4                                   # shots per sheet row (two frames each)
    cols = per * 2
    lines = math.ceil(len(rows) / per)
    sheet = Image.new("RGB", (cols * tw, lines * (th + 40)), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    f = _font(22)
    for i, (n, sh, fa, fb) in enumerate(rows):
        x0, y0 = (i % per) * 2 * tw, (i // per) * (th + 40)
        sheet.paste(fa.resize((tw, th)), (x0, y0 + 40))
        sheet.paste(fb.resize((tw, th)), (x0 + tw, y0 + 40))
        fc = sh.get("framecheck") or {}
        ok = not fc.get("cut")
        mode = (sh.get("plan") or {}).get("mode", "")
        label = f"#{n} {sh['start']:.1f}s {mode}{' refit' if fc.get('refit') else ''} {'OK' if ok else 'CUT'}"
        d.text((x0 + 8, y0 + 8), label, font=f, fill=(120, 230, 120) if ok else (255, 90, 90))
    sheet.save(out, quality=86)

def _mean_luma(path: Path) -> float | None:
    res = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-vf",
                          "fps=4,scale=270:-2,signalstats,metadata=print:key=lavfi.signalstats.YAVG",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    vals = [float(v) for v in re.findall(r"YAVG=([\d.]+)", res)]
    return sum(vals) / len(vals) if vals else None


# ================================================================= graphics
def _ease_out(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def _fit(text: str, max_w: float, start: float) -> ImageFont.FreeTypeFont:
    size = start
    while size > 30:
        f = _font(size)
        if f.getlength(text) <= max_w:
            return f
        size -= 6
    return _font(30)


def _glow_text(layer: Image.Image, xy: tuple[float, float], text: str, font, fill, glow=YELLOW,
               anchor="mm", glow_alpha=150) -> None:
    g = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).text(xy, text, font=font, fill=glow + (glow_alpha,), anchor=anchor)
    g = g.filter(ImageFilter.GaussianBlur(18))
    layer.alpha_composite(g)
    d = ImageDraw.Draw(layer)
    d.text((xy[0] + 5, xy[1] + 7), text, font=font, fill=(0, 0, 0, 120), anchor=anchor)
    d.text(xy, text, font=font, fill=fill, anchor=anchor)


def _fmt(v: float, dec: int) -> str:
    return f"{v:,.{dec}f}"


def _graphic_frames(beat: dict, kind: str, size: tuple[int, int], fps: int, length: float,
                    out_dir: Path, marks: dict | None = None) -> tuple[Path, int]:
    """PNG frames (transparent) of the animated graphic; the last frame holds.
    marks: times of the words the graphic waits for ("end" of a count, "right" of a compare)."""
    w, h = size
    marks = marks or {}
    out_dir.mkdir(parents=True, exist_ok=True)
    rw, rh, oy = w, int(h * 0.38), int(h * 0.19)          # region 1080x730 at y=365
    if kind == "compare":
        rw, rh, oy = w, int(h * 0.42), int(h * 0.13)      # taller: the bone stacks
    last = max([v for v in marks.values() if isinstance(v, (int, float))] or [0.0])
    anim = min(length, max(1.6, last + 1.3))
    n = max(int(anim * fps), 2)
    for old in out_dir.glob("*.png"):
        old.unlink()
    for i in range(n):
        t = i / fps
        img = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
        if kind == "number":
            _draw_number(img, beat.get("number") or {}, t, marks)
        elif kind == "compare":
            spec = beat.get("compare") or {}
            if str(spec.get("style", "")) == "stack":
                _draw_stack(img, spec, t, marks)
            else:
                _draw_compare(img, spec, t)
        else:
            _draw_title(img, str(beat.get("text") or beat.get("query") or ""), t)
        img.save(out_dir / f"{i:04d}.png", compress_level=1)
    return out_dir, oy


def _scaled(img: Image.Image, layer: Image.Image, s: float, alpha: float = 1.0) -> None:
    if s <= 0.01 or alpha <= 0.01:
        return
    lw, lh = layer.size
    if abs(s - 1) > 0.005:
        layer = layer.resize((max(int(lw * s), 1), max(int(lh * s), 1)), Image.BICUBIC)
    if alpha < 1:
        a = layer.getchannel("A").point(lambda v: int(v * alpha))
        layer.putalpha(a)
    img.alpha_composite(layer, ((img.width - layer.width) // 2, (img.height - layer.height) // 2))


def _scale_curve(t: float, start: float = 0.0, dur: float = 0.34) -> float:
    u = (t - start) / dur
    if u <= 0:
        return 0.0
    if u >= 1:
        return 1.0
    return 0.55 + 0.45 * _ease_out(u) + 0.10 * math.sin(math.pi * u)


def _draw_number(img: Image.Image, spec: dict, t: float, marks: dict | None = None) -> None:
    rw, rh = img.size
    to = float(spec.get("to", 0) or 0)
    frm = float(spec.get("from", 0) or 0)
    dec = int(spec.get("decimals", 0) or (0 if float(to).is_integer() else 1))
    val, land = _num_value(spec, t, marks)
    k = (val - frm) / (to - frm) if to != frm else 1.0
    if spec.get("dial"):
        _draw_dial(img, spec, k, t, land)
    num = f"{spec.get('prefix', '')}{_fmt(val, dec)}"
    final = f"{spec.get('prefix', '')}{_fmt(to, dec)}"
    suffix = str(spec.get("suffix", "")).upper()
    label = str(spec.get("label", "")).upper()
    layer = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    big = _fit(final + suffix, rw * (0.50 if spec.get("dial") else 0.78), 260 if not spec.get("dial") else 190)
    suf_font = _font(big.size * 0.42)
    nw = big.getlength(final)
    sw = suf_font.getlength(suffix) if suffix else 0
    x0 = (rw - nw - sw - (16 if suffix else 0)) / 2
    cy = rh * 0.52
    _glow_text(layer, (x0 + nw / 2, cy), num, big, (255, 255, 255, 255))
    if suffix == "°":                                    # a degree sign sits high, like in print
        df = _font(big.size * 0.55)
        d.text((x0 + nw + 10 + 4, cy - big.size * 0.42 + 5), "°", font=df, fill=(0, 0, 0, 120), anchor="lm")
        d.text((x0 + nw + 10, cy - big.size * 0.42), "°", font=df, fill=YELLOW + (255,), anchor="lm")
        suffix = ""
    if suffix:
        d.text((x0 + nw + 16 + 4, cy + big.size * 0.28 + 5), suffix, font=suf_font, fill=(0, 0, 0, 120), anchor="ls")
        d.text((x0 + nw + 16, cy + big.size * 0.28), suffix, font=suf_font, fill=YELLOW + (255,), anchor="ls")
    if label:
        lf = _fit(label, rw * (0.8 if not spec.get("dial") else 0.36), 70 if not spec.get("dial") else 42)
        ly = cy - big.size * 0.62 if not spec.get("dial") else cy + big.size * 0.78
        _spaced(d, (rw / 2, ly), label, lf, (255, 255, 255, 235))
    # accent bar under the number
    bw = (nw + sw + 16) * _ease_out((t - 0.25) / 0.6) * (0 if spec.get("dial") else 1)
    by = cy + big.size * 0.48
    if bw > 4:
        d.rounded_rectangle(((rw - bw) / 2, by, (rw + bw) / 2, by + 14), radius=7, fill=YELLOW + (255,))
    pulse = 0.0
    if land is not None and t >= land:                   # a small beat when the count lands
        q = (t - land) / 0.32
        pulse = 0.10 * math.sin(math.pi * q) if q < 1 else 0.0
    _scaled(img, layer, _scale_curve(t) + pulse, min(1.0, t / 0.12))


def _num_value(spec: dict, t: float, marks: dict | None = None) -> tuple[float, float | None]:
    """The count shown at time t, and when it lands. With word keys the count follows the
    voice: eased in on the first word, steady between the words, eased out on the last."""
    to = float(spec.get("to", 0) or 0)
    frm = float(spec.get("from", 0) or 0)
    keys = (marks or {}).get("keys")
    if keys:
        pts = [(float(a), float(v)) for a, v in keys]
        if t <= pts[0][0]:
            return pts[0][1], pts[-1][0]
        if t >= pts[-1][0]:
            return pts[-1][1], pts[-1][0]
        for j in range(len(pts) - 1):
            (a, va), (b, vb) = pts[j], pts[j + 1]
            if a <= t <= b:
                u = (t - a) / max(b - a, 1e-3)
                if len(pts) == 2:
                    u = u * u * (3 - 2 * u)
                elif j == 0:
                    u = u ** 1.7                          # eases in
                elif j == len(pts) - 2:
                    u = 1 - (1 - u) ** 1.7                # settles on the word
                return va + (vb - va) * u, pts[-1][0]
    te = float((marks or {}).get("end") or 1.17)         # the count lands on this spoken word
    te = min(max(te, 0.6), 3.2)
    u = min(max((t - 0.12) / (te - 0.12), 0.0), 1.0)
    k = 1 - (1 - u) ** 2.2                               # steady, then settles on the word
    return frm + (to - frm) * k, te


def _draw_dial(img: Image.Image, spec: dict, k: float, t: float, land: float | None = None) -> None:
    """A ring that sweeps round with the count (degrees), with a glowing head."""
    rw, rh = img.size
    to = float(spec.get("to", 0) or 0)
    full = float(spec.get("dial_full", 360) or 360)
    cx, cy = rw / 2, rh * 0.52
    r = min(rw, rh) * 0.40
    a = min(1.0, t / 0.2)
    lay = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    box = (cx - r, cy - r, cx + r, cy + r)
    d.ellipse(box, outline=(255, 255, 255, int(70 * a)), width=16)
    sweep = 360 * (to / full) * k
    if sweep > 0.5:
        glow = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
        ImageDraw.Draw(glow).arc(box, -90, -90 + sweep, fill=YELLOW + (int(150 * a),), width=34)
        lay.alpha_composite(glow.filter(ImageFilter.GaussianBlur(14)))
        d.arc(box, -90, -90 + sweep, fill=YELLOW + (int(255 * a),), width=20)
        ang = math.radians(-90 + sweep)
        hx, hy = cx + r * math.cos(ang), cy + r * math.sin(ang)
        d.ellipse((hx - 19, hy - 19, hx + 19, hy + 19), fill=(255, 255, 255, int(255 * a)))
        if land is not None and 0 <= t - land < 0.45:   # the ring rings out when the count lands
            q = (t - land) / 0.45
            rr = r * (1 + 0.22 * q)
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=YELLOW + (int(200 * (1 - q)),),
                      width=max(int(14 * (1 - q)), 2))
        # tick marks every 90 degrees
    for q in range(4):
        ang = math.radians(-90 + 90 * q)
        x0, y0 = cx + (r - 34) * math.cos(ang), cy + (r - 34) * math.sin(ang)
        x1, y1 = cx + (r - 50) * math.cos(ang), cy + (r - 50) * math.sin(ang)
        d.line((x0, y0, x1, y1), fill=(255, 255, 255, int(150 * a)), width=5)
    img.alpha_composite(lay)


def _bone(d: ImageDraw.ImageDraw, cx: float, cy: float, w: float, h: float, col: tuple, a: float) -> None:
    """One vertebra: a rounded body with a thinner bar either side."""
    al = int(255 * a)
    d.rounded_rectangle((cx - w / 2 + 5, cy - h * 0.18 + 6, cx + w / 2 + 5, cy + h * 0.18 + 6), radius=h * 0.18,
                        fill=(0, 0, 0, int(90 * a)))
    d.rounded_rectangle((cx - w * 0.31 + 5, cy - h / 2 + 6, cx + w * 0.31 + 5, cy + h / 2 + 6), radius=h * 0.42,
                        fill=(0, 0, 0, int(110 * a)))
    d.rounded_rectangle((cx - w / 2, cy - h * 0.18, cx + w / 2, cy + h * 0.18), radius=h * 0.18, fill=col + (al,))
    d.rounded_rectangle((cx - w * 0.31, cy - h / 2, cx + w * 0.31, cy + h / 2), radius=h * 0.42, fill=col + (al,))
    d.rounded_rectangle((cx - w * 0.22, cy - h * 0.30, cx + w * 0.22, cy - h * 0.12), radius=h * 0.1,
                        fill=(255, 255, 255, int(90 * a)))


def _draw_stack(img: Image.Image, spec: dict, t: float, marks: dict | None = None) -> None:
    """Two columns of vertebrae that stack up one by one with the count, the second
    column arriving on its spoken word, then a "2x" badge between them."""
    rw, rh = img.size
    marks = marks or {}
    left, right = spec.get("left") or {}, spec.get("right") or {}
    lv, rv = int(left.get("value", 1) or 1), int(right.get("value", 1) or 1)
    top_v = max(lv, rv, 1)
    unit = str(spec.get("unit", "")).upper()
    layer = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    base, roof = rh * 0.84, rh * 0.22
    pitch = (base - roof) / top_v
    bh, bw = pitch * 0.74, rw * 0.21
    (lt0, lstep), (rt0, rstep), badge_t = _stack_times(spec, marks)
    vf = _font(86)
    cols = ((left, lv, rw * 0.28, YELLOW, lt0, lstep), (right, rv, rw * 0.72, (240, 240, 240), rt0, rstep))
    done_at = 0.0
    for item, v, cx, col, t0, step in cols:
        shown = 0
        for i in range(v):
            ti = t0 + i * step
            u = (t - ti) / 0.14
            if u <= 0:
                break
            shown = i + 1
            e = _ease_out(min(u, 1.0))
            yc = base - pitch * (i + 0.5) - (1 - e) * pitch * 0.9
            _bone(d, cx, yc, bw * (0.7 + 0.3 * e), bh, col, min(1.0, u * 1.6))
        done_at = max(done_at, t0 + v * step)
        if shown:
            ytop = base - pitch * shown
            txt = str(shown)
            land = t0 + (v - 1) * step + 0.14             # the last bone has dropped in
            q = (t - land) / 0.3
            f = _font(86 * (1 + 0.28 * math.sin(math.pi * q))) if 0 <= q < 1 else vf
            if shown == v and 0 <= q < 1:                 # the full count glows for a moment
                gl = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
                ImageDraw.Draw(gl).rounded_rectangle((cx - bw * 0.62, ytop - 10, cx + bw * 0.62, base + 6),
                                                     radius=30, fill=col + (int(110 * (1 - q)),))
                layer.alpha_composite(gl.filter(ImageFilter.GaussianBlur(22)))
            d.text((cx + 4, ytop - 52 + 5), txt, font=f, fill=(0, 0, 0, 120), anchor="mm")
            d.text((cx, ytop - 52), txt, font=f, fill=col + (255,), anchor="mm")
        lab = str(item.get("label", "")).upper()
        if lab and t >= t0 - 0.05:
            f = _fit(lab, bw * 1.6, 58)
            la = min(1.0, (t - t0 + 0.05) / 0.15)
            d.text((cx + 3, base + 52 + 4), lab, font=f, fill=(0, 0, 0, int(120 * la)), anchor="mm")
            d.text((cx, base + 52), lab, font=f, fill=col + (int(255 * la),), anchor="mm")
    if unit:
        _spaced(d, (rw / 2, rh * 0.07), unit, _font(54), (255, 255, 255, 230), 0.12)
    badge = str(spec.get("badge", "")).upper()
    if badge_t is None:
        badge_t = done_at + 0.12
    if badge and t > badge_t:
        s = _scale_curve(t, badge_t, 0.3)
        bf = _font(92)
        tw = bf.getlength(badge)
        bl = Image.new("RGBA", (int(tw + 90), 150), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bl)
        bd.rounded_rectangle((8, 22, bl.width - 8, 128), radius=40, fill=YELLOW + (255,))
        bd.text((bl.width / 2, 76), badge, font=bf, fill=(18, 18, 18, 255), anchor="mm")
        bl = bl.rotate(-6, resample=Image.BICUBIC, expand=True)
        if abs(s - 1) > 0.01:
            bl = bl.resize((max(int(bl.width * s), 1), max(int(bl.height * s), 1)), Image.BICUBIC)
        ymid = base - pitch * (lv + rv) / 2
        layer.alpha_composite(bl, (int(rw * 0.5 - bl.width / 2), int(ymid - bl.height / 2)))
    _scaled(img, layer, 1.0, min(1.0, t / 0.15))


def _stack_times(spec: dict, marks: dict | None) -> tuple[tuple[float, float], tuple[float, float], float | None]:
    """When each column of bones starts and how fast it stacks, and when the badge pops.
    With word marks the last bone of a column drops in exactly on its spoken word."""
    marks = marks or {}
    lv = int((spec.get("left") or {}).get("value", 1) or 1)
    rv = int((spec.get("right") or {}).get("value", 1) or 1)
    out, badge = [], None
    for side, v in (("left", lv), ("right", rv)):
        a, b = marks.get(side + "0"), marks.get(side + "1")
        if a is not None and b is not None:
            step = max((b - 0.14 - a) / max(v - 1, 1), 0.03)
            out.append((a, step))
            badge = b + 0.04
        else:
            out.append(None)
    step0 = min(0.075, 1.0 / max(lv, rv, 1))
    if out[0] is None:
        out[0] = (0.10, step0)
    if out[1] is None:
        tr = float(marks.get("right") if marks.get("right") is not None else 0.95) - 0.08
        out[1] = (max(tr, 0.4), step0)
    return out[0], out[1], badge


def _gfx_sounds(beat: dict, kind: str, marks: dict, fps: int, length: float) -> list[tuple[str, float, float]]:
    """Sounds that follow the graphic itself (times from the start of the shot): a tick each
    time the count passes a step or a bone drops in, a ding when it lands, a thud on the badge."""
    ev: list[tuple[str, float, float]] = []
    if kind == "number":
        spec = beat.get("number") or {}
        frm, to = float(spec.get("from", 0) or 0), float(spec.get("to", 0) or 0)
        steps = 9
        last, land = 0, None
        for i in range(int(length * fps)):
            v, land = _num_value(spec, i / fps, marks)
            q = int((v - frm) / (to - frm) * steps + 1e-6) if to != frm else steps
            if q > last and q < steps:
                ev.append(("tick", i / fps, 0.6))
            last = max(last, q)
        if land is not None:
            ev.append(("ding", land, 0.6))
    elif kind == "compare" and str((beat.get("compare") or {}).get("style", "")) == "stack":
        spec = beat.get("compare") or {}
        (lt0, ls), (rt0, rs), badge = _stack_times(spec, marks)
        lv = int((spec.get("left") or {}).get("value", 1) or 1)
        rv = int((spec.get("right") or {}).get("value", 1) or 1)
        for t0, st, v in ((lt0, ls, lv), (rt0, rs, rv)):
            for i in range(v):
                ev.append(("tick", t0 + i * st + 0.07, 0.55))
        ev.append(("ding", lt0 + (lv - 1) * ls + 0.14, 0.5))
        if spec.get("badge"):
            ev.append(("thud", badge if badge is not None else rt0 + rv * rs + 0.12, 0.9))
    return ev


def _spaced(d: ImageDraw.ImageDraw, center: tuple[float, float], text: str, font, fill, track: float = 0.08) -> None:
    gap = font.size * track
    total = sum(font.getlength(c) for c in text) + gap * (len(text) - 1)
    x = center[0] - total / 2
    for c in text:
        d.text((x + 3, center[1] + 4), c, font=font, fill=(0, 0, 0, 110), anchor="lm")
        d.text((x, center[1]), c, font=font, fill=fill, anchor="lm")
        x += font.getlength(c) + gap


def _draw_compare(img: Image.Image, spec: dict, t: float) -> None:
    rw, rh = img.size
    left, right = spec.get("left") or {}, spec.get("right") or {}
    unit = str(spec.get("unit", "")).upper()
    lv, rv = float(left.get("value", 1) or 1), float(right.get("value", 1) or 1)
    top = max(lv, rv, 1e-6)
    layer = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    base, maxh, bw = rh * 0.80, rh * 0.52, rw * 0.24
    vf, lf = _font(84), _font(54)
    for k, (item, v, cx, col, t0) in enumerate(((left, lv, rw * 0.31, (245, 245, 245), 0.05),
                                                 (right, rv, rw * 0.69, YELLOW, 0.45))):
        g = _ease_out((t - t0) / 0.8)
        bh = maxh * v / top * g
        if bh > 2:
            d.rounded_rectangle((cx - bw / 2 + 6, base - bh + 8, cx + bw / 2 + 6, base + 8), radius=22,
                                fill=(0, 0, 0, 110))
            d.rounded_rectangle((cx - bw / 2, base - bh, cx + bw / 2, base), radius=22, fill=col + (255,))
        if g > 0:
            txt = _fmt(v * g, 0 if float(v).is_integer() else 1)
            d.text((cx + 4, base - bh - 50 + 5), txt, font=vf, fill=(0, 0, 0, 120), anchor="mm")
            d.text((cx, base - bh - 50), txt, font=vf, fill=(255, 255, 255, 255), anchor="mm")
        lab = str(item.get("label", "")).upper()
        if lab:
            f = _fit(lab, bw * 1.5, 54)
            d.text((cx + 3, base + 52 + 4), lab, font=f, fill=(0, 0, 0, 120), anchor="mm")
            d.text((cx, base + 52), lab, font=f, fill=col + (255,), anchor="mm")
    if unit:
        _spaced(d, (rw / 2, rh * 0.08), unit, lf, (255, 255, 255, 230), 0.12)
    _scaled(img, layer, 1.0, min(1.0, t / 0.15))


def _draw_title(img: Image.Image, text: str, t: float) -> None:
    rw, rh = img.size
    words = text.upper().split()
    if not words:
        return
    f = _font(150)
    lines, line = [], []
    for wd in words:
        trial = " ".join(line + [wd])
        if line and f.getlength(trial) > rw * 0.84:
            lines.append(line)
            line = [wd]
        else:
            line.append(wd)
    lines.append(line)
    while max(f.getlength(" ".join(l)) for l in lines) > rw * 0.88 and f.size > 60:
        f = _font(f.size - 10)
    lh = f.size * 1.08
    y0 = rh / 2 - lh * (len(lines) - 1) / 2
    idx = 0
    for li, ln in enumerate(lines):
        widths = [f.getlength(wd) for wd in ln]
        space = f.getlength(" ")
        x = rw / 2 - (sum(widths) + space * (len(ln) - 1)) / 2
        for wd, ww in zip(ln, widths):
            start = 0.09 * idx
            s = _scale_curve(t, start, 0.28)
            if s > 0:
                lay = Image.new("RGBA", (int(ww + 80), int(f.size * 1.6)), (0, 0, 0, 0))
                col = YELLOW if idx % 2 else (255, 255, 255)
                _glow_text(lay, (lay.width / 2, lay.height / 2), wd, f, col + (255,), glow=(0, 0, 0), glow_alpha=160)
                if abs(s - 1) > 0.01:
                    sc = 1 + (1.6 - 1) * (1 - _ease_out((t - start) / 0.28)) if t - start < 0.28 else 1.0
                    lay = lay.resize((max(int(lay.width * sc), 1), max(int(lay.height * sc), 1)), Image.BICUBIC)
                a = min(1.0, (t - start) / 0.1)
                if a < 1:
                    lay.putalpha(lay.getchannel("A").point(lambda v, a=a: int(v * a)))
                img.alpha_composite(lay, (int(x + ww / 2 - lay.width / 2), int(y0 + li * lh - lay.height / 2)))
            x += ww + space
            idx += 1


# ================================================================= captions
def _highlight_mask(scene: dict, tokens: list[str]) -> list[int]:
    """For every word: 0, or an id shared by the words of one highlight phrase."""
    from .render import scene_highlights
    norm = [re.sub(r"[^a-z0-9']", "", t.lower()) for t in tokens]
    mask = [0] * len(tokens)
    gid = 0
    for ph in scene_highlights(scene, " ".join(tokens)):
        pw = [re.sub(r"[^a-z0-9']", "", x.lower()) for x in ph.split()]
        pw = [x for x in pw if x]
        if not pw:
            continue
        for s in range(len(norm) - len(pw) + 1):
            if norm[s:s + len(pw)] == pw and not any(mask[s:s + len(pw)]):
                gid += 1
                for k in range(s, s + len(pw)):
                    mask[k] = gid
                break
    return mask


def _display(tok: str) -> str:
    t = tok.replace("⁠", "").strip()
    t = re.sub(r"^[\"'“‘(]+|[\"'”’),.;:…]+$", "", t)
    t = t.rstrip(".")
    return t.upper()


def _chunks(words: list[dict]) -> list[list[dict]]:
    out, cur = [], []
    for wd in words:
        disp = _display(wd["tok"])
        if not disp:
            continue
        wd = {**wd, "disp": disp}
        if cur:
            same_phrase = wd["hi"] and wd["hi"] == cur[-1]["hi"]
            chars = sum(len(c["disp"]) + 1 for c in cur) + len(disp)
            limit_w, limit_c = (5, 24) if same_phrase else (3, 15)
            brk = (wd["scene"] != cur[-1]["scene"] or len(cur) >= limit_w or chars > limit_c
                   or (cur[-1]["tok"][-1:] in ",;:.!?…" and not same_phrase)
                   or (cur[-1]["hi"] and not same_phrase and len(cur) >= 2))
            if brk:
                out.append(cur)
                cur = []
        cur.append(wd)
    if cur:
        out.append(cur)
    return out


def _round_rect(wd: float, ht: float, r: float) -> str:
    c = r * 0.552
    return (f"m {r:.1f} 0 l {wd - r:.1f} 0 b {wd - r + c:.1f} 0 {wd:.1f} {r - c:.1f} {wd:.1f} {r:.1f} "
            f"l {wd:.1f} {ht - r:.1f} b {wd:.1f} {ht - r + c:.1f} {wd - r + c:.1f} {ht:.1f} {wd - r:.1f} {ht:.1f} "
            f"l {r:.1f} {ht:.1f} b {r - c:.1f} {ht:.1f} 0 {ht - r + c:.1f} 0 {ht - r:.1f} "
            f"l 0 {r:.1f} b 0 {r - c:.1f} {r - c:.1f} 0 {r:.1f} 0")


def _t(sec: float) -> str:
    sec = max(sec, 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_captions(words: list[dict], size: tuple[int, int], out: Path,
                   hidden: list[tuple[float, float]]) -> tuple[Path, list[tuple], list[float]]:
    """Word-by-word animated captions as an .ass file.

    Returns (file, boxes, pill_times): boxes are the screen areas the captions use
    (for the quality check), pill_times when a yellow key-word pill pops in.
    """
    w, h = size
    fs = int(h * 0.053)                          # 101 px at 1920
    cy_base = int(h * 0.615)
    max_w = w * 0.78
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{ASS_FONT},{fs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,0,0,0,0,100,100,1,0,1,{max(5, fs // 13)},{max(3, fs // 24)},5,0,0,0,1
Style: Key,{ASS_FONT},{fs},&H00121212,&H00121212,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,0,0,5,0,0,0,1
Style: Pill,{ASS_FONT},{fs},&H000AD6FF,&H000AD6FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,0,{max(3, fs // 22)},5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events, boxes, pills = [], [], []
    chunks = [c for c in _chunks(words)
              if not any(a - 0.05 <= (c[0]["t0"] + c[-1]["t1"]) / 2 <= b + 0.05 for a, b in hidden)]
    for ci, ch in enumerate(chunks):
        start = ch[0]["t0"] - 0.06
        nxt = chunks[ci + 1][0]["t0"] - 0.06 if ci + 1 < len(chunks) else ch[-1]["t1"] + 0.6
        end = min(nxt, ch[-1]["t1"] + 0.9)
        size_px = fs
        while True:
            f = _font(size_px * ASS_K)
            space = f.getlength(" ") + size_px * 0.17     # room for the outline and the pop
            widths = [f.getlength(c["disp"]) + size_px * 0.01 * len(c["disp"]) for c in ch]
            lines, cur, cw = [], [], 0.0
            for k, ww in enumerate(widths):
                add = ww + (space if cur else 0)
                if cur and cw + add > max_w:
                    lines.append(cur)
                    cur, cw = [k], ww
                else:
                    cur.append(k)
                    cw += add
            lines.append(cur)
            if len(lines) <= 2 and all(widths[k] <= max_w for k in range(len(ch))) or size_px < 50:
                break
            size_px -= 6
        line_h = size_px * 0.95
        cap_h = size_px * ASS_K * 0.72
        y_first = cy_base - line_h * (len(lines) - 1) / 2
        bord = max(5, size_px // 13)
        for li, ln in enumerate(lines):
            lw = sum(widths[k] for k in ln) + space * (len(ln) - 1)
            x = w / 2 - lw / 2
            y = y_first + li * line_h
            boxes.append((x - bord - lw * 0.06, y - cap_h / 2 - bord - 18, x + lw + bord + lw * 0.06,
                          y + cap_h / 2 + bord + 18))
            # yellow pills behind runs of key words on this line
            k = 0
            while k < len(ln):
                wi = ln[k]
                if ch[wi]["hi"]:
                    m = k
                    while m + 1 < len(ln) and ch[ln[m + 1]]["hi"] == ch[wi]["hi"]:
                        m += 1
                    px0 = x + sum(widths[q] + space for q in ln[:k])
                    px1 = px0 + sum(widths[q] for q in ln[k:m + 1]) + space * (m - k)
                    pad_x, pad_y = size_px * 0.22, size_px * 0.20
                    pw, ph = px1 - px0 + pad_x * 2, cap_h + pad_y * 2
                    pcx, pcy = (px0 + px1) / 2, y + size_px * 0.01
                    ps = max(ch[wi]["t0"] - 0.07, start)
                    dur_ms = int((end - ps) * 1000)
                    # the pill grows word by word under the key words as they are spoken
                    grow, edge = "", px0
                    for q in range(k, m + 1):
                        edge = px0 + sum(widths[ln[r]] for r in range(k, q + 1)) + space * (q - k)
                        frac = min(100.0, 100 * (edge - px0 + pad_x * 2) / pw)
                        if q == k:
                            first_frac = frac
                        else:
                            dt = int((max(ch[ln[q]]["t0"] - 0.17, ps) - ps) * 1000)
                            grow += f"\\t({dt},{dt + 100},0.6,\\fscx{frac:.1f})"
                    events.append(
                        f"Dialogue: 1,{_t(ps)},{_t(end)},Pill,,0,0,0,,"
                        f"{{\\an4\\pos({px0 - pad_x:.1f},{pcy:.1f})\\frz-1.5\\fscx{first_frac * 0.6:.1f}\\fscy20"
                        f"\\alpha&HFF&\\t(0,120,0.7,\\fscx{first_frac * 1.04:.1f}\\fscy114\\alpha&H00&)"
                        f"\\t(120,210,\\fscx{first_frac:.1f}\\fscy100){grow}"
                        f"\\t({max(dur_ms - 90, 0)},{dur_ms},\\alpha&HFF&)\\p1}}{_round_rect(pw, ph, ph * 0.28)}{{\\p0}}")
                    boxes.append((pcx - pw * 0.56, pcy - ph * 0.58, pcx + pw * 0.56, pcy + ph * 0.58))
                    pills.append(ps)
                    k = m + 1
                else:
                    k += 1
            # the words themselves, each popping in when it is spoken
            for k, wi in enumerate(ln):
                c = ch[wi]
                cx = x + sum(widths[q] + space for q in ln[:k]) + widths[wi] / 2
                ws = max(c["t0"] - 0.05, start)
                dur_ms = int((end - ws) * 1000)
                style, extra = ("Key", "") if c["hi"] else ("Cap", "")
                txt = c["disp"].replace("{", "(").replace("}", ")")
                events.append(
                    f"Dialogue: 2,{_t(ws)},{_t(end)},{style},,0,0,0,,"
                    f"{{\\an5\\move({cx:.1f},{y + 26:.1f},{cx:.1f},{y:.1f},0,150)\\fs{size_px}"
                    f"\\fscx45\\fscy45\\alpha&HFF&\\blur5{extra}"
                    f"\\t(0,110,0.6,\\fscx114\\fscy114\\alpha&H00&\\blur0.6)\\t(110,220,1.4,\\fscx100\\fscy100)"
                    f"\\t({max(dur_ms - 90, 0)},{dur_ms},\\alpha&HFF&\\fscx94\\fscy94)}}{txt}")
    out.write_text(head + "\n".join(events) + "\n", encoding="utf-8")
    return out, boxes, pills


# ==================================================================== sound
def _sfx_events(shots: list[dict], pills: list[float]) -> list[tuple[str, float, float]]:
    ev: list[tuple[str, float, float]] = []
    for n, s in enumerate(shots):
        b = s["beat"]
        at = s["start"] if n else 0.0
        for kind in b.get("sfx") or []:
            if kind == "riser":
                ev.append(("riser", max(at - 1.3, 0.0), 0.9))
            elif kind == "tick" and b.get("shot") in ("number", "compare") and s.get("sfx_times"):
                ev.extend(s["sfx_times"])
            elif kind == "tick" and b.get("shot") in ("number", "compare"):
                for m in range(14):
                    ev.append(("tick", at + 0.15 + m * 0.07, 0.7))
                ev.append(("ding", at + 1.2, 0.55))
            elif kind in ("whoosh", "swish"):
                ev.append((kind, max(at - 0.2, 0), 1.0))
            else:
                ev.append((kind, at, 1.0))
        if b.get("shot") == "card" and not b.get("sfx"):
            ev.append(("tick", at + 0.05, 0.8))
        if b.get("shot") in ("number", "compare", "text") and "pop" not in (b.get("sfx") or []):
            ev.append(("pop", at + 0.1, 0.7))
    for p in pills:
        ev.append(("pop", p + 0.02, 0.35))
    return ev


def _impact(rnd) -> np.ndarray:
    from .motion import _band, _env
    n = int(SR * 1.3)
    t = np.arange(n) / SR
    f = 70 * np.exp(-t * 5) + 34
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.32)
    crack = _band(rnd.normal(0, 1, n), 900, 7000) * _env(n, 0.0008, 0.05) * 0.7
    body = _band(rnd.normal(0, 1, n), 80, 900) * _env(n, 0.002, 0.18) * 0.6
    return sub + crack + body


def _glitch(rnd) -> np.ndarray:
    from .motion import _band
    n = int(SR * 0.32)
    s = np.zeros(n)
    i = 0
    while i < n:
        m = int(SR * rnd.uniform(0.012, 0.04))
        tone = np.sign(np.sin(2 * np.pi * rnd.uniform(200, 1800) * np.arange(m) / SR))
        s[i:i + m] = (tone * 0.5 + _band(rnd.normal(0, 1, m), 1500, 9000)[:m] * 0.5)[: n - i] * (rnd.random() > 0.25)
        i += m + int(SR * rnd.uniform(0, 0.015))
    return s * 0.8


GAIN = {"whoosh": .75, "swish": .6, "pop": .55, "riser": .45, "impact": .95, "ding": .35, "tick": .22,
        "glitch": .45, "shimmer": .4, "thud": .8}


# Sound files (lab): assets/sfx/<kind>/*.mp3|wav, taken from the ElevenLabs Sound Effects library.
# When a kind has files, they are used instead of the synthesized sound; variants rotate so the
# same file is never heard twice in a row. No files for a kind = the old synthesized sound.
SFX_DIR = ROOT / "assets" / "sfx"
SFX_MAX_SEC = {"tick": 0.16, "ding": 1.6, "impact": 2.2, "thud": 2.0, "shimmer": 2.4, "riser": 2.6}
_SFX_FILES: dict[str, np.ndarray] = {}


def _sfx_variants(kind: str) -> list[Path]:
    d = SFX_DIR / kind
    if not d.is_dir():
        return []
    return sorted(f for f in d.iterdir() if f.suffix.lower() in (".mp3", ".wav", ".ogg", ".opus", ".flac"))


def _load_sfx_file(path: Path, kind: str) -> np.ndarray | None:
    key = str(path)
    if key not in _SFX_FILES:
        try:
            raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR),
                                  "-f", "s16le", "-"], capture_output=True, check=True).stdout
        except Exception as e:  # a broken file must never stop a render
            log(f"sfx file skipped ({path.name}): {e}")
            return None
        a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
        nz = np.flatnonzero(np.abs(a) > 0.01)        # trim silence at the start
        a = a[nz[0]:] if len(nz) else a
        if kind == "riser":                          # end on the loudest point (the cut)
            blk = max(1, int(SR * 0.02))
            env = np.abs(a[: len(a) // blk * blk]).reshape(-1, blk).max(1) if len(a) >= blk else np.abs(a)
            a = a[: (int(env.argmax()) + 1) * blk]
            a = a[-int(SR * SFX_MAX_SEC["riser"]):]
        else:
            a = a[: int(SR * SFX_MAX_SEC.get(kind, 2.5))]
        fade = min(len(a), int(SR * 0.03))
        if fade:
            a[-fade:] *= np.linspace(1, 0, fade)
        _SFX_FILES[key] = a
    return _SFX_FILES[key]


def _write_sfx(events, total: float, out: Path, voice: Path, volume: float) -> Path:
    from .motion import _speech_rms, make_sfx
    track = np.zeros(int(SR * (total + 2)), np.float32)
    seen: dict[str, int] = {}
    last_tick = -9.0
    for n, (kind, at, gain) in enumerate(events):
        rnd = np.random.default_rng(n)
        s = None
        files = _sfx_variants(kind)
        if files:
            if kind == "tick":                       # one file per run of counter ticks
                if at - last_tick > 0.3:
                    seen[kind] = seen.get(kind, -1) + 1
                last_tick = at
                k = seen[kind]
            else:
                k = seen[kind] = seen.get(kind, -1) + 1
            s = _load_sfx_file(files[k % len(files)], kind)
            if s is not None and kind == "riser":    # riser events start 1.3 s before the cut
                at = at + 1.3 - len(s) / SR
        if s is None:
            try:
                s = _impact(rnd) if kind == "impact" else _glitch(rnd) if kind == "glitch" else make_sfx(kind, n % 7)
            except ValueError:
                continue
        s = s.astype(np.float32)
        s = s / (np.abs(s).max() + 1e-9) * GAIN.get(kind, .5) * gain
        i = int(at * SR)
        if i < 0:
            s, i = s[-i:], 0
        if 0 <= i < len(track):
            j = min(len(track), i + len(s))
            track[i:j] += s[:j - i]
    ref = _speech_rms(voice)
    if ref:
        blk = track[: len(track) // 2400 * 2400].reshape(-1, 2400)
        rms = np.sqrt((blk ** 2).mean(1))
        loud = np.percentile(rms[rms > 1e-4], 95) if (rms > 1e-4).any() else 0
        if loud > 0:
            track *= (ref * 0.6 * volume) / loud
    peak = np.abs(track).max()
    if peak > 0.95:
        track *= 0.95 / peak
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((np.clip(track[: int(SR * total)], -1, 1) * 32767).astype(np.int16).tobytes())
    return out


def _pick_music(data: dict) -> Path | None:
    music = {m.name: m for m in MUSIC_DIR.glob("*.mp3")}
    if not music:
        return None
    if data.get("music") in music:
        return music[data["music"]]
    names = [n for n in MOOD_TRACKS.get(data.get("music_mood", ""), []) if n in music] or sorted(music)
    return music[random.Random(data["title"]).choice(names)]


def _mean_db(path: Path, seconds: float = 90) -> float | None:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-t", str(seconds), "-i", str(path), "-af", "volumedetect",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", out)
    return float(m.group(1)) if m else None


def _mix_audio(voice: Path, sfx: Path, track: Path | None, total: float, vol: float, work: Path, tag: str,
               curve: list | None = None) -> Path:
    """Voice + effects + ducked music, then two-pass loudness normalisation to -14 LUFS."""
    from .motion import _speech_rms
    raw = work / f"pro_mix_raw_{tag}.wav"
    inputs = ["-i", voice.name, "-i", sfx.name]
    if track and vol > 0:
        ref = _speech_rms(voice)
        mdb = _mean_db(track)
        gain = 0.1
        if ref and mdb is not None:
            target = 20 * math.log10(ref) - 18 + 20 * math.log10(max(vol, 1e-4) / 0.06)
            gain = min(10 ** ((target - mdb) / 20), 1.0)
        off = random.Random(track.name + str(total)).uniform(0, 12)
        inputs += ["-stream_loop", "-1", "-ss", f"{off:.2f}", "-i", str(track)]
        # the music follows the feeling of each part: softer when sad or whispered, louder when
        # it gets loud. Each change glides over 0.6 s so it is never a jump.
        expr = "1"
        for a, b, g in curve or []:
            if abs(g - 1) > 1e-3:
                ramp = f"min(max((t-{a - 0.3:.3f})/0.6,0),1)*min(max(({b + 0.3:.3f}-t)/0.6,0),1)"
                expr += f"*(1+{g - 1:.3f}*{ramp})"
        mood = f"volume='{expr}':eval=frame," if expr != "1" else ""
        fc = (f"[0:a]aformat=sample_rates={SR}:channel_layouts=mono,asplit=2[vo][key];"
              f"[2:a]aformat=sample_rates={SR}:channel_layouts=stereo,atrim=0:{total:.3f},asetpts=PTS-STARTPTS,{mood}volume={gain:.4f},"
              f"afade=t=in:st=0:d=0.4,afade=t=out:st={max(total - 1.8, 0):.3f}:d=1.8[m0];"
              f"[key]aformat=channel_layouts=stereo[k2];"
              f"[m0][k2]sidechaincompress=threshold=0.02:ratio=7:attack=20:release=320:makeup=1,"
              f"asplit=2[m][mstem];"
              f"[vo]aformat=channel_layouts=stereo[v2];[1:a]aformat=channel_layouts=stereo[s2];"
              f"[v2][s2][m]amix=inputs=3:duration=first:dropout_transition=0:normalize=0[a]")
    else:
        fc = "[0:a][1:a]amix=inputs=2:duration=first:normalize=0,aformat=channel_layouts=stereo[a]"
    extra = (["-map", "[mstem]", "-t", f"{total:.3f}", "-ar", str(SR), "-c:a", "pcm_s16le",
              f"pro_music_{tag}.wav"] if "[mstem]" in fc else [])
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc, "-map", "[a]",
         "-t", f"{total:.3f}", "-ar", str(SR), "-c:a", "pcm_s16le", raw.name, *extra], cwd=work)
    # pass 1: measure
    res = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(raw), "-af",
                          "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", res, re.S)
    out = work / f"pro_mix_{tag}.wav"
    afade = f"afade=t=in:st=0:d=0.03,afade=t=out:st={max(total - 0.06, 0):.3f}:d=0.06"
    if m:
        j = json.loads(m.group(0))
        ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
              f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:"
              f"linear=true")
    else:
        ln = "loudnorm=I=-14:TP=-1.5:LRA=11"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw.name, "-af",
         f"{ln},aresample={SR},alimiter=limit=0.75:attack=2:release=60:level=false,{afade}", "-ar", str(SR),
         "-c:a", "pcm_s16le", out.name], cwd=work)
    return out


# ============================================================ source files
def _slug(t: str, n: int = 28) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(t).lower()).strip("-")[:n] or "shot"


def _tc(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:06.3f}"


def _srt(words: list[dict], out: Path) -> None:
    """Plain subtitles, 2-4 words per line, for editors that don't read .ass."""
    lines, cur = [], []
    for wd in words:
        cur.append(wd)
        if len(cur) >= 4 or wd["tok"][-1:] in ".,!?;:" or (len(cur) >= 2 and wd["t1"] - cur[0]["t0"] > 1.2):
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    def ts(t):
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    out.write_text("\n".join(f"{k + 1}\n{ts(l[0]['t0'])} --> {ts(l[-1]['t1'])}\n"
                             f"{' '.join(x['tok'] for x in l)}\n" for k, l in enumerate(lines)), encoding="utf-8")


def export_sources(out_file: Path, data: dict, shots: list[dict], segs: list[Path], pictures: Path,
                   voice: Path, sfx: Path, mix: Path, ass: Path, words: list[dict], track: Path | None,
                   size: tuple[int, int], fps: int, total: float, work: Path, tag: str) -> Path:
    """Everything an editor needs to rebuild or change the Short, at full quality:
    the video without captions, every shot, the original stock footage (only the part used),
    the graphics and captions as transparent overlays, and voice / effects / music as
    separate tracks, with a readme of the timeline."""
    w, h = size
    root = out_file.with_name(out_file.stem + "-sources")
    if root.exists():
        shutil.rmtree(root)
    for d in ("audio", "shots", "stock-original", "overlays", "captions"):
        (root / d).mkdir(parents=True, exist_ok=True)
    hi = ["-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p"]

    shutil.copy(out_file, root / "01_final_with_captions.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(pictures), "-i", str(mix), "-map", "0:v", "-map", "1:a",
         "-t", f"{total:.3f}", *hi, "-r", str(fps), "-c:a", "aac", "-b:a", "256k",
         str(root / "02_video_no_captions.mp4")])

    # audio stems (voice, effects and ducked music add up to the mix before loudness levelling)
    shutil.copy(voice, root / "audio" / "voice.wav")
    shutil.copy(sfx, root / "audio" / "sound_effects.wav")
    stem = work / f"pro_music_{tag}.wav"
    if stem.exists():
        shutil.copy(stem, root / "audio" / "music_ducked.wav")
    shutil.copy(mix, root / "audio" / "final_mix_-14LUFS.wav")

    # captions: animated transparent overlay + the .ass and .srt files and the font
    shutil.copy(ass, root / "captions" / "captions_animated.ass")
    _srt(words, root / "captions" / "captions_plain.srt")
    if FONT.exists():
        shutil.copy(FONT, root / "captions" / "Montserrat-ExtraBold.ttf")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=black@0.0:s={w}x{h}:r={fps}:d={total:.3f},format=rgba",
         "-vf", f"ass={ass.name}:fontsdir={FONT_DIR.resolve()}:alpha=1", "-c:v", "png", "-pix_fmt", "rgba",
         str((root / "overlays" / "captions_transparent.mov").resolve())], cwd=work)

    rows = []
    for n, (sh, seg) in enumerate(zip(shots, segs)):
        b = sh["beat"]
        kind = b.get("shot", "clip")
        name = f"{n + 1:02d}_{kind}_{_slug(b.get('text') or b.get('query') or kind)}"
        shutil.copy(seg, root / "shots" / f"{name}.mp4")
        src = sh.get("src") or {}
        orig = ""
        if src.get("kind") == "vid":
            st = max(float(src.get("start", 0.0)) - 1.0, 0.0)
            dst = root / "stock-original" / f"{name}{Path(src['src']).suffix}"
            run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{st:.2f}", "-i", str(src["src"]),
                 "-t", f"{sh['len'] + 3.0:.2f}", "-map", "0:v:0", "-c", "copy", "-an", str(dst)])
            orig = dst.name
        elif src.get("kind") == "img":
            dst = root / "stock-original" / f"{name}.jpg"
            shutil.copy(src["src"], dst)
            orig = dst.name
        gfx = ""
        if sh.get("gfx"):
            gdir, oy = sh["gfx"]
            gname = f"{name}_graphic.mov"
            run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(gdir / "%04d.png"),
                 "-vf", f"pad={w}:{h}:0:{oy}:color=black@0.0,format=rgba", "-c:v", "png",
                 str(root / "overlays" / gname)])
            gfx = gname
        rows.append((n + 1, sh["b"], sh["len"], sh["tr"], kind, b.get("camera", ""), ", ".join(b.get("sfx") or []),
                     b.get("query", ""), f"shots/{name}.mp4", f"stock-original/{orig}" if orig else "-",
                     f"overlays/{gfx}" if gfx else "-"))

    music_line = (f"{track.name} by Kevin MacLeod (incompetech.com), licensed under Creative Commons: "
                  f"By Attribution 4.0. Keep this credit in the description." if track else "none")
    lines = [
        f"{data.get('title', '')}: source files for editing",
        "",
        f"Length {total:.2f} s, {w}x{h}, {fps} fps. Voice: {data.get('_voice', '')}".rstrip(),
        "",
        "Files",
        "- 01_final_with_captions.mp4: the finished Short.",
        "- 02_video_no_captions.mp4: the same picture and sound with no captions burned in.",
        "- shots/: every shot as rendered (camera move, colour grade, graphic), in timeline order.",
        "- stock-original/: the original stock footage at full resolution, only the part used plus about 1 s"
        " either side. Photos are whole.",
        "- overlays/captions_transparent.mov: the animated captions on a transparent background (PNG codec,"
        " put it on the top track).",
        "- overlays/*_graphic.mov: number, chart and title graphics on a transparent background, full frame.",
        "- captions/: captions_animated.ass (exact animation, needs the Montserrat font beside it),"
        " captions_plain.srt (plain subtitles) and the font.",
        "- audio/voice.wav, sound_effects.wav, music_ducked.wav: separate tracks, already lined up from 0:00."
        " Together they make the mix before loudness levelling.",
        "- audio/final_mix_-14LUFS.wav: the finished mix (YouTube loudness, -14 LUFS, peak -1.5 dB).",
        "",
        "Timeline (start, length and the transition into each shot)",
        "no | start | length | transition | kind | camera | sound | stock search | files",
    ]
    for r in rows:
        lines.append(f"{r[0]:02d} | {_tc(r[1])} | {r[2]:.2f}s | {r[3]} | {r[4]} | {r[5]} | {r[6] or '-'} | "
                     f"{r[7]} | {r[8]}; {r[9]}; {r[10]}")
    lines += ["", "Transitions overlap the next shot by their length (whip 0.22 s, zoom 0.30 s,"
              " slide 0.26 s, flash and glitch short). A plain cut has none.",
              "", f"Music: {music_line}",
              "Stock footage: Pixabay and Pexels content licences (free to use and edit, no credit needed)."]
    (root / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "timeline.json").write_text(json.dumps([
        {"no": r[0], "start": round(r[1], 3), "length": round(r[2], 3), "transition": r[3], "kind": r[4],
         "camera": r[5], "sfx": r[6], "query": r[7], "shot": r[8], "original": r[9], "overlay": r[10]}
        for r in rows], indent=1), encoding="utf-8")
    log(f"Source files for editing in {root.name}/")
    return root
