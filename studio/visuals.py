"""Pictures for each scene, and the thumbnail.

- With a free PEXELS_API_KEY or PIXABAY_API_KEY secret, each scene's English
  "visual" hint is searched on Pexels first, then Pixabay (free stock photos,
  free for YouTube use, no credit needed).
- Without a key (or if nothing is found) a clean gradient slide is drawn.
The scene's short "on_screen" headline is written on the picture.
"""
from __future__ import annotations

import hashlib
import os
import random
import re
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .common import font_family_for, font_file, log

PEXELS_URL = "https://api.pexels.com/v1/search"
PIXABAY_URL = "https://pixabay.com/api/"
PIXABAY_VIDEO_URL = "https://pixabay.com/api/videos/"


# ------------------------------------------------------- relevance check
# words that describe the scene, not the thing it is about
GENERIC = set("""a an the of in on at with and or to from by for close closeup up macro
underwater water ocean sea deep blue night day sky light sunlight sunset sunrise dark
background nature wild wildlife view aerial top side slow motion moving flying swimming
walking running small big large huge tiny old ancient young baby group many one two
forest trees tree field grass desert snow ice beach river lake cave space earth planet
world landscape scenery color colorful beautiful amazing""".split())


def subject_words(query: str, subject: str | None = None) -> list[str]:
    """The words a stock result must be tagged with (e.g. 'great white shark' -> shark)."""
    if subject:
        return [w.lower() for w in re.findall(r"[A-Za-z]+", subject)]
    words = [w.lower() for w in re.findall(r"[A-Za-z]+", query)]
    key = [w for w in words if w not in GENERIC and len(w) > 2]
    return key[-1:] if key else []          # the last real noun: "great white SHARK"


def tags_match(tags: str, need: list[str]) -> bool:
    have = {t.strip().lower() for t in re.split(r"[,\s]+", tags or "") if t.strip()}
    def ok(w: str) -> bool:
        return any(h == w or h.rstrip("s") == w.rstrip("s") or (len(w) > 4 and w in h) for h in have)
    return all(ok(w) for w in need)


