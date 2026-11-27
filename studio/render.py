"""Turn a script into an MP4 with ffmpeg.

Per scene: voice (TTS) + picture with a slow zoom. Then all scenes are
joined, subtitles burned in, optional background music mixed under the
voice, and the whole video fades in from black and fades out at the end.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

from . import tts, visuals
from .common import MUSIC_DIR, ROOT, font_family_for, log, media_duration, run

ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
AUD = ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]


def _ass_time(t: float) -> str:
    t = max(t, 0)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


# ------------------------------------------------------------- highlights
JOIN = "\u2060"   # invisible "word joiner": keeps a highlighted phrase on one line
_NUM_WORDS = ("zero one two three four five six seven eight nine ten eleven twelve "
              "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty "
              "thirty forty fifty sixty seventy eighty ninety hundred thousand "
              "million billion trillion half").split()
_AUTO = re.compile(
    r"\b(?:\d[\d,.]*|(?:" + "|".join(_NUM_WORDS) + r"))"
    r"(?:[\s-]+(?:and\s+)?(?:\d[\d,.]*|(?:" + "|".join(_NUM_WORDS) + r")))*"
    r"(?:\s+[A-Za-z]+)?\b", re.IGNORECASE)


def scene_highlights(scene: dict, text: str) -> list[str]:
    """Phrases to show on a yellow box: the scene's "highlight" list if given,
    otherwise numbers (with the word after them, like "three hearts")."""
    given = scene.get("highlight")
    if isinstance(given, str):
        given = [given]
    if given:
        return [g.strip() for g in given if str(g).strip()]
    found = []
    for m in _AUTO.finditer(text):
        words = m.group(0).split()
        stop = {"and", "a", "an", "the", "of", "to", "too", "but", "or", "is", "are",
                "was", "were", "in", "on", "at", "it", "that", "so", "for", "by", "with"}
        while words and words[-1].lower() in stop:
            words = words[:-1]
        if len(words) == 1 and words[0].lower() in _NUM_WORDS:
            continue    # a lone "one" or "two" is rarely the point
        if words and len(words) <= 5:
            found.append(" ".join(words))
    return found


def protect(text: str, phrases: list[str]) -> str:
    """Glue the words of each phrase together so a caption line never splits it."""
    for ph in sorted(phrases, key=len, reverse=True):
        pat = re.compile(r"(?<!\w)" + r"\s+".join(map(re.escape, ph.split())) + r"(?!\w)",
                         re.IGNORECASE)
        text = pat.sub(lambda m: JOIN.join(m.group(0).split()), text)
    return text


def write_ass(cues: list[tuple[float, float, str]], size: tuple[int, int],
              sample_text: str, out: Path, font: str | None = None, scale: float = 1.0) -> Path:
    w, h = size
    portrait = h > w
    font = font or font_family_for(sample_text)
    fs = int(h * (0.055 if not portrait else 0.034) * scale)
    margin_v = int(h * (0.07 if not portrait else 0.22))
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{fs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,1,{max(2, fs // 14)},1,2,{int(w * .06)},{int(w * .06)},{margin_v},1
Style: Hi,{font},{fs},&H00141414,&H00141414,&H0000D6FF,&H0000D6FF,1,0,0,0,100,100,0,0,3,{max(4, fs // 10)},0,2,{int(w * .06)},{int(w * .06)},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    hide, show = r"{\1a&HFF&\3a&HFF&}", r"{\1a&H00&\3a&H00&}"
    for start, end, text in cues:
        safe = text.replace("{", "(").replace("}", ")").replace("\n", " ")
        t0, t1 = _ass_time(start), _ass_time(end)
        pop = r"{\fscx82\fscy82\t(0,130,\fscx100\fscy100)}"    # each line pops in
        lines.append(f"Dialogue: 0,{t0},{t1},Default,,0,0,0,,{pop}{safe.replace(JOIN, chr(92) + 'h')}")
        # yellow boxes: same text on a top layer, only the glued phrases visible
        parts = re.split(r"(\S*" + JOIN + r"\S*)", safe)
        if len(parts) > 1:
            hi = pop + hide
            for k, part in enumerate(parts):
                if k % 2:
                    word = part.strip(".,!?;:")
                    lead, trail = part[:part.find(word)], part[part.find(word) + len(word):]
                    hi += lead + show + word.replace(JOIN, chr(92) + "h") + hide + trail
                else:
                    hi += part
            lines.append(f"Dialogue: 1,{t0},{t1},Hi,,0,0,0,,{hi}")
    out.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return out


def render(data: dict, cfg: dict, work: Path, out_file: Path,
           size: tuple[int, int], max_seconds: float | None = None) -> dict:
    """Render one video. Returns info incl. duration and first image path."""
    vcfg = cfg["video"]
    fps = int(vcfg.get("fps", 30))
    pause = float(vcfg.get("scene_pause", 0.35))
    work.mkdir(parents=True, exist_ok=True)
    w, h = size
    tag = f"{w}x{h}"

    all_cues: list[tuple[float, float, str]] = []
    t0 = 0.0
    first_img: Path | None = None

    style = str(data.get("style", "")).lower()
    if style == "pro" or (vcfg.get("pro_shorts") and h > w and style not in ("map", "explainer")):
        from . import pro            # professional Shorts: beats, clips, word captions, sound design
        return pro.render(data, cfg, work, out_file, size, max_seconds)
    map_style = style == "map"
    explainer = style == "explainer"
    speech: list[tuple[float, float]] = []
    timings: list[tuple[float, float]] = []
    voice_parts: list[Path] = []
    segments: list[dict] = []     # picture pieces for the photo/clip style
    visuals.reset_clips()         # no clip twice in one video

    for i, scene in enumerate(data["scenes"]):
        text = str(scene.get("text", "")).strip()
        audio = work / f"scene{i:02d}.mp3"
        if not text:                                 # a silent shot (explainer style)
            dur, cues = float(scene.get("hold", 1.0)), []
            if not audio.exists():
                run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                     "-t", f"{dur:.3f}", str(audio)])
                (work / f"scene{i:02d}.cues").write_text("[]", encoding="utf-8")
        elif not audio.exists():                     # 16:9 and 9:16 share voice
            dur, cues = tts.speak(text, audio, cfg)
            (work / f"scene{i:02d}.cues").write_text(json.dumps(cues, ensure_ascii=False), encoding="utf-8")
        else:
            dur = media_duration(audio)
            cues = [tuple(c) for c in json.loads((work / f"scene{i:02d}.cues").read_text(encoding="utf-8"))]
        scene_len = dur + (float(scene.get("pause", pause)) if text else 0.0)
        if max_seconds and t0 + scene_len > max_seconds:
            log(f"Stopping at scene {i} to stay under {max_seconds}s")
            break

        part = work / f"voice{i:02d}.wav"
        if not part.exists():
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio), "-af",
                 f"apad=whole_dur={scene_len:.3f}", "-t", f"{scene_len:.3f}",
                 "-ar", "48000", "-ac", "1", str(part)])
        voice_parts.append(part)
        timings.append((t0, t0 + scene_len))
        speech.append((cues[0][0], cues[-1][1]) if cues else (0.0, 0.0))

        if not map_style and not explainer:
            segments += _scene_segments(scene, i, data["title"], cfg, size, scene_len, work, tag)
            if first_img is None:
                first_img = next((sg["thumb"] for sg in segments if sg.get("thumb")), None)

        if vcfg.get("highlight", True):
            phrases = scene_highlights(scene, text)
            cues = [(cs, ce, protect(ct, phrases)) for cs, ce, ct in cues]
        for s_, e_, c_ in tts.split_cues(cues, int(data.get("caption_chars", vcfg.get("subtitle_max_chars", 42)))):
            all_cues.append((t0 + s_, t0 + min(e_, dur), c_))
        t0 += scene_len

    if not voice_parts:
        raise RuntimeError("No scenes fit into the video")
    if map_style:
        joined, first_img = _map_joined(data, voice_parts, timings, t0, size, fps, vcfg, work, tag)
    elif explainer:
        joined, first_img = _explainer_joined(data, voice_parts, timings, speech, t0, size, fps, vcfg, work, tag)
    else:
        joined = _photo_joined(segments, voice_parts, t0, size, fps, vcfg, work, tag)
    total = media_duration(joined)

    # Final pass: subtitles + music + fades
    fade = float(vcfg.get("fade_seconds", 0.8))
    vf = []
    if vcfg.get("subtitles", True) and all_cues:
        if explainer:
            ass = write_ass(all_cues, size, data["title"], work / f"subs_{tag}.ass", "Inter", 0.82)
            vf.append(f"ass={ass.name}:fontsdir={(ROOT / 'assets' / 'fonts').resolve()}")
        else:
            ass = write_ass(all_cues, size, data["title"], work / f"subs_{tag}.ass")
            vf.append(f"ass={ass.name}")
    vf.append(f"fade=t=in:st=0:d={fade}")
    vf.append(f"fade=t=out:st={max(total - fade, 0):.3f}:d={fade}")

    inputs = ["-i", joined.name]
    music = sorted(MUSIC_DIR.glob("*.mp3"))
    vol = float(vcfg.get("map_music_volume" if map_style else "music_volume",
                         vcfg.get("music_volume", 0.1)))
    if "music_volume" in data:
        vol = float(data["music_volume"])
    track = None
    afade = f"afade=t=in:st=0:d={fade},afade=t=out:st={max(total - fade, 0):.3f}:d={fade}"
    if music and vol > 0:
        named = [m for m in music if m.name == data.get("music")]
        track = named[0] if named else random.Random(data["title"]).choice(music)
        vol = _music_gain(track, work, vol)
        inputs += ["-stream_loop", "-1", "-i", str(track)]
        # music dips further whenever someone speaks (sidechain ducking)
        fc = (f"[0:v]{','.join(vf)}[v];[0:a]asplit=2[sp][key];[1:a]volume={vol}[m0];"
              f"[m0][key]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=350[m];"
              f"[sp][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,{afade}[a]")
    else:
        fc = f"[0:v]{','.join(vf)}[v];[0:a]{afade}[a]"

    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc,
         "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}", *ENC, *AUD,
         "-r", str(fps), "-movflags", "+faststart", str(out_file.resolve())], cwd=work)
    log(f"Rendered {out_file.name} ({total:.1f}s, {tag})")
    chapters = [(timings[i][0], str(sc["chapter"])) for i, sc in enumerate(data["scenes"][:len(timings)])
                if sc.get("chapter")]
    return {"duration": total, "first_image": first_img, "music": track.name if track else None,
            "chapters": chapters}


def _music_gain(track: Path, work: Path, vol: float) -> float:
    """Set the music by measurement: about 20 dB under the voice (at volume 0.06),
    whatever the song's own loudness is."""
    import math
    import subprocess
    from .motion import _speech_rms
    voices = sorted(work.glob("voice_all_*.wav"))
    ref = _speech_rms(voices[-1]) if voices else None
    if not ref:
        return vol
    out = subprocess.run(["ffmpeg", "-hide_banner", "-t", "90", "-i", str(track), "-af", "volumedetect",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", out)
    if not m:
        return vol
    voice_db = 20 * math.log10(ref)
    target = voice_db - 20 + 20 * math.log10(max(vol, 1e-4) / 0.06)
    gain = 10 ** ((target - float(m.group(1))) / 20)
    log(f"Music {track.name}: set {target - voice_db:+.0f} dB under the voice")
    return min(gain, 1.0)


def _voice_track(voice_parts: list[Path], work: Path) -> Path:
    lst = work / "voice_list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in voice_parts), encoding="utf-8")
    voice = work / f"voice_all_{len(voice_parts)}.wav"
    if not voice.exists():
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", lst.name, "-c", "copy", voice.name], cwd=work)
    return voice


TRANSITIONS = ["slideleft", "zoomin", "smoothleft", "circleopen", "slideup", "fadeblack"]


def _scene_segments(scene: dict, i: int, title: str, cfg: dict, size: tuple[int, int],
                    scene_len: float, work: Path, tag: str) -> list[dict]:
    """One or two picture pieces for a scene: stock video clips if possible, else photos."""
    import hashlib
    vcfg = cfg["video"]
    use_clips = vcfg.get("clips", True) and vcfg.get("visuals", "auto") == "auto"
    pieces = 2 if use_clips and scene_len > float(vcfg.get("cut_after_seconds", 5.5)) else 1
    seed = int(hashlib.md5(f"{title}-{i}".encode()).hexdigest()[:8], 16)
    query = str(scene.get("visual", ""))
    subj = " ".join(visuals.subject_words(query, scene.get("subject"))) or query
    overlay = None
    out, img = [], None
    for k in range(pieces):
        length = scene_len / pieces
        clip = visuals.pixabay_video(query, seed + k, work / f"vid{i:02d}_{k}.mp4",
                                     scene.get("subject")) if use_clips else None
        if clip is not None:
            if overlay is None:
                overlay = visuals.headline_overlay(str(scene.get("on_screen") or ""), size,
                                                   work / f"head{i:02d}_{tag}.png") or False
            thumb = work / f"vid{i:02d}_{k}_{tag}.jpg"
            if not thumb.exists():
                run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", str(clip), "-frames:v", "1",
                     "-vf", f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=increase,"
                            f"crop={size[0]}:{size[1]}", str(thumb)])
                if thumb.exists():
                    import shutil
                    shutil.copy(thumb, thumb.with_name(thumb.stem + "_bg.jpg"))
            out.append({"kind": "vid", "src": clip, "overlay": overlay or None, "len": length,
                        "scene": i, "subject": subj, "thumb": thumb if thumb.exists() else None})
        else:
            if img is None:
                img = visuals.scene_image(scene, i, title, cfg, size, work / f"img{i:02d}_{tag}.jpg")
            out.append({"kind": "img", "src": img, "len": length, "scene": i, "zoom_in": (i + k) % 2 == 0,
                        "subject": subj, "thumb": img})
    return out


