"""Automatic director for the "pro" Shorts style.

A script written with the MindBlip director skill (skills/mindblip-director)
already has a "beats" list in every scene: what fills the screen, the camera
move, the transition and the sounds. For scripts without beats (the older
queue), this module plans them by itself from each scene's text, visual,
on_screen and highlight fields, following the same rules as the skill.
"""
from __future__ import annotations

import copy
import hashlib
import re

SHOTS = {"clip", "photo", "number", "compare", "text"}
CAMERAS = ["push_in", "pan_left", "pull_out", "pan_right", "tilt_up", "drift", "tilt_down"]
SCENE_TRANSITIONS = ["whip_left", "slide_up", "zoom", "whip_right", "cut", "slide_up", "whip_left", "zoom"]
TRANSITION_SFX = {"whip_left": "swish", "whip_right": "swish", "slide_up": "whoosh",
                  "zoom": "whoosh", "glitch": "glitch", "flash": "impact"}
REVEAL = re.compile(r"\b(weirder|strangest|stranger|twist|turns out|but here|exactly why|that's why|"
                    r"which is why|the craziest|wildest|even more|it gets)\b", re.I)
WRONG = re.compile(r"\b(stops?|impossible|backwards|upside down|wrong|broken|dies|dead|vanish\w*)\b", re.I)
SPLIT_AT = {"and", "but", "so", "which", "that", "then", "while", "because", "when"}

MOOD_WORDS = {
    "mysterious": "space planet venus mars moon sun star galaxy ocean deep sea octopus whale shark squid "
                  "heart brain blood body cell dna ghost dark secret mystery cave",
    "quirky": "duck cat dog penguin cow goat sloth frog monkey panda banana funny sneeze hiccup",
    "upbeat": "fastest record speed fastest strongest biggest olympic run racing",
    "epic": "volcano earthquake ancient empire pyramid dinosaur giant storm hurricane",
    "calm": "sleep flower forest tree rain calm",
}


def _seed(*parts) -> int:
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def music_mood(data: dict) -> str:
    if data.get("music_mood"):
        return str(data["music_mood"]).lower()
    words = re.findall(r"[a-z]+", (data.get("title", "") + " " +
                                   " ".join(str(s.get("text", "")) for s in data.get("scenes", []))).lower())
    # with no clear mood words, spread the videos over the lighter moods instead of
    # sending most of them to "mysterious"
    best, score = ["quirky", "upbeat", "mysterious", "calm"][_seed(data.get("title", "")) % 4], 0
    for mood, vocab in MOOD_WORDS.items():
        v = set(vocab.split())
        n = sum(1 for w in words if w in v or w.rstrip("s") in v)
        if n > score:
            best, score = mood, n
    return best


_NUM = re.compile(r"(?P<pre>[$£€]?)(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<suf>%|[A-Za-z]+(?:\s[A-Za-z]+)?)?")


def number_from(on_screen: str) -> dict | None:
    """'1 spin = 243 days' -> {to: 243, suffix: ' DAYS', label: '1 SPIN'}."""
    s = (on_screen or "").strip()
    if not s:
        return None
    label, _, value = s.partition("=") if "=" in s else s.partition(":") if ":" in s else ("", "", s)
    m = _NUM.search(value)
    if not m:
        return None
    num = float(m.group("num").replace(",", ""))
    if num < 2 or (num < 10 and not label.strip()):
        return None                       # "1 for the body", "2 adults": not worth a counter
    before = value[:m.start()].strip(" -")
    suf = (m.group("suf") or "").strip()
    label = (label.strip() or before).upper()
    return {"from": 0, "to": num, "prefix": m.group("pre") or "",
            "suffix": (" " + suf.upper()) if suf and suf != "%" else suf,
            "label": label, "decimals": len(m.group("num").split(".")[1]) if "." in m.group("num") else 0}


def _split_point(tokens: list[str]) -> int | None:
    if len(tokens) <= 9:
        return None
    mid = len(tokens) / 2
    cands = [i for i in range(3, len(tokens) - 2)
             if tokens[i - 1][-1:] in ",;:" or tokens[i].lower().strip(",.") in SPLIT_AT]
    if not cands:
        return int(round(mid))
    return min(cands, key=lambda i: abs(i - mid))


