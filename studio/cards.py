"""Floating showcase cards and name tags (mindblip-studio core/motion.md §1, §4, §7).

A card is a smaller, framed picture that floats in over a dimmed background while the
narration names the thing: polaroid, print with a margin, rounded box, torn-edge
cut-out, letterbox band or a thought bubble (for "imagine" lines). 2-3 per Short,
each a different style, never the same picture twice.

It lands with "settle & hold": arrives a little lower and bigger, slightly blurred,
settles in about 9 frames with a long ease, then holds still.

A name tag is the lower-third label (yellow bar, big name, small line under it).
Everything here is drawn with Pillow into transparent PNG frames; the renderer lays
them over the shot with ffmpeg and the last frame holds.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .common import ROOT

FONT_DIR = ROOT / "assets" / "fonts"
BOLD = FONT_DIR / "Montserrat.ttf"
HAND = FONT_DIR / "Caveat.ttf"
PAPER = (244, 239, 228)          # warm off-white, never pure white
INK = (40, 36, 32)
YELLOW = (255, 214, 10)
STYLES = ("polaroid", "print", "rounded", "torn", "letterbox", "bubble")
ASPECT = {"polaroid": [1.0, 0.8], "print": [0.8, 1.25, 1.0], "rounded": [0.8, 1.0, 1.25],
          "torn": [0.8, 1.0, 1.25], "letterbox": [2.2, 1.78], "bubble": [1.25, 1.0]}


def _font(path: Path, px: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), px)
    except Exception:
        return ImageFont.load_default()


# ------------------------------------------------------------------ picture crop
def crop_for(img: Image.Image, box: tuple | None, style: str) -> Image.Image:
    """A crop of the picture in one of the style's shapes that keeps the whole subject
    (box = 0..1 keep-box) with room around it. If no shape can hold it, the crop is
    widened to the picture's own shape: the subject is never cut."""
    W, H = img.size
    if box:
        bw, bh = (box[2] - box[0]) * W, (box[3] - box[1]) * H
        pad = 0.10
        bx0, by0 = max(box[0] * W - bw * pad, 0), max(box[1] * H - bh * pad, 0)
        bx1, by1 = min(box[2] * W + bw * pad, W), min(box[3] * H + bh * pad, H)
    else:
        bx0, by0, bx1, by1 = W * 0.1, H * 0.1, W * 0.9, H * 0.9
    bw, bh = bx1 - bx0, by1 - by0
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
    best = None
    for a in ASPECT.get(style, [1.0]):
        # the smallest window of aspect a that holds the subject, at least 1.25x its size
        ww = max(bw, bh * a) * 1.12
        wh = ww / a
        if ww > W or wh > H:
            k = min(W / ww, H / wh)
            ww, wh = ww * k, wh * k
        if ww + 0.5 < bw or wh + 0.5 < bh:         # this shape can't hold the subject
            continue
        best = (ww, wh)
        break
    if best is None:                               # widest shape the picture allows
        a = max(bw / max(bh, 1), 0.5)
        ww, wh = (min(W, H * a), min(W, H * a) / a)
        if wh > H:
            wh, ww = H, H * a
        best = (ww, wh)
    ww, wh = best
    x = min(max(cx - ww / 2, 0), W - ww)
    y = min(max(cy - wh / 2, 0), H - wh)
    return img.crop((int(x), int(y), int(x + ww), int(y + wh)))


# ------------------------------------------------------------------ card styles
def _paper(size: tuple[int, int], rnd: random.Random) -> Image.Image:
    w, h = size
    base = np.zeros((h, w, 3), np.float32) + np.array(PAPER, np.float32)
    noise = np.random.default_rng(rnd.randint(0, 10 ** 6)).normal(0, 5, (h // 4 + 1, w // 4 + 1, 1))
    noise = np.kron(noise, np.ones((4, 4, 1)))[:h, :w]
    return Image.fromarray(np.clip(base + noise, 0, 255).astype(np.uint8), "RGB")


def _round_mask(size: tuple[int, int], r: int) -> Image.Image:
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), r, fill=255)
    return m


def _torn_mask(size: tuple[int, int], rnd: random.Random, depth: int) -> Image.Image:
    w, h = size
    pts = []
    step = 9
    for x in range(0, w, step):
        pts.append((x, rnd.uniform(0, depth)))
    for y in range(0, h, step):
        pts.append((w - rnd.uniform(0, depth), y))
    for x in range(w, 0, -step):
        pts.append((x, h - rnd.uniform(0, depth)))
    for y in range(h, 0, -step):
        pts.append((rnd.uniform(0, depth), y))
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return m.filter(ImageFilter.GaussianBlur(0.6))