def _photo_joined(segments: list[dict], voice_parts: list[Path], total: float,
                  size: tuple[int, int], fps: int, vcfg: dict, work: Path, tag: str) -> Path:
    """Picture pieces joined with transitions, plus voice and whoosh sounds."""
    from . import motion
    w, h = size
    d = float(vcfg.get("transition_seconds", 0.35)) if vcfg.get("transitions", True) else 0.0
    files = []
    for n, sg in enumerate(segments):
        length = sg["len"] + (d if n < len(segments) - 1 else 0)
        f = work / f"seg{n:02d}_{tag}.mp4"
        if sg["kind"] == "img":
            frames = max(int(length * fps), 1)
            zoom = f"1+0.08*on/{frames}" if sg["zoom_in"] else f"1.08-0.08*on/{frames}"
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(sg["src"]), "-filter_complex",
                 f"[0:v]zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                 f":d={frames}:s={w}x{h}:fps={fps},setsar=1,format=yuv420p[v]",
                 "-map", "[v]", "-t", f"{length:.3f}", *ENC, str(f)])
        else:
            chain = (f"[0:v]scale={int(w * 1.06)}:{int(h * 1.06)}:force_original_aspect_ratio=increase,"
                     f"crop={w}:{h},fps={fps},setsar=1")
            start = visuals.CLIP_START.get(str(sg["src"]), 0.0)
            inputs = ["-stream_loop", "-1", *(["-ss", f"{start:.2f}"] if start else []), "-i", str(sg["src"])]
            if sg.get("overlay"):
                inputs += ["-i", str(sg["overlay"])]
                chain += "[b];[b][1:v]overlay=0:0"
            run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex",
                 chain + ",format=yuv420p[v]", "-map", "[v]", "-an", "-t", f"{length:.3f}",
                 *ENC, str(f)])
        files.append(f)

    pic = work / f"pictures_{tag}.mp4"
    events: list[tuple[str, float, float]] = []
    if d > 0 and len(files) > 1:
        args, fc, last, offset = [], [], "0:v", 0.0
        for n, f in enumerate(files):
            args += ["-i", str(f)]
        for n in range(1, len(files)):
            offset += segments[n - 1]["len"]
            new_scene = segments[n]["scene"] != segments[n - 1]["scene"]
            kind = TRANSITIONS[segments[n]["scene"] % len(TRANSITIONS)] if new_scene else "fade"
            fc.append(f"[{last}][{n}:v]xfade=transition={kind}:duration={d}:offset={offset:.3f}[x{n}]")
            last = f"x{n}"
            if new_scene:   # soft, varied transition sounds, kept well under the voice
                events.append((["swish", "whoosh"][segments[n]["scene"] % 2], offset - 0.1, 0.6))
        run(["ffmpeg", "-y", "-loglevel", "error", *args, "-filter_complex", ";".join(fc),
             "-map", f"[{last}]", *ENC, str(pic)])
    else:
        lst = work / f"segs_{tag}.txt"
        lst.write_text("".join(f"file '{f.name}'\n" for f in files), encoding="utf-8")
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", lst.name, "-c", "copy", pic.name], cwd=work)

    voice = _voice_track(voice_parts, work)
    joined = work / f"joined_{tag}.mp4"
    if events:
        sfx = motion.write_sfx(events, total, work / f"sfx_{tag}.wav",
                               float(vcfg.get("sfx_volume", 0.5)), voice)
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", pic.name, "-i", voice.name, "-i", sfx.name,
             "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=first:normalize=0[a]",
             "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}", "-c:v", "copy", *AUD,
             joined.name], cwd=work)
    else:
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", pic.name, "-i", voice.name,
             "-map", "0:v", "-map", "1:a", "-t", f"{total:.3f}", "-c:v", "copy", *AUD,
             joined.name], cwd=work)
    return joined