def plan(data: dict) -> dict:
    """Return a copy of the script where every scene has a valid "beats" list."""
    data = copy.deepcopy(data)
    data["music_mood"] = music_mood(data)
    scenes = data["scenes"]
    graphics = sum(1 for s in scenes for b in (s.get("beats") or []) if b.get("shot") in ("number", "compare", "text"))
    cam_i = _seed(data.get("title")) % len(CAMERAS)
    tr_i = 0
    nums = [number_from(str(s.get("on_screen") or "")) for s in scenes]
    for i, sc in enumerate(scenes):
        text = str(sc.get("text", "")).strip()
        tokens = text.split()
        if sc.get("beats"):
            sc["beats"] = _clean(sc["beats"], tokens, sc)
            continue
        query = str(sc.get("visual") or sc.get("subject") or data.get("title", ""))
        subject = sc.get("subject")
        first: dict = {"at_word": 0, "shot": "clip", "query": query, "subject": subject}
        # graphics: a counter for a striking number, a comparison for two numbers in a row
        n = nums[i]
        if i > 0 and n and graphics < 3:
            prev = nums[i - 1]
            if prev and prev.get("suffix") and prev["suffix"] == n.get("suffix") and \
                    scenes[i - 1].get("beats", [{}])[0].get("shot") == "number":
                first.update(shot="compare", compare={
                    "left": {"label": prev["label"] or "BEFORE", "value": prev["to"]},
                    "right": {"label": n["label"] or "NOW", "value": n["to"]},
                    "unit": n["suffix"].strip()})
                graphics += 1
            elif graphics < 2:
                first.update(shot="number", number=n)
                graphics += 1
        # camera and transition
        if i == 0:
            first.update(camera="punch", sfx=["impact"])
        else:
            first["camera"] = CAMERAS[cam_i % len(CAMERAS)]
            cam_i += 1
            if REVEAL.search(text):
                first.update(transition="flash", sfx=["riser", "impact"])
            elif WRONG.search(text) and i % 3 == 0:
                first.update(transition="glitch", sfx=["glitch"])
            elif i == len(scenes) - 1:
                first.update(transition="cut")           # the loop: no outro, no fade
            else:
                tr = SCENE_TRANSITIONS[tr_i % len(SCENE_TRANSITIONS)]
                tr_i += 1
                first["transition"] = tr
                if tr in TRANSITION_SFX:
                    first["sfx"] = [TRANSITION_SFX[tr]]
            if first["shot"] in ("number", "compare"):
                first.setdefault("sfx", [])
                first["sfx"] = list(dict.fromkeys(first["sfx"] + ["tick"]))
        beats = [first]
        k = _split_point(tokens)
        if k and first["shot"] in ("clip", "photo"):
            beats.append({"at_word": k, "shot": "clip", "query": query, "subject": subject,
                          "camera": CAMERAS[cam_i % len(CAMERAS)], "transition": "cut", "alt": 1})
            cam_i += 1
        sc["beats"] = beats
    return data


def _clean(beats: list[dict], tokens: list[str], sc: dict) -> list[dict]:
    """Make a hand-written beats list safe to render."""
    out, last = [], -1
    for b in beats:
        b = dict(b)
        b["shot"] = b.get("shot") if b.get("shot") in SHOTS else "clip"
        try:
            at = int(b.get("at_word", 0))
        except (TypeError, ValueError):
            at = 0
        at = 0 if not out else max(last + 1, min(at, max(len(tokens) - 1, 0)))
        if out and at <= last:
            continue
        b["at_word"] = at
        last = at
        b.setdefault("query", sc.get("visual") or sc.get("subject") or "")
        b.setdefault("subject", sc.get("subject"))
        sfx = b.get("sfx") or []
        b["sfx"] = [sfx] if isinstance(sfx, str) else list(sfx)
        out.append(b)
    return out or [{"at_word": 0, "shot": "clip", "query": sc.get("visual", ""), "subject": sc.get("subject")}]