# ------------------------------------------------------------------ helpers
def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _font(text: str, size: int) -> ImageFont.FreeTypeFont:
    path = font_file(font_family_for(text), bold=True)
    try:
        return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
    except Exception:
        return ImageFont.truetype(path, size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _fit_text(draw, text: str, max_w: int, max_h: int, start: int, min_size: int = 28):
    """Largest font size where the wrapped text fits the box."""
    size = start
    while size >= min_size:
        font = _font(text, size)
        lines = _wrap(draw, text, font, max_w)
        line_h = int(size * 1.35)
        if line_h * len(lines) <= max_h and all(
                draw.textlength(l, font=font) <= max_w for l in lines):
            return font, lines, line_h
        size -= 4
    font = _font(text, min_size)
    return font, _wrap(draw, text, font, max_w), int(min_size * 1.35)


def _draw_block(img: Image.Image, text: str, box: tuple[int, int, int, int],
                start_size: int, stroke: int = 0,
                fill: tuple[int, int, int] = (255, 255, 255)) -> None:
    """Centre `text` inside box=(x, y, w, h)."""
    draw = ImageDraw.Draw(img)
    x, y, w, h = box
    font, lines, line_h = _fit_text(draw, text, w, h, start_size)
    total = line_h * len(lines)
    cy = y + (h - total) // 2
    for line in lines:
        lw = draw.textlength(line, font=font)
        draw.text((x + (w - lw) / 2, cy), line, font=font, fill=fill,
                  stroke_width=stroke, stroke_fill=(0, 0, 0))
        cy += line_h


def _gradient(size: tuple[int, int], c1: str, c2: str, seed: int) -> Image.Image:
    w, h = size
    a, b = _hex(c1), _hex(c2)
    base = Image.new("RGB", (1, 256))
    for i in range(256):
        t = i / 255
        base.putpixel((0, i), tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3)))
    img = base.resize((w, h)).rotate(0)
    # Soft decorative circles so slides don't look flat
    rnd = random.Random(seed)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(6):
        r = rnd.randint(min(w, h) // 8, min(w, h) // 2)
        cx, cy = rnd.randint(-r // 2, w + r // 2), rnd.randint(-r // 2, h + r // 2)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, rnd.randint(10, 28)))
    layer = layer.filter(ImageFilter.GaussianBlur(min(w, h) // 30))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def _cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize + centre-crop to exactly fill `size`."""
    w, h = size
    scale = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


# ------------------------------------------------------------------- pexels
def pexels_photo(query: str, portrait: bool, seed: int, subject: str | None = None) -> Image.Image | None:
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key or not query:
        return None
    try:
        r = requests.get(PEXELS_URL, headers={"Authorization": key}, timeout=30, params={
            "query": query, "per_page": 15,
            "orientation": "portrait" if portrait else "landscape"})
        r.raise_for_status()
        photos = r.json().get("photos", [])
        need = subject_words(query, subject)
        photos = [p for p in photos if not need or tags_match(p.get("alt", ""), need)]
        if not photos:
            log(f"Pexels: nothing for '{query}', using a slide")
            return None
        photo = random.Random(seed).choice(photos[:8])
        img = requests.get(photo["src"]["large2x"], timeout=60)
        img.raise_for_status()
        return Image.open(BytesIO(img.content)).convert("RGB")
    except Exception as e:
        log(f"Pexels failed for '{query}': {e}")
        return None


# ------------------------------------------------------------------ pixabay
def pixabay_photo(query: str, portrait: bool, seed: int, subject: str | None = None) -> Image.Image | None:
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    query = " ".join(query.split())[:100]          # Pixabay allows max 100 chars
    if not key or not query:
        return None
    try:
        r = requests.get(PIXABAY_URL, timeout=30, params={
            "key": key, "q": query, "image_type": "photo", "safesearch": "true",
            "orientation": "vertical" if portrait else "horizontal",
            "order": "popular", "per_page": 20})
        if r.status_code != 200:
            # Pixabay answers errors as plain text; never log the URL (it holds the key)
            log(f"Pixabay error {r.status_code} for '{query}': {r.text.strip()[:120]}")
            return None
        hits = r.json().get("hits", [])
        need = subject_words(query, subject)
        good = [h for h in hits if not need or tags_match(h.get("tags", ""), need)]
        if not good and need and query.lower().split() != need:
            return pixabay_photo(" ".join(need), portrait, seed, subject)   # just the subject
        if not good:
            log(f"Pixabay: nothing tagged {need or query!r} for '{query}', using a slide")
            return None
        hit = random.Random(seed).choice(good[:8])
        url = hit.get("largeImageURL") or hit.get("webformatURL")
        img = requests.get(url, timeout=60)
        img.raise_for_status()
        return Image.open(BytesIO(img.content)).convert("RGB")
    except Exception as e:
        log(f"Pixabay failed for '{query}': {type(e).__name__}")
        return None


# clips already used in the video being made, so the same footage never comes back
_USED_CLIPS: set[int] = set()
CLIP_START: dict[str, float] = {}


def reset_clips() -> None:
    _USED_CLIPS.clear()
    CLIP_START.clear()


def _pixabay_hits(key: str, query: str, page: int = 1) -> list[dict]:
    r = requests.get(PIXABAY_VIDEO_URL, timeout=30, params={
        "key": key, "q": query, "video_type": "film", "safesearch": "true",
        "order": "popular", "per_page": 50, "page": page})
    if r.status_code != 200:
        log(f"Pixabay video error {r.status_code} for '{query}': {r.text.strip()[:120]}")
        return []
    return r.json().get("hits", [])


def pixabay_video(query: str, pick: int, out: Path, subject: str | None = None) -> Path | None:
    """A free stock video clip from Pixabay (same key as photos), saved to out.
    Only clips tagged with the scene's subject (shark, octopus ...) are used, and a clip
    already used earlier in the same video is skipped, so footage doesn't repeat."""
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    query = " ".join(query.split())[:100]
    if not key or not query:
        return None
    if out.exists() and out.stat().st_size > 10000:
        return out
    try:
        need = subject_words(query, subject)
        searches = [(query, 1)]
        if need and query.lower().split() != need:
            searches.append((" ".join(need), 1))
        searches.append((searches[-1][0], 2))
        seen, fresh, old = set(), [], []
        for q, page in searches:
            for hit in _pixabay_hits(key, q, page):
                hid = hit.get("id")
                if hid in seen or not 3 <= float(hit.get("duration", 0)) <= 60:
                    continue
                seen.add(hid)
                if need and not tags_match(hit.get("tags", ""), need):
                    continue
                for size in ("large", "medium"):
                    v = (hit.get("videos") or {}).get(size) or {}
                    if v.get("url") and v.get("height", 0) >= 720 and 0 < v.get("size", 0) < 45_000_000:
                        item = (hid, float(hit.get("duration", 0)), v)
                        (old if hid in _USED_CLIPS else fresh).append(item)
                        break
            if len(fresh) >= 6:
                break
        if not fresh and not old:
            log(f"Pixabay: no video tagged {need or query!r} for '{query}'")
            return None
        if fresh:
            hid, dur, v = fresh[:6][pick % len(fresh[:6])]
            start = 0.0
        else:   # every matching clip is used already: take one again, from a later part of it
            hid, dur, v = old[pick % len(old)]
            start = round(dur * 0.5, 2) if dur > 8 else 0.0
            log(f"Pixabay: only reused clips left for '{query}', starting at {start}s")
        _USED_CLIPS.add(hid)
        data = requests.get(v["url"], timeout=120)
        data.raise_for_status()
        out.write_bytes(data.content)
        CLIP_START[str(out)] = start
        log(f"Video clip from Pixabay for '{query}' ({v.get('width')}x{v.get('height')}, clip {hid})")
        return out
    except Exception as e:
        log(f"Pixabay video failed for '{query}': {type(e).__name__}")
        return None


def headline_overlay(headline: str, size: tuple[int, int], out: Path) -> Path | None:
    """Transparent picture with the scene headline on a dark top band (for video clips)."""
    headline = headline.strip()
    if not headline:
        return None
    w, h = size
    portrait = h > w
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    band = int(h * (0.28 if not portrait else 0.22))
    for y in range(band):
        d.line([(0, y), (w, y)], fill=(0, 0, 0, int(170 * (1 - y / band))))
    _draw_block(img, headline, (int(w * .08), int(h * .06), int(w * .84), int(band * .7)),
                start_size=int(h * 0.07), stroke=3)
    img.save(out)
    return out


def stock_photo(query: str, portrait: bool, seed: int, subject: str | None = None) -> Image.Image | None:
    """Pexels if its key is set, then Pixabay, else None (gradient slide)."""
    for name, fetch in (("Pexels", pexels_photo), ("Pixabay", pixabay_photo)):
        photo = fetch(query, portrait, seed, subject)
        if photo is not None:
            log(f"Photo from {name} for '{query}' ({photo.width}x{photo.height})")
            return photo
    if not (os.environ.get("PEXELS_API_KEY", "").strip()
            or os.environ.get("PIXABAY_API_KEY", "").strip()):
        log(f"No photo key set: slide for '{query}'")
    return None


# ------------------------------------------------------------------- public
def scene_image(scene: dict, index: int, title: str, cfg: dict,
                size: tuple[int, int], out: Path) -> Path:
    """Draw one scene picture (2x size, so the slow zoom stays sharp)."""
    w, h = size[0] * 2, size[1] * 2
    portrait = h > w
    seed = int(hashlib.md5(f"{title}-{index}".encode()).hexdigest()[:8], 16)
    headline = str(scene.get("on_screen") or "").strip()

    photo = None
    if cfg["video"].get("visuals", "auto") == "auto":
        photo = stock_photo(str(scene.get("visual", "")), portrait, seed, scene.get("subject"))

    bg_path = out.with_name(out.stem + "_bg.jpg")   # clean copy for the thumbnail
    if photo is not None:
        img = _cover(photo, (w, h))
        img.save(bg_path, quality=90)
        if headline:
            # dark band at the top so the headline is readable on any photo
            shade = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(shade)
            band = int(h * (0.28 if not portrait else 0.22))
            for y in range(band):
                d.line([(0, y), (w, y)], fill=(0, 0, 0, int(170 * (1 - y / band))))
            img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
            # kept away from the edges: the slow zoom crops up to ~4% per side
            _draw_block(img, headline, (int(w * .08), int(h * .06), int(w * .84), int(band * .7)),
                        start_size=int(h * 0.07), stroke=3)
    else:
        palette = cfg["video"].get("palette") or [["#0f2027", "#2c5364"]]
        c1, c2 = palette[index % len(palette)]
        img = _gradient((w, h), c1, c2, seed)
        img.save(bg_path, quality=90)
        text = headline or title
        box_h = int(h * (0.45 if not portrait else 0.35))
        _draw_block(img, text, (int(w * .1), int(h * .5 - box_h * .75), int(w * .8), box_h),
                    start_size=int(h * (0.11 if not portrait else 0.065)), stroke=2)

    img.save(out, quality=92)
    return out


def thumbnail(data: dict, first_scene_img: Path, out: Path) -> Path:
    """1280x720 thumbnail: first picture, darkened, with big bold text."""
    text = str(data.get("thumbnail_text") or data["title"]).strip()
    bg = first_scene_img.with_name(first_scene_img.stem + "_bg.jpg")
    src = bg if bg.exists() else first_scene_img
    base = _cover(Image.open(src).convert("RGB"), (1280, 720))
    base = Image.blend(base, Image.new("RGB", base.size, (0, 0, 0)), 0.35)
    _draw_block(base, text, (70, 80, 1140, 560), start_size=130, stroke=7,
                fill=(255, 214, 0))
    base.save(out, "JPEG", quality=90)
    return out