def _map_joined(data: dict, voice_parts: list[Path], timings: list[tuple[float, float]],
                total: float, size: tuple[int, int], fps: int, vcfg: dict,
                work: Path, tag: str) -> tuple[Path, Path]:
    """Map-style picture track + voice + sound effects in one file."""
    from . import motion
    voice = _voice_track(voice_parts, work)
    pic, sfx = work / f"motion_{tag}.mp4", work / f"sfx_{tag}.wav"
    motion.render_track(data["scenes"][:len(timings)], timings, total, size, fps, pic, sfx,
                        float(vcfg.get("sfx_volume", 0.5)), voice)
    joined = work / f"joined_{tag}.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", pic.name, "-i", voice.name, "-i", sfx.name,
         "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=first:normalize=0[a]",
         "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}", "-c:v", "copy", *AUD,
         joined.name], cwd=work)
    thumb = work / f"map_first_{tag}.jpg"
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{min(2.5, total / 2):.2f}", "-i", str(pic),
         "-frames:v", "1", str(thumb)])
    return joined, thumb


def _explainer_joined(data: dict, voice_parts: list[Path], timings: list[tuple[float, float]],
                      speech: list[tuple[float, float]], total: float, size: tuple[int, int], fps: int,
                      vcfg: dict, work: Path, tag: str) -> tuple[Path, Path]:
    """Animated explainer picture track + voice + sound effects in one file."""
    from . import explainer
    voice = _voice_track(voice_parts, work)
    pic, sfx = work / f"explainer_{tag}.mp4", work / f"sfx_{tag}.wav"
    explainer.render_track(data["scenes"][:len(timings)], timings, speech, total, size, fps, pic, sfx,
                           float(data.get("sfx_volume", vcfg.get("sfx_volume", 0.3))), voice)
    joined = work / f"joined_{tag}.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", pic.name, "-i", voice.name, "-i", sfx.name,
         "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=first:normalize=0[a]",
         "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}", "-c:v", "copy", *AUD,
         joined.name], cwd=work)
    thumb = work / f"explainer_thumb_{tag}.jpg"
    if data.get("thumbnail_spec"):
        explainer.thumbnail(data["thumbnail_spec"], (1280, 720), thumb)
    else:
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{min(3.0, total / 2):.2f}", "-i", str(pic),
             "-frames:v", "1", str(thumb)])
    return joined, thumb