def _shadow(card: Image.Image, blur: int, offset: tuple[int, int], alpha: int) -> Image.Image:
    """Card on a bigger transparent canvas with a soft drop shadow under it."""
    m = blur * 3
    w, h = card.size
    out = Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    a = card.split()[-1].point(lambda v: v * alpha // 255)
    sh.paste((0, 0, 0, 255), (m + offset[0], m + offset[1]), a)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(sh)
    out.alpha_composite(card, (m, m))
    return out


def style_card(pic: Image.Image, style: str, max_w: int, max_h: int, caption: str = "",
               seed: int = 0, tail_to: tuple[float, float] | None = None) -> Image.Image:
    """The finished card (RGBA, with shadow, tilted for the paper styles)."""
    rnd = random.Random(seed)
    style = style if style in STYLES else "rounded"
    pic = pic.convert("RGB")
    if style == "polaroid":
        side, bottom = 0.06, 0.24
    elif style in ("print", "torn"):
        side, bottom = 0.05, 0.05
    elif style == "bubble":
        side, bottom = 0.07, 0.07
    else:
        side, bottom = 0.0, 0.0
    # fit picture + border inside max_w x max_h
    a = pic.width / pic.height
    pw = max_w / (1 + 2 * side)
    ph = pw / a
    if ph * (1 + side + bottom) > max_h:
        ph = max_h / (1 + side + bottom)
        pw = ph * a
    pw, ph = int(pw), int(ph)
    pic = pic.resize((max(pw, 2), max(ph, 2)), Image.LANCZOS)
    b, bb = int(pw * side), int(pw * bottom) if style == "polaroid" else int(pw * side)
    if style in ("polaroid", "print", "torn"):
        card = _paper((pw + 2 * b, ph + b + bb), rnd).convert("RGBA")
        # the photo itself: very slightly faded, like a print
        photo = Image.blend(pic, Image.new("RGB", pic.size, PAPER), 0.04)
        card.paste(photo, (b, b))
        d = ImageDraw.Draw(card)
        d.rectangle((b - 1, b - 1, b + pw, b + ph), outline=(0, 0, 0, 40), width=1)
        if style == "polaroid" and caption:
            f = _font(HAND, max(int(bb * 0.42), 20))
            tw = d.textlength(caption, font=f)
            if tw > pw:
                f = _font(HAND, max(int(bb * 0.42 * pw / tw), 16))
                tw = d.textlength(caption, font=f)
            d.text(((card.width - tw) / 2, b + ph + bb * 0.22), caption, font=f, fill=INK)
        if style == "torn":
            card.putalpha(_torn_mask(card.size, rnd, max(int(b * 0.55), 6)))
        tilt = rnd.choice([-1, 1]) * rnd.uniform(2.0, 4.5)
        card = card.rotate(tilt, Image.BICUBIC, expand=True)
        return _shadow(card, 18, (8, 14), 150)
    if style == "rounded":
        r = int(min(pw, ph) * 0.07)
        card = Image.new("RGBA", (pw + 12, ph + 12), (0, 0, 0, 0))
        ImageDraw.Draw(card).rounded_rectangle((0, 0, pw + 11, ph + 11), r + 6, fill=(255, 255, 255, 235))
        inner = pic.convert("RGBA")
        inner.putalpha(_round_mask(pic.size, r))
        card.alpha_composite(inner, (6, 6))
        return _shadow(card, 22, (0, 16), 160)
    if style == "letterbox":
        card = pic.convert("RGBA")
        d = ImageDraw.Draw(card)
        d.rectangle((0, 0, pw - 1, 3), fill=(255, 255, 255, 200))
        d.rectangle((0, ph - 4, pw - 1, ph - 1), fill=(255, 255, 255, 200))
        return _shadow(card, 20, (0, 12), 150)
    # bubble: a soft cloud with the picture inside and little circles trailing to a head
    r = int(min(pw, ph) * 0.16)
    bw, bh = pw + 2 * b, ph + 2 * b
    pad = int(max(bw, bh) * 0.35)
    canvas = Image.new("RGBA", (bw + 2 * pad, bh + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    x0, y0 = pad, pad
    # scalloped edge: circles all round the rounded box
    for k in range(28):
        ang = 2 * math.pi * k / 28
        cx = x0 + bw / 2 + math.cos(ang) * bw / 2 * 0.98
        cy = y0 + bh / 2 + math.sin(ang) * bh / 2 * 0.98
        rr = r * rnd.uniform(0.75, 1.0)
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=(255, 255, 255, 245))
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), r, fill=(255, 255, 255, 245))
    inner = pic.convert("RGBA")
    inner.putalpha(_round_mask(pic.size, int(r * 0.7)))
    canvas.alpha_composite(inner, (x0 + b, y0 + b))
    # trailing circles toward tail_to (canvas-relative direction, default down-left)
    tx, ty = tail_to if tail_to else (-0.6, 1.0)
    n = math.hypot(tx, ty) or 1
    tx, ty = tx / n, ty / n
    sx = x0 + bw / 2 + tx * bw / 2 * 0.9
    sy = y0 + bh / 2 + ty * bh / 2 * 0.95
    for k, rr in enumerate((r * 0.55, r * 0.38, r * 0.24)):
        cx = sx + tx * (r * 0.9 + (k + 1) * r * 1.2)
        cy = sy + ty * (r * 0.9 + (k + 1) * r * 1.2)
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=(255, 255, 255, 245))
    bbox = canvas.getbbox()
    canvas = canvas.crop(bbox) if bbox else canvas
    return _shadow(canvas, 16, (0, 10), 120)


# ------------------------------------------------------------------ animation
def _ease_out(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def settle_frames(card: Image.Image, fps: int, out_dir: Path, frames: int = 9) -> tuple[Path, int, int]:
    """Settle & hold: from 7% bigger, 40 px lower and blurred to sharp and still.
    Frames are the card's own size plus margin; returns (dir, margin_x, margin_y)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()
    w, h = card.size
    mx, my = int(w * 0.05), int(h * 0.05) + 44
    for i in range(frames + 1):
        e = _ease_out(i / frames)
        s = 1.07 - 0.07 * e
        dy = 40 * (1 - e)
        blur = 8 * (1 - e)
        alpha = min(1.0, i / 3)
        im = card.resize((max(int(w * s), 2), max(int(h * s), 2)), Image.BICUBIC)
        if blur > 0.4:
            im = im.filter(ImageFilter.GaussianBlur(blur))
        if alpha < 1:
            im.putalpha(im.split()[-1].point(lambda v: int(v * alpha)))
        frame = Image.new("RGBA", (w + 2 * mx, h + 2 * my), (0, 0, 0, 0))
        frame.alpha_composite(im, (int(mx + (w - im.width) / 2), int(my + (h - im.height) / 2 + dy)))
        frame.save(out_dir / f"{i:04d}.png", compress_level=1)
    return out_dir, mx, my


def tag_frames(title: str, sub: str, size: tuple[int, int], fps: int, out_dir: Path) -> tuple[Path, int, int]:
    """Lower-third name tag: the yellow bar grows, then the name and the line under it
    wipe in from the left. Returns (dir, x, y) of the frames on the screen."""
    W, H = size
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()
    title = title.upper()
    ft = _font(BOLD, int(H * 0.034))
    fs = _font(BOLD, int(H * 0.020))
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    tw = probe.textlength(title, font=ft)
    if tw > W * 0.78:
        ft = _font(BOLD, int(H * 0.034 * W * 0.78 / tw))
        tw = probe.textlength(title, font=ft)
    sw = probe.textlength(sub, font=fs) if sub else 0
    bar_w, gap = int(W * 0.011), int(W * 0.022)
    cw = int(bar_w + gap + max(tw, sw) + 40)
    ch = int(H * 0.034 * 1.25 + (H * 0.020 * 1.5 if sub else 0) + 30)
    n = 14
    for i in range(n + 1):
        img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        e_bar = _ease_out(i / 5)
        bh = int((ch - 16) * e_bar)
        d.rectangle((0, (ch - bh) // 2, bar_w, (ch + bh) // 2), fill=YELLOW + (255,))
        e_txt = _ease_out((i - 3) / (n - 3))
        if e_txt > 0:
            txt = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            dt = ImageDraw.Draw(txt)
            x = bar_w + gap - int(30 * (1 - e_txt))
            for o in (3, 2):
                dt.text((x + o, 8 + o), title, font=ft, fill=(0, 0, 0, 120))
            dt.text((x, 8), title, font=ft, fill=(255, 255, 255, 255))
            if sub:
                y2 = 8 + int(H * 0.034 * 1.2)
                dt.text((x + 2, y2 + 2), sub, font=fs, fill=(0, 0, 0, 120))
                dt.text((x, y2), sub, font=fs, fill=(225, 225, 225, 255))
            # wipe: only the part left of the moving edge shows
            m = Image.new("L", (cw, ch), 0)
            ImageDraw.Draw(m).rectangle((0, 0, int(bar_w + (cw - bar_w) * e_txt), ch), fill=255)
            txt.putalpha(ImageChops.multiply(txt.split()[-1], m))
            img.alpha_composite(txt)
        img.save(out_dir / f"{i:04d}.png", compress_level=1)
    return out_dir, int(W * 0.06), int(H * 0.705)
