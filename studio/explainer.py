"""Animated explainer style ("style": "explainer"): flat 2D motion graphics drawn in code.

Each scene of the script is one shot. Its "text" is spoken (or "hold" seconds of
silence when there is no text), and its "els" are the pieces that pop in on screen:

    {"text": "Reason number one: names don't mean anything.",
     "bg": "navy", "tr": "zap", "chapter": "Reason 1: Names mean nothing",
     "els": [{"type": "title", "top": "REASON #1", "sub": "NAMES MEAN NOTHING"},
             {"type": "blip", "pose": "shrug", "x": 0.8, "y": 0.6, "at": "w3"}]}

Times ("at", "until", "dissolve", path keys) are seconds from the shot start, or
"w5" (when word 5 of the text is spoken), "e-1" (1 s before the shot ends),
or "p0.5" (half-way through the shot).

Everything is drawn with Pillow and numpy, with free fonts (Montserrat, Inter,
Caveat: SIL Open Font License) and Noto Color Emoji for small object icons.
"""
from __future__ import annotations

import json
import math
import random
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .common import ROOT, log
from .motion import _back, _ease, _out, emoji_image, write_sfx

FONTS = ROOT / "assets" / "fonts"
NAVY, PANEL = (11, 16, 32), (20, 27, 51)
CYAN, PINK, YELLOW, WHITE = (46, 230, 214), (255, 92, 138), (255, 214, 0), (244, 244, 248)
SKINS = [(236, 196, 164), (198, 140, 100), (141, 94, 66), (245, 214, 186)]
COLORS = {"cyan": CYAN, "pink": PINK, "yellow": YELLOW, "white": WHITE, "navy": NAVY,
          "red": (232, 64, 64), "grey": (140, 146, 165), "black": (20, 20, 20), "green": (80, 220, 120)}


def col(c, default=WHITE):
    if c is None:
        return default
    if isinstance(c, (list, tuple)):
        return tuple(c)
    return COLORS.get(str(c), default)


@lru_cache(maxsize=None)
def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    name = {"title": "Montserrat.ttf", "body": "Inter.ttf", "hand": "Caveat.ttf"}[kind]
    try:
        return ImageFont.truetype(str(FONTS / name), max(size, 6))
    except OSError:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", max(size, 6))


def _lerp(a, b, p):
    return a + (b - a) * p


# ----------------------------------------------------------------- sprites
def text_img(text: str, size: int, fill=WHITE, kind="title", spacing=0.04, stroke=0,
             stroke_fill=(0, 0, 0), shadow=True) -> Image.Image:
    f = font(kind, size)
    sp = int(size * spacing) if kind == "title" else 0
    widths = [f.getbbox(ch)[2] - f.getbbox(ch)[0] if ch != " " else size * 0.28 for ch in text]
    asc, desc = f.getmetrics()
    w = int(sum(f.getlength(ch) for ch in text) + sp * max(len(text) - 1, 0)) + 2 * stroke + 8
    h = asc + desc + 2 * stroke + 8
    pad = int(size * 0.25)
    img = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = pad + stroke + 4
    for ch in text:
        d.text((x, pad + stroke + 4), ch, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        x += f.getlength(ch) + sp
    del widths
    if shadow:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sh.paste((0, 0, 0, 140), (0, max(2, size // 22)), img)
        sh = sh.filter(ImageFilter.GaussianBlur(max(2, size // 14)))
        sh.alpha_composite(img)
        img = sh
    return img


def wrap_lines(text: str, size: int, max_w: int, kind="title") -> list[str]:
    f = font(kind, size)
    words, lines, cur = text.split(), [], ""
    for wd in words:
        test = (cur + " " + wd).strip()
        if f.getlength(test) * 1.05 > max_w and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def block_img(text: str, size: int, fill=WHITE, kind="title", max_w=1500, box=None,
              box_pad=0.35, radius=0.3, align="center") -> Image.Image:
    lines = wrap_lines(text, size, max_w, kind)
    imgs = [text_img(ln, size, fill, kind, shadow=box is None) for ln in lines]
    gap = int(size * -0.18)
    w = max(i.width for i in imgs)
    h = sum(i.height for i in imgs) + gap * (len(imgs) - 1)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    y = 0
    for im in imgs:
        x = (w - im.width) // 2 if align == "center" else 0
        out.alpha_composite(im, (x, y))
        y += im.height + gap
    if box is not None:
        bb = out.getbbox() or (0, 0, w, h)
        p = int(size * box_pad)
        bw, bh = bb[2] - bb[0] + 2 * p, bb[3] - bb[1] + 2 * p
        b = Image.new("RGBA", (bw + 20, bh + 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(b)
        d.rounded_rectangle((10, 10, 10 + bw, 10 + bh), radius=int(size * radius), fill=box)
        b.alpha_composite(out.crop(bb), (10 + p, 10 + p))
        sh = Image.new("RGBA", b.size, (0, 0, 0, 0))
        sh.paste((0, 0, 0, 120), (0, 6), b)
        sh = sh.filter(ImageFilter.GaussianBlur(8))
        sh.alpha_composite(b)
        out = sh
    return out


def glow(img: Image.Image, color, radius: int, strength: float = 1.0) -> Image.Image:
    """Add a soft colored glow behind an RGBA sprite."""
    pad = radius * 2
    out = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    a = img.getchannel("A")
    g = Image.new("RGBA", out.size, (0, 0, 0, 0))
    g.paste(color + (int(200 * strength),), (pad, pad), a)
    g = g.filter(ImageFilter.GaussianBlur(radius))
    out.alpha_composite(g)
    out.alpha_composite(img, (pad, pad))
    return out


def _ss(w, h, k=2):
    img = Image.new("RGBA", (int(w * k), int(h * k)), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _down(img, k=2):
    return img.resize((max(1, img.width // k), max(1, img.height // k)), Image.LANCZOS)


def sticker_img(name: str, size: int, blank=False, q=False, progress=1.0) -> Image.Image:
    """'HELLO my name is' sticker (size = height in px)."""
    k = 2
    h = size
    w = int(size * 1.45)
    img, d = _ss(w, h, k)
    r = int(h * 0.12 * k)
    d.rounded_rectangle((0, 0, w * k - 1, h * k - 1), radius=r, fill=(255, 255, 255))
    d.rounded_rectangle((0, 0, w * k - 1, int(h * 0.36 * k)), radius=r, fill=(214, 40, 48))
    d.rectangle((0, int(h * 0.2 * k), w * k - 1, int(h * 0.36 * k)), fill=(214, 40, 48))
    fh = font("title", int(h * 0.16 * k))
    fs = font("body", int(h * 0.09 * k))
    d.text((w * k / 2, h * 0.13 * k), "HELLO", font=fh, fill=WHITE, anchor="mm")
    d.text((w * k / 2, h * 0.28 * k), "my name is", font=fs, fill=WHITE, anchor="mm")
    if not blank and name:
        shown = name[: max(0, round(len(name) * progress))]
        d.text((w * k / 2, h * 0.68 * k), shown, font=font("hand", int(h * 0.42 * k)),
               fill=(25, 35, 90), anchor="mm")
    if q:
        d.text((w * k / 2, h * 0.68 * k), "?", font=font("title", int(h * 0.38 * k)), fill=PINK, anchor="mm")
    img = _down(img, k)
    sh = Image.new("RGBA", (img.width + 30, img.height + 30), (0, 0, 0, 0))
    s2 = Image.new("RGBA", sh.size, (0, 0, 0, 0))
    s2.paste((0, 0, 0, 120), (15, 21), img)
    s2 = s2.filter(ImageFilter.GaussianBlur(7))
    s2.alpha_composite(img, (15, 15))
    return s2


# ----------------------------------------------------------------- people
PEOPLE = {
    "everyman": {"top": (38, 166, 154), "legs": (40, 48, 72), "skin": SKINS[0], "hair": None, "hood": True},
    "megan": {"top": (255, 207, 64), "legs": None, "skin": SKINS[3], "hair": (176, 74, 40), "curly": True,
              "dress": True},
    "jessica": {"top": (128, 72, 196), "legs": (30, 30, 46), "skin": SKINS[1], "hair": (24, 24, 28),
                "ponytail": True},
    "suit": {"top": (90, 96, 112), "legs": (60, 64, 76), "skin": SKINS[0], "hair": (60, 44, 30), "tie": True},
}


def _person_spec(who: str, seed: int = 0) -> dict:
    if who in PEOPLE:
        return PEOPLE[who]
    rnd = random.Random(seed)
    tops = [(214, 120, 90), (90, 140, 214), (120, 190, 110), (200, 160, 80), (170, 110, 170), (80, 170, 190)]
    return {"top": rnd.choice(tops), "legs": (52, 58, 80), "skin": rnd.choice(SKINS),
            "hair": rnd.choice([(40, 30, 20), (90, 60, 30), (20, 20, 20), (150, 110, 60)]),
            "short": rnd.random() < .5}


def _arm(d, sx, sy, ang, length, width, color, skin, bend=None):
    """Arm from shoulder at angle (deg, 0 = straight down, + = outward to the right)."""
    a = math.radians(ang)
    if bend is None:
        ex, ey = sx + math.sin(a) * length, sy + math.cos(a) * length
        d.line((sx, sy, ex, ey), fill=color, width=int(width))
        d.ellipse((ex - width * .55, ey - width * .55, ex + width * .55, ey + width * .55), fill=skin)
        return ex, ey
    b = math.radians(bend)
    mx, my = sx + math.sin(a) * length * .52, sy + math.cos(a) * length * .52
    ex, ey = mx + math.sin(b) * length * .5, my + math.cos(b) * length * .5
    d.line((sx, sy, mx, my), fill=color, width=int(width))
    d.line((mx, my, ex, ey), fill=color, width=int(width))
    d.ellipse((mx - width / 2, my - width / 2, mx + width / 2, my + width / 2), fill=color)
    d.ellipse((ex - width * .55, ey - width * .55, ex + width * .55, ey + width * .55), fill=skin)
    return ex, ey


@lru_cache(maxsize=512)
def person_img(who: str, pose: str, height: int, phase: int = 0, seed: int = 0) -> Image.Image:
    """Flat 2D adult, front view, no face details. phase animates waves/walks (0..7)."""
    sp = _person_spec(who, seed)
    k = 2
    u = height * k / 6.4                     # head height unit
    W, H = int(u * 5.5), int(height * k + u * 0.6)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = W / 2
    head_top = u * 0.35
    neck = head_top + u * 1.05
    sh_y = neck + u * 0.25
    hip = sh_y + u * 2.4
    foot = H - u * 0.25
    skin, top = sp["skin"], sp["top"]
    legs = sp.get("legs") or skin
    swing = math.sin(phase / 8 * 2 * math.pi) if pose == "walk" else 0
    # back hair / hood / ponytail
    if sp.get("hood"):
        d.ellipse((cx - u * .62, head_top - u * .12, cx + u * .62, head_top + u * 1.2), fill=tuple(int(c * .8) for c in top))
    if sp.get("ponytail"):
        d.ellipse((cx + u * .25, head_top + u * .2, cx + u * .85, head_top + u * 1.35), fill=sp["hair"])
    if sp.get("curly"):
        for ang in range(0, 360, 30):
            a = math.radians(ang)
            px, py = cx + math.cos(a) * u * .52, head_top + u * .55 + math.sin(a) * u * .6
            if py < head_top + u * 1.25:
                d.ellipse((px - u * .26, py - u * .26, px + u * .26, py + u * .26), fill=sp["hair"])
    # legs
    lw = u * .42
    for side in (-1, 1):
        lx = cx + side * u * .32
        off = side * swing * u * .5
        if sp.get("dress"):
            d.line((lx, hip + u * 1.1, lx + off, foot - u * .1), fill=skin, width=int(lw * .8))
        else:
            d.line((lx, hip - u * .1, lx + off, foot - u * .15), fill=legs, width=int(lw))
        d.ellipse((lx + off - u * .3, foot - u * .3, lx + off + u * .3, foot), fill=(40, 40, 50))
    # torso
    if sp.get("dress"):
        d.polygon([(cx - u * .6, sh_y), (cx + u * .6, sh_y), (cx + u * 1.05, hip + u * 1.25),
                   (cx - u * 1.05, hip + u * 1.25)], fill=top)
    else:
        d.rounded_rectangle((cx - u * .75, sh_y - u * .1, cx + u * .75, hip + u * .15), radius=u * .35, fill=top)
        if sp.get("hood"):
            d.line((cx - u * .2, sh_y + u * .2, cx - u * .2, sh_y + u * .9), fill=(230, 240, 240), width=int(u * .08))
            d.line((cx + u * .2, sh_y + u * .2, cx + u * .2, sh_y + u * .9), fill=(230, 240, 240), width=int(u * .08))
            d.rounded_rectangle((cx - u * .45, hip - u * .75, cx + u * .45, hip - u * .25), radius=u * .1,
                                fill=tuple(int(c * .85) for c in top))
        if sp.get("tie"):
            d.polygon([(cx - u * .25, sh_y - u * .05), (cx + u * .25, sh_y - u * .05), (cx, sh_y + u * .55)],
                      fill=(240, 240, 240))
            d.polygon([(cx - u * .08, sh_y + u * .05), (cx + u * .08, sh_y + u * .05), (cx + u * .12, sh_y + u * 1.2),
                       (cx, sh_y + u * 1.35), (cx - u * .12, sh_y + u * 1.2)], fill=(200, 50, 60))
    # arms
    aw = u * .36
    sx_l, sx_r = cx - u * .72, cx + u * .72
    arm_c = top if not sp.get("dress") else skin
    L, R, RB, LB = 8, -8, None, None        # angles: + outward
    if pose == "wave":
        R, RB = -150 + 18 * math.sin(phase / 8 * 2 * math.pi), None
    elif pose == "hand":
        R = -78
    elif pose == "point":
        R = -100
    elif pose == "think":
        R, RB = -25, 175
    elif pose == "plate":
        R, RB = -30, -95
    elif pose == "shrug":
        L, LB, R, RB = 40, 140, -40, -140
    elif pose == "walk":
        L, R = 8 + swing * 22, -8 + swing * 22
    elif pose == "juggle":
        L, LB, R, RB = 35, 150, -35, -150
    elif pose == "glance":
        R = -12
    # left arm (viewer's left) angle is mirrored
    _arm(d, sx_l, sh_y + u * .1, -L if LB is None else -L, u * 2.2, aw, arm_c, skin,
         None if LB is None else -LB)
    _arm(d, sx_r, sh_y + u * .1, -R, u * 2.2, aw, arm_c, skin, None if RB is None else -RB)
    if pose == "plate":
        hx, hy = sx_r + math.sin(math.radians(30)) * u * 1.15, sh_y + u * .1 + math.cos(math.radians(30)) * u * 1.15
        d.ellipse((hx - u * .2, hy - u * .55, hx + u * 1.2, hy - u * .15), fill=(250, 250, 250), outline=(200, 200, 200))
    # neck + head
    d.rectangle((cx - u * .16, neck - u * .1, cx + u * .16, sh_y + u * .05), fill=skin)
    d.ellipse((cx - u * .42, head_top, cx + u * .42, head_top + u * 1.05), fill=skin)
    hair = sp.get("hair")
    if hair is not None and not sp.get("curly"):
        if sp.get("short") or who == "suit":
            d.chord((cx - u * .44, head_top - u * .05, cx + u * .44, head_top + u * .7), 180, 360, fill=hair)
        else:
            d.chord((cx - u * .46, head_top - u * .06, cx + u * .46, head_top + u * .8), 170, 370, fill=hair)
    if sp.get("curly"):
        for ang in range(200, 341, 28):
            a = math.radians(ang)
            px, py = cx + math.cos(a) * u * .42, head_top + u * .5 + math.sin(a) * u * .5
            d.ellipse((px - u * .2, py - u * .2, px + u * .2, py + u * .2), fill=hair)
    return _down(img, k)


@lru_cache(maxsize=256)
def topdown_img(size: int, seed: int, highlight=None) -> Image.Image:
    """A person seen from above: shoulders + head."""
    sp = _person_spec("guest", seed)
    k = 2
    s = size * k
    img = Image.new("RGBA", (int(s * 1.4), int(s * 1.4)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = s * .7
    if highlight:
        d.ellipse((c - s * .62, c - s * .5, c + s * .62, c + s * .5), outline=highlight, width=int(s * .08))
    d.ellipse((c - s * .5, c - s * .26, c + s * .5, c + s * .26), fill=sp["top"])
    d.ellipse((c - s * .2, c - s * .2, c + s * .2, c + s * .2), fill=sp["hair"])
    return _down(img, k)


# ----------------------------------------------------------------- Blip
def _drawn_face(d, cx, cy, r, mood, color):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=max(2, int(r * .12)))
    e = r * .32
    if mood == "happy":
        for sx in (-1, 1):
            d.ellipse((cx + sx * e - r * .08, cy - r * .3, cx + sx * e + r * .08, cy - r * .14), fill=color)
        d.arc((cx - r * .5, cy - r * .35, cx + r * .5, cy + r * .5), 20, 160, fill=color, width=max(2, int(r * .12)))
    else:  # dizzy
        for sx in (-1, 1):
            x0, y0 = cx + sx * e, cy - r * .22
            d.line((x0 - r * .12, y0 - r * .12, x0 + r * .12, y0 + r * .12), fill=color, width=max(2, int(r * .1)))
            d.line((x0 - r * .12, y0 + r * .12, x0 + r * .12, y0 - r * .12), fill=color, width=max(2, int(r * .1)))
        d.arc((cx - r * .4, cy + r * .15, cx + r * .4, cy + r * .6), 200, 340, fill=color, width=max(2, int(r * .1)))


def _sign(d, x0, y0, x1, y1, text, color, k, face=None):
    d.rounded_rectangle((x0, y0, x1, y1), radius=int((y1 - y0) * .12), fill=(250, 250, 252),
                        outline=color, width=int(6 * k))
    w, h = x1 - x0, y1 - y0
    if face:
        _drawn_face(d, x0 + w / 2, y0 + h * .32, h * .2, face, color)
        ty = y0 + h * .72
    else:
        ty = y0 + h / 2
    size = int(h * (0.24 if face else 0.3))
    f = font("title", size)
    while f.getlength(text) > w * .88 and size > 10:
        size -= 2
        f = font("title", size)
    d.text(((x0 + x1) / 2, ty), text, font=f, fill=color if color != WHITE else NAVY, anchor="mm")


@lru_cache(maxsize=256)
def blip_img(size: int, pose: str = "idle", sign: str = "", signs: str = "", hat: bool = False,
             phase: int = 0) -> Image.Image:
    """Blip: a small round glowing pink brain with dot eyes and stubby arms."""
    k = 2
    r = size * k / 2
    W = int(r * 6.2)
    Hh = int(r * 5.2)
    img = Image.new("RGBA", (W, Hh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = W / 2, Hh * .62
    arm_c = (240, 70, 120)
    aw = r * .26

    def arm(ang, bend=None, side=1):
        sx, sy = cx + side * r * .85, cy + r * .15
        _arm(d, sx, sy, ang * side, r * .9, aw, arm_c, (255, 130, 165), None if bend is None else bend * side)

    wave = 18 * math.sin(phase / 8 * 2 * math.pi)
    # feet
    for s in (-1, 1):
        d.ellipse((cx + s * r * .45 - r * .25, cy + r * .82, cx + s * r * .45 + r * .25, cy + r * 1.1), fill=arm_c)
    signs_list = [x for x in signs.split("|") if x] if signs else []
    if pose in ("wave",):
        arm(30, side=-1)
        arm(150 + wave, side=1)
    elif pose == "shrug":
        arm(120, 60, -1)
        arm(120, 60, 1)
    elif pose == "point":
        arm(30, side=-1)
        arm(100, side=1)
    elif pose == "shock":
        arm(160, 230, -1)
        arm(160, 230, 1)
    elif pose in ("sign",) or signs_list:
        arm(165, side=-1)
        arm(165, side=1)
    else:
        arm(25, side=-1)
        arm(25, side=1)
    # body glow + body
    body = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(body)
    bd.ellipse((cx - r * 1.05, cy - r, cx + r * 1.05, cy + r * .95), fill=PINK)
    g = body.filter(ImageFilter.GaussianBlur(r * .35))
    img.alpha_composite(g)
    img.alpha_composite(body)
    # folds
    fold = (225, 60, 112)
    d.line((cx, cy - r * .95, cx, cy + r * .2), fill=fold, width=int(r * .07))
    for (ax, ay, a0, a1) in [(-.5, -.45, 200, 340), (.5, -.45, 200, 340), (-.6, .05, 150, 290),
                             (.6, .05, 250, 30), (-.25, -.15, 180, 330), (.3, -.1, 210, 350)]:
        d.arc((cx + ax * r - r * .35, cy + ay * r - r * .25, cx + ax * r + r * .35, cy + ay * r + r * .25),
              a0, a1, fill=fold, width=int(r * .07))
    d.ellipse((cx - r * .55, cy - r * .8, cx - r * .15, cy - r * .55), fill=(255, 150, 185))   # shine
    # eyes
    ey = cy + r * .18
    for s in (-1, 1):
        ex = cx + s * r * .33
        if pose == "shock":
            d.ellipse((ex - r * .2, ey - r * .24, ex + r * .2, ey + r * .24), fill=WHITE)
            d.ellipse((ex - r * .09, ey - r * .1, ex + r * .09, ey + r * .1), fill=(20, 20, 30))
        else:
            d.ellipse((ex - r * .11, ey - r * .14, ex + r * .11, ey + r * .14), fill=(20, 20, 30))
            d.ellipse((ex - r * .04, ey - r * .1, ex + r * .03, ey - r * .03), fill=WHITE)
    if pose == "shock":
        d.ellipse((cx - r * .1, cy + r * .5, cx + r * .1, cy + r * .72), fill=(120, 20, 50))
    if hat:
        d.chord((cx - r * .8, cy - r * 1.35, cx + r * .8, cy - r * .35), 180, 360, fill=YELLOW)
        d.rounded_rectangle((cx - r * 1.0, cy - r * .9, cx + r * 1.0, cy - r * .74), radius=r * .08, fill=(235, 190, 0))
    if pose == "sign" and sign:
        _sign(d, cx - r * 2.1, cy - r * 2.6, cx + r * 2.1, cy - r * 1.15, sign, NAVY, k)
    if signs_list:
        faces = ["happy", "dizzy"]
        cols = [CYAN, PINK]
        for n, txt in enumerate(signs_list[:2]):
            s = -1 if n == 0 else 1
            x0 = cx + s * r * 1.15 - r * 1.9 if s > 0 else cx - r * 3.05
            x0 = cx - r * 3.05 if s < 0 else cx + r * 1.15
            _sign(d, x0, cy - r * 2.45, x0 + r * 1.9, cy - r * .55, txt, cols[n], k, faces[n])
    return _down(img, k)


# ----------------------------------------------------------------- backgrounds
class Backdrop:
    """Background art for a shot; some parts move a little every frame."""

    def __init__(self, name: str, size: tuple[int, int], seed: int = 1):
        self.name, self.size, self.seed = name, size, seed
        self.W, self.H = size
        self.s = self.H / 1080
        self.rnd = random.Random(seed)
        self.curves: list[np.ndarray] = []
        self.base = self._build(name)

    # neural lines shared by the "inside the brain" looks
    def _neurons(self, img, n=26, alpha=40, area=None):
        d = ImageDraw.Draw(img, "RGBA")
        W, H = self.size
        x0, y0, x1, y1 = area or (0, 0, W, H)
        for _ in range(n):
            p = [(self.rnd.uniform(x0, x1), self.rnd.uniform(y0, y1)) for _ in range(4)]
            ts = np.linspace(0, 1, 60)[:, None]
            pts = ((1 - ts) ** 3 * p[0] + 3 * (1 - ts) ** 2 * ts * p[1] + 3 * (1 - ts) * ts ** 2 * p[2]
                   + ts ** 3 * p[3])
            pts = np.asarray(pts)
            self.curves.append(pts)
            d.line([tuple(q) for q in pts], fill=CYAN + (alpha,), width=max(1, int(2 * self.s)))
            for q in (pts[0], pts[-1]):
                rr = 4 * self.s
                d.ellipse((q[0] - rr, q[1] - rr, q[0] + rr, q[1] + rr), fill=CYAN + (alpha + 40,))

    def _gradient(self, c0, c1, radial=True):
        W, H = self.size
        y, x = np.mgrid[0:H, 0:W]
        if radial:
            r = np.sqrt(((x - W / 2) / W) ** 2 + ((y - H / 2) / H) ** 2) / 0.75
        else:
            r = y / H
        r = np.clip(r, 0, 1)[..., None]
        arr = (np.array(c0) * (1 - r) + np.array(c1) * r).astype(np.uint8)
        return Image.fromarray(arr, "RGB").convert("RGBA")

    def _brain(self, img, cx, cy, w, h, alpha=255):
        """Side-view brain outline with soft pink glow."""
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        th = np.linspace(0, 2 * np.pi, 240)
        rr = 1 + 0.035 * np.sin(9 * th) + 0.02 * np.sin(17 * th + 1)
        xs = cx + np.cos(th) * w / 2 * rr
        ys = cy - np.sin(th) * h / 2 * rr
        ys = np.where(ys > cy + h * .28, cy + h * .28 + (ys - cy - h * .28) * .35, ys)   # flatter base
        poly = list(zip(xs, ys))
        d.polygon(poly, fill=(26, 20, 48, int(alpha * .85)))
        # cerebellum + stem
        d.ellipse((cx + w * .12, cy + h * .2, cx + w * .38, cy + h * .44), fill=(30, 22, 52, alpha))
        d.rounded_rectangle((cx + w * .02, cy + h * .3, cx + w * .12, cy + h * .62), radius=w * .03,
                            fill=(30, 22, 52, alpha))
        g = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(g)
        gd.line(poly + [poly[0]], fill=PINK + (alpha,), width=int(10 * self.s))
        gd.ellipse((cx + w * .12, cy + h * .2, cx + w * .38, cy + h * .44), outline=PINK + (alpha,), width=int(8 * self.s))
        g2 = g.filter(ImageFilter.GaussianBlur(22 * self.s))
        layer.alpha_composite(g2)
        layer.alpha_composite(g2)
        d2 = ImageDraw.Draw(layer)
        d2.line(poly + [poly[0]], fill=(255, 140, 175, alpha), width=int(5 * self.s))
        d2.ellipse((cx + w * .12, cy + h * .2, cx + w * .38, cy + h * .44), outline=(255, 140, 175, alpha),
                   width=int(4 * self.s))
        # gyri
        rnd = random.Random(3)
        for _ in range(14):
            px, py = cx + rnd.uniform(-w * .38, w * .3), cy + rnd.uniform(-h * .36, h * .18)
            rad = rnd.uniform(.05, .11) * w
            a0 = rnd.uniform(0, 360)
            d2.arc((px - rad, py - rad * .6, px + rad, py + rad * .6), a0, a0 + rnd.uniform(100, 200),
                   fill=PINK + (int(alpha * .35),), width=int(4 * self.s))
        img.alpha_composite(layer)
        self._neurons(img, 10, 55, (cx - w * .4, cy - h * .38, cx + w * .3, cy + h * .2))

    def _build(self, name):
        W, H, s = self.W, self.H, self.s
        if name in ("navy", "lab", "graph"):
            img = self._gradient(PANEL, NAVY)
            self._neurons(img, 22 if name == "navy" else 10, 34)
            if name == "lab":
                d = ImageDraw.Draw(img, "RGBA")
                for x in range(0, W, int(60 * s)):
                    d.line((x, 0, x, H), fill=(255, 255, 255, 10))
                for y in range(0, H, int(60 * s)):
                    d.line((0, y, W, y), fill=(255, 255, 255, 10))
            return img
        if name == "brain":
            img = self._gradient(PANEL, NAVY)
            self._neurons(img, 12, 26)
            self._brain(img, W * .5, H * .44, W * .62, H * .78)
            return img
        if name == "plain":                     # thumbnail: clean navy with a cyan glow on the right
            img = self._gradient(PANEL, NAVY)
            g = Image.new("RGBA", self.size, (0, 0, 0, 0))
            ImageDraw.Draw(g).ellipse((W * .62, H * .3, W * .94, H * .9), fill=CYAN + (110,))
            img.alpha_composite(g.filter(ImageFilter.GaussianBlur(90 * s)))
            return img
        if name == "black":
            return Image.new("RGBA", self.size, (4, 6, 12, 255))
        if name in ("backyard", "backyard_blur"):
            img = self._gradient((140, 200, 240), (250, 214, 160), radial=False)
            d = ImageDraw.Draw(img, "RGBA")
            d.ellipse((W * .78, H * .05, W * .9, H * .26), fill=(255, 240, 190, 200))
            d.rectangle((0, H * .62, W, H), fill=(120, 186, 96))
            d.rectangle((0, H * .62, W, H * .66), fill=(104, 168, 84))
            for x in range(0, W, int(46 * s)):            # fence
                d.rectangle((x + 4 * s, H * .44, x + 38 * s, H * .63), fill=(196, 150, 104))
                d.polygon([(x + 4 * s, H * .44), (x + 21 * s, H * .42), (x + 38 * s, H * .44)], fill=(196, 150, 104))
            d.rectangle((0, H * .48, W, H * .5), fill=(170, 126, 86))
            d.rectangle((0, H * .57, W, H * .59), fill=(170, 126, 86))
            # string lights
            pts = [(x, H * .1 + H * .08 * math.sin(math.pi * (x / W * 2 % 1))) for x in np.linspace(0, W, 80)]
            d.line(pts, fill=(60, 50, 40, 220), width=max(2, int(3 * s)))
            self.bulbs = pts[::4]
            # grill
            gx, gy = W * .16, H * .6
            d.line((gx - 40 * s, gy + 10 * s, gx - 60 * s, gy + 120 * s), fill=(40, 40, 46), width=int(8 * s))
            d.line((gx + 40 * s, gy + 10 * s, gx + 60 * s, gy + 120 * s), fill=(40, 40, 46), width=int(8 * s))
            d.chord((gx - 90 * s, gy - 70 * s, gx + 90 * s, gy + 60 * s), 0, 180, fill=(34, 34, 40))
            d.chord((gx - 90 * s, gy - 110 * s, gx + 90 * s, gy - 10 * s), 180, 360, fill=(52, 52, 60))
            self.smoke_at = (gx, gy - 110 * s)
            # picnic table
            tx, ty = W * .76, H * .66
            d.rectangle((tx - 170 * s, ty - 20 * s, tx + 170 * s, ty + 4 * s), fill=(150, 96, 56))
            for sx in (-1, 1):
                d.line((tx + sx * 130 * s, ty, tx + sx * 160 * s, ty + 110 * s), fill=(130, 82, 46), width=int(12 * s))
            d.ellipse((tx - 60 * s, ty - 38 * s, tx - 10 * s, ty - 18 * s), fill=(240, 240, 240))
            d.ellipse((tx + 30 * s, ty - 40 * s, tx + 80 * s, ty - 20 * s), fill=(220, 70, 60))
            # background guests (small, softer)
            for n, gxp in enumerate((.3, .42, .62, .88, .53)):
                p = person_img("guest", ["stand", "plate", "stand", "wave", "stand"][n], int(250 * s), 2, n + 3)
                p = p.copy()
                p.putalpha(p.getchannel("A").point(lambda v: int(v * .75)))
                img.alpha_composite(p, (int(W * gxp - p.width / 2), int(H * .7 - p.height)))
            if name == "backyard_blur":
                img = img.filter(ImageFilter.GaussianBlur(14 * s))
                dark = Image.new("RGBA", self.size, NAVY + (150,))
                img.alpha_composite(dark)
            return img
        if name == "coffee":
            img = self._gradient((96, 66, 48), (60, 40, 30), radial=False)
            d = ImageDraw.Draw(img, "RGBA")
            d.rectangle((0, H * .62, W, H), fill=(140, 96, 64))
            d.rectangle((0, H * .62, W, H * .66), fill=(170, 120, 80))
            d.rounded_rectangle((W * .62, H * .1, W * .92, H * .42), radius=12 * s, fill=(30, 30, 30))
            for n in range(5):
                d.line((W * .65, H * (.16 + n * .05), W * (.8 + .03 * (n % 2)), H * (.16 + n * .05)),
                       fill=(230, 230, 230, 120), width=int(5 * s))
            for n, xx in enumerate((.12, .2, .28)):
                d.rounded_rectangle((W * xx, H * .54, W * xx + 50 * s, H * .62), radius=8 * s, fill=(245, 245, 245))
            return img
        if name == "sepia":
            img = self._gradient((120, 88, 56), (70, 48, 30), radial=True)
            d = ImageDraw.Draw(img, "RGBA")
            d.rectangle((0, H * .55, W, H), fill=(110, 74, 44))
            for y in range(int(H * .55), H, int(18 * s)):
                d.line((0, y, W, y + 6 * s), fill=(90, 60, 36, 120), width=2)
            return img
        if name == "film":
            img = self._gradient((96, 96, 96), (50, 50, 50))
            return img
        if name == "crowd":
            img = self._gradient((60, 66, 90), (36, 40, 60))
            d = ImageDraw.Draw(img, "RGBA")
            for x in range(0, W, int(90 * s)):
                d.line((x, 0, x, H), fill=(255, 255, 255, 12))
            for y in range(0, H, int(90 * s)):
                d.line((0, y, W, y), fill=(255, 255, 255, 12))
            return img
        return self._build("navy")

    def frame(self, t: float) -> Image.Image:
        img = self.base.copy()
        W, H, s = self.W, self.H, self.s
        if self.curves and self.name in ("navy", "brain", "lab", "graph"):
            d = ImageDraw.Draw(img, "RGBA")
            for n, pts in enumerate(self.curves[:14]):
                p = ((t * 0.18 + n * 0.37) % 1.4)
                if p > 1:
                    continue
                q = pts[int(p * (len(pts) - 1))]
                for rr, a in ((10 * s, 40), (5 * s, 120), (2.5 * s, 255)):
                    d.ellipse((q[0] - rr, q[1] - rr, q[0] + rr, q[1] + rr), fill=CYAN + (a,))
        if self.name == "backyard":
            d = ImageDraw.Draw(img, "RGBA")
            for n, (x, y) in enumerate(getattr(self, "bulbs", [])):
                tw = 0.75 + 0.25 * math.sin(t * 3 + n * 1.7)
                for rr, a in ((14 * s, int(60 * tw)), (6 * s, int(255 * tw))):
                    d.ellipse((x - rr, y + 8 * s - rr, x + rr, y + 8 * s + rr), fill=(255, 220, 120, a))
            sx, sy = getattr(self, "smoke_at", (0, 0))
            for n in range(6):
                p = (t * 0.25 + n / 6) % 1
                rr = (18 + 40 * p) * s
                x = sx + math.sin(p * 6 + n) * 20 * s
                y = sy - p * 260 * s
                d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(230, 230, 230, int(90 * (1 - p))))
        return img


# ----------------------------------------------------------------- timing
class Shot:
    def __init__(self, raw: dict, start: float, end: float, speech: tuple[float, float], index: int):
        self.raw, self.start, self.end, self.i = raw, start, end, index
        self.dur = end - start
        self.text = str(raw.get("text", "") or "")
        self.words = self.text.split()
        self.s0, self.s1 = speech
        total = max(1, sum(len(w) + 1 for w in self.words))
        acc, self.word_frac = 0, []
        for w in self.words:
            self.word_frac.append(acc / total)
            acc += len(w) + 1

    def T(self, spec, default=0.0) -> float:
        if spec is None:
            return default
        if isinstance(spec, (int, float)):
            return float(spec)
        s = str(spec).strip()
        m = __import__("re").match(r"^(w\d+|e|p[\d.]+)([+\-]\d[\d.]*)$", s)
        if m and not s.startswith("e"):
            return self.T(m.group(1), default) + float(m.group(2))
        if s.startswith("w"):
            idx = int(float(s[1:]))
            if not self.words:
                return default
            idx = max(0, min(idx, len(self.words) - 1))
            return self.s0 + (self.s1 - self.s0) * self.word_frac[idx]
        if s.startswith("e"):
            return self.dur + float(s[1:] or 0)
        if s.startswith("p"):
            return self.dur * float(s[1:])
        return float(s)


# ----------------------------------------------------------------- elements
def _paste(frame: Image.Image, img: Image.Image, cx: float, cy: float, scale=1.0, alpha=1.0, rot=0.0):
    if alpha <= 0.01 or scale <= 0.01:
        return
    if abs(scale - 1) > 0.003:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BILINEAR)
    if rot:
        img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 0.995:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
    x, y = int(cx - img.width / 2), int(cy - img.height / 2)
    W, H = frame.size
    if x >= W or y >= H or x + img.width <= 0 or y + img.height <= 0:
        return
    l, t = max(0, -x), max(0, -y)
    r, b = min(img.width, W - x), min(img.height, H - y)
    frame.alpha_composite(img.crop((l, t, r, b)), (x + l, y + t))


class El:
    """Base element: a sprite that pops in, can move along a path, shake, dissolve and leave."""
    animated = False

    def __init__(self, d: dict, shot: Shot, size):
        self.d, self.shot = d, shot
        self.W, self.H = size
        self.s = self.H / 1080
        self.t0 = shot.T(d.get("at"), 0.0)
        self.t1 = shot.T(d.get("until"), 1e9)
        self.x, self.y = float(d.get("x", .5)), float(d.get("y", .5))
        self.path = [(shot.T(k[0]), float(k[1]), float(k[2])) for k in d.get("path", [])]
        self.dis = shot.T(d["dissolve"]) if "dissolve" in d else None
        sh = d.get("shake")
        self.shake = (shot.T(sh[0]), shot.T(sh[1])) if sh else None
        self.scale = float(d.get("scale", 1.0))
        self.rot = float(d.get("rot", 0))
        self.pop = d.get("pop", "pop")
        self.seed = abs(hash(json.dumps(d, sort_keys=True, default=str))) % 10000
        self._parts = None

    # --- motion helpers
    def pos(self, t):
        x, y = self.x, self.y
        if self.path:
            pts = [(self.t0, self.x, self.y)] + self.path
            if t <= pts[0][0]:
                x, y = pts[0][1], pts[0][2]
            elif t >= pts[-1][0]:
                x, y = pts[-1][1], pts[-1][2]
            else:
                for (ta, xa, ya), (tb, xb, yb) in zip(pts, pts[1:]):
                    if ta <= t <= tb:
                        p = _ease((t - ta) / max(tb - ta, 1e-3))
                        x, y = _lerp(xa, xb, p), _lerp(ya, yb, p)
                        break
        px, py = x * self.W, y * self.H
        if self.shake and self.shake[0] <= t <= self.shake[1]:
            px += math.sin(t * 60) * 8 * self.s
            py += math.cos(t * 47) * 5 * self.s
        return px, py

    def fade(self, t):
        if t < self.t0:
            return 0.0, 0.8
        p = (t - self.t0) / 0.3
        if self.pop == "none":
            a, sc = 1.0, 1.0
        elif self.pop == "fade":
            a, sc = min(1, p), 1.0
        else:
            a, sc = min(1, p), (0.8 + 0.2 * _back(min(1, p * 0.9)) if self.pop == "pop" else 0.8 + 0.2 * _out(p))
        if t > self.t1:
            a *= max(0.0, 1 - (t - self.t1) / 0.3)
        if self.dis is not None and t > self.dis:
            a *= max(0.0, 1 - (t - self.dis) / 0.7)
        return a, sc

    def sprite(self, t) -> Image.Image | None:
        return None

    def draw(self, frame, t):
        a, sc = self.fade(t)
        if a > 0:
            img = self.sprite(t)
            if img is not None:
                cx, cy = self.pos(t)
                _paste(frame, img, cx, cy, sc * self.scale, a, self.rot)
        self.particles(frame, t)

    def particles(self, frame, t):
        if self.dis is None or t < self.dis or t > self.dis + 1.8:
            return
        if self._parts is None:
            img = self.sprite(self.dis)
            if img is None:
                self._parts = []
                return
            rnd = random.Random(self.seed)
            w, h = img.width * self.scale, img.height * self.scale
            cx, cy = self.pos(self.dis)
            self._parts = [(cx + rnd.uniform(-w * .4, w * .4), cy + rnd.uniform(-h * .3, h * .3),
                            rnd.uniform(-60, 60), rnd.uniform(-160, -50), rnd.uniform(3, 8), rnd.uniform(0, .5))
                           for _ in range(70)]
        d = ImageDraw.Draw(frame, "RGBA")
        dt = t - self.dis
        for (x, y, vx, vy, r, delay) in self._parts:
            q = dt - delay
            if q < 0 or q > 1.3:
                continue
            a = int(255 * (1 - q / 1.3))
            px, py = x + vx * q * self.s, y + vy * q * self.s
            rr = r * self.s * (1 - q / 2)
            d.ellipse((px - rr, py - rr, px + rr, py + rr), fill=PINK + (a,))

    def sfx(self) -> list[tuple[str, float, float]]:
        ev = []
        if self.d.get("sfx"):
            ev.append((self.d["sfx"], self.t0, 1.0))
        if self.dis is not None and self.d.get("dissolve_sfx", "shimmer"):
            ev.append((self.d.get("dissolve_sfx", "shimmer"), self.dis, 1.0))
        for spec in self.d.get("sfx_at", []):
            ev.append((spec[1], self.shot.T(spec[0]), float(spec[2]) if len(spec) > 2 else 1.0))
        return ev


class TextEl(El):
    def sprite(self, t):
        d = self.d
        return _text_cached(str(d.get("text", "")), int(d.get("size", 64) * self.s), str(d.get("color", "white")),
                            d.get("font", "title"), int(d.get("max_w", 1500) * self.s),
                            str(d.get("box", "")), str(d.get("glow", "")))


@lru_cache(maxsize=512)
def _text_cached(text, size, color, kind, max_w, box, glw):
    fill = col(color)
    if box:
        img = block_img(text, size, fill if color != "white" or box != "yellow" else (15, 15, 15), kind, max_w,
                        box=col(box))
    else:
        img = block_img(text, size, fill, kind, max_w)
    if glw:
        img = glow(img, col(glw), max(4, size // 6), 0.6)
    return img


class TitleEl(El):
    """'REASON #1' in yellow, then the subtitle in white below it."""
    animated = True

    def draw(self, frame, t):
        d = self.d
        a, sc = self.fade(t)
        if a <= 0:
            return
        cx, cy = self.pos(t)
        top = _text_cached(str(d.get("top", "")), int(d.get("size", 120) * self.s), "yellow", "title",
                           int(1700 * self.s), "", "yellow")
        _paste(frame, top, cx, cy - 70 * self.s, sc, a)
        if d.get("sub"):
            t2 = self.t0 + 0.55
            if t >= t2:
                a2 = min(1, (t - t2) / 0.3) * a
                sc2 = 0.85 + 0.15 * _out((t - t2) / 0.3)
                sub = _text_cached(str(d["sub"]), int(d.get("sub_size", 78) * self.s), "white", "title",
                                   int(1600 * self.s), "", "")
                _paste(frame, sub, cx, cy + 70 * self.s + sub.height * 0.15, sc2, a2)
        # a thin cyan underline that draws itself
        p = _ease((t - self.t0 - .2) / .6)
        if p > 0:
            dr = ImageDraw.Draw(frame, "RGBA")
            w = 520 * self.s * p
            yy = cy + 10 * self.s
            dr.line((cx - w / 2, yy, cx + w / 2, yy), fill=CYAN + (int(220 * a),), width=int(5 * self.s))


class SourceEl(El):
    def sprite(self, t):
        return _text_cached(str(self.d.get("text", "")), int(30 * self.s), "grey", "body", int(900 * self.s), "", "")

    def pos(self, t):
        img = self.sprite(t)
        return 50 * self.s + img.width / 2, 60 * self.s + img.height / 2


class StickerEl(El):
    def sprite(self, t):
        d = self.d
        size = int(d.get("size", 170) * self.s)
        prog = 1.0
        if "write" in d:
            w0 = self.shot.T(d["write"])
            prog = max(0.0, min(1.0, (t - w0) / 0.8))
            if t < w0:
                return sticker_img(str(d.get("name", "")), size, True, bool(d.get("q")))
            return sticker_img(str(d.get("name", "")), size, False, False, round(prog * 8) / 8)
        blank = bool(d.get("blank"))
        if self.dis is not None and t >= self.dis + 0.2 and d.get("after_q"):
            return sticker_img("", size, True, True)
        return sticker_img(str(d.get("name", "")), size, blank, bool(d.get("q")))

    def fade(self, t):
        # an "after_q" sticker keeps the blank tag after its name dissolves
        a, sc = super().fade(t)
        if self.dis is not None and self.d.get("after_q") and t > self.dis:
            base = El.fade(self, self.dis)
            a = base[0] if t <= self.t1 else a
            if t > self.dis + 0.2:
                a = 1.0 if t <= self.t1 else max(0, 1 - (t - self.t1) / .3)
        return a, sc


class PersonEl(El):
    def sprite(self, t):
        d = self.d
        pose = d.get("pose", "stand")
        for sw in d.get("poses", []):           # [[time, pose], ...]
            if t >= self.shot.T(sw[0]):
                pose = sw[1]
        moving = False
        if self.path:
            for (ta, _xa, _ya), (tb, _xb, _yb) in zip([(self.t0, 0, 0)] + self.path, self.path):
                if ta <= t <= tb:
                    moving = True
        if moving and d.get("walk", True):
            pose = "walk"
        phase = int(t * 10) % 8 if pose in ("wave", "walk") else 0
        img = person_img(d.get("who", "everyman"), pose, int(d.get("h", 460) * self.s), phase,
                         int(d.get("seed", 0)))
        if d.get("flip"):
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if d.get("silhouette"):
            sil = Image.new("RGBA", img.size, (0, 0, 0, 0))
            sil.paste((60, 70, 110, 255), (0, 0), img)
            img = sil
        return img


class JugglerEl(PersonEl):
    """A person juggling five colorful jelly beans."""
    animated = True

    def draw(self, frame, t):
        super().draw(frame, t)
        a, _ = self.fade(t)
        if a <= 0:
            return
        cx, cy = self.pos(t)
        h = float(self.d.get("h", 460)) * self.s
        dr = ImageDraw.Draw(frame, "RGBA")
        cols = [PINK, YELLOW, CYAN, (140, 230, 90), (190, 120, 255)]
        for k, c in enumerate(cols):
            ph = t * 2.2 + k / 5
            u = ph % 1
            side = 1 if int(ph) % 2 else -1
            x = cx + side * (u - .5) * h * .5
            y = cy - h * .34 - math.sin(u * math.pi) * h * .38
            r = 13 * self.s
            dr.ellipse((x - r * 1.3, y - r, x + r * 1.3, y + r), fill=c + (int(255 * a),))

    def sfx(self):
        ev = super().sfx()
        ev += [("plink", self.t0 + .3 + k * .22, 0.8) for k in range(5)]
        return ev


class SpinnerEl(El):
    """A small loading spinner."""
    animated = True

    def draw(self, frame, t):
        a, sc = self.fade(t)
        if a <= 0:
            return
        cx, cy = self.pos(t)
        r = float(self.d.get("r", 40)) * self.s * sc
        dr = ImageDraw.Draw(frame, "RGBA")
        start = (t * 360) % 360
        dr.arc((cx - r, cy - r, cx + r, cy + r), start, start + 270, fill=CYAN + (int(255 * a),),
               width=int(9 * self.s))

    def sfx(self):
        return super().sfx() + [("loading", self.t0, 1.0)]


class BlipEl(El):
    def sprite(self, t):
        d = self.d
        pose = d.get("pose", "idle")
        for sw in d.get("poses", []):
            if t >= self.shot.T(sw[0]):
                pose = sw[1]
        phase = int(t * 10) % 8
        return blip_img(int(d.get("size", 170) * self.s), pose, str(d.get("sign", "")),
                        "|".join(d.get("signs", [])), bool(d.get("hat")), phase if pose == "wave" else 0)

    def pos(self, t):
        x, y = super().pos(t)
        return x, y + math.sin(t * 2.4) * 6 * self.s


class IconEl(El):
    def sprite(self, t):
        d = self.d
        return _icon_cached(str(d.get("emoji", "❓")), int(d.get("size", 120) * self.s), str(d.get("label", "")),
                            str(d.get("label_color", "white")), str(d.get("ring", "")), str(d.get("tint", "")))


@lru_cache(maxsize=512)
def _icon_cached(emoji, size, label, label_color, ring, tint):
    em = emoji_image(emoji, size).copy()
    if tint == "grey":
        g = em.convert("LA").convert("RGBA")
        g.putalpha(em.getchannel("A").point(lambda v: int(v * .6)))
        em = g
    if ring:
        pad = int(size * .3)
        base = Image.new("RGBA", (em.width + 2 * pad, em.height + 2 * pad), (0, 0, 0, 0))
        dd = ImageDraw.Draw(base)
        dd.ellipse((4, 4, base.width - 4, base.height - 4), fill=PANEL + (235,), outline=col(ring),
                   width=max(3, size // 22))
        base.alpha_composite(em, (pad, pad))
        em = base
    if not label:
        return em
    lab = block_img(label, max(16, size // 3), col(label_color), "body", size * 4)
    out = Image.new("RGBA", (max(em.width, lab.width), em.height + lab.height), (0, 0, 0, 0))
    out.alpha_composite(em, ((out.width - em.width) // 2, 0))
    out.alpha_composite(lab, ((out.width - lab.width) // 2, em.height - lab.height // 6))
    return out


class BubbleEl(El):
    """A thought bubble (cloud) or speech bubble with optional text."""

    def sprite(self, t):
        d = self.d
        return _bubble_cached(int(d.get("w", 520) * self.s), int(d.get("h", 340) * self.s), d.get("kind", "thought"),
                              str(d.get("text", "")), int(d.get("size", 54) * self.s), d.get("tail", "left"))


@lru_cache(maxsize=128)
def _bubble_cached(w, h, kind, text, size, tail):
    k = 2
    pad = int(h * .45)
    img, d = _ss(w + 2 * pad, h + 2 * pad, k)
    fill, edge = (250, 250, 252, 255), (200, 205, 220, 255)
    ox, oy = pad * k, pad * k
    W, H = w * k, h * k
    if kind == "thought":
        rnd = random.Random(w + h)
        for n in range(14):
            a = n / 14 * 2 * math.pi
            cx, cy = ox + W / 2 + math.cos(a) * W * .42, oy + H / 2 + math.sin(a) * H * .38
            r = rnd.uniform(.16, .22) * min(W, H) * 1.1
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)
        d.ellipse((ox + W * .06, oy + H * .08, ox + W * .94, oy + H * .92), fill=fill)
        sx = ox + W * (.2 if tail == "left" else .8)
        for n, r in enumerate((.075, .05, .03)):
            rr = r * H
            yy = oy + H + (n + 1) * H * .13
            xx = sx + (-1 if tail == "left" else 1) * n * W * .04
            d.ellipse((xx - rr, yy - rr, xx + rr, yy + rr), fill=fill)
    else:
        d.rounded_rectangle((ox, oy, ox + W, oy + H), radius=H * .3, fill=fill, outline=edge, width=3 * k)
        sx = ox + W * (.25 if tail == "left" else .75)
        d.polygon([(sx - W * .06, oy + H - 2), (sx + W * .06, oy + H - 2),
                   (sx + (-1 if tail == "left" else 1) * W * .12, oy + H + H * .3)], fill=fill)
    if text:
        f = font("body", size * k)
        lines = wrap_lines(text, size * k, int(W * .82), "body")
        lh = size * k * 1.2
        y0 = oy + H / 2 - lh * (len(lines) - 1) / 2
        for n, ln in enumerate(lines):
            d.text((ox + W / 2, y0 + n * lh), ln, font=f, fill=NAVY, anchor="mm")
    img = _down(img, k)
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, 90), (0, 6), img)
    sh = sh.filter(ImageFilter.GaussianBlur(8))
    sh.alpha_composite(img)
    return sh


class MarkEl(El):
    """Big check (yellow) or cross (pink)."""

    def sprite(self, t):
        return _mark_cached(self.d.get("kind", "check"), int(self.d.get("size", 160) * self.s))


@lru_cache(maxsize=32)
def _mark_cached(kind, size):
    k = 2
    img, d = _ss(size, size, k)
    S = size * k
    w = int(S * .16)
    if kind == "check":
        d.line((S * .15, S * .55, S * .4, S * .8, S * .88, S * .2), fill=YELLOW, width=w, joint="curve")
        c = YELLOW
    else:
        d.line((S * .2, S * .2, S * .8, S * .8), fill=PINK, width=w)
        d.line((S * .8, S * .2, S * .2, S * .8), fill=PINK, width=w)
        c = PINK
    return glow(_down(img, k), c, max(4, size // 10), 0.6)


class PillEl(El):
    """Small rounded label tag (e.g. NAME / JOB / BAKER)."""

    def sprite(self, t):
        d = self.d
        return _pill_cached(str(d.get("text", "")), int(d.get("size", 40) * self.s), str(d.get("color", "cyan")),
                            str(d.get("fg", "navy")), str(d.get("icon", "")))


@lru_cache(maxsize=256)
def _pill_cached(text, size, color, fg, icon):
    f = font("title", size)
    tw = int(f.getlength(text))
    ic = emoji_image(icon, int(size * 1.1)) if icon else None
    iw = ic.width if ic else 0
    w, h = tw + int(size * 1.2) + iw, int(size * 1.7)
    img = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((10, 10, 10 + w, 10 + h), radius=h // 2, fill=col(color))
    if ic:
        img.alpha_composite(ic, (10 + int(size * .35), 10 + (h - ic.height) // 2))
    d.text((10 + iw + int(size * .6) + tw / 2, 10 + h / 2), text, font=f, fill=col(fg), anchor="mm")
    return img


class CardEl(El):
    """A rounded panel card with an emoji and/or text (stat cards, inbox cards, step cards)."""

    def sprite(self, t):
        d = self.d
        return _card_cached(str(d.get("text", "")), str(d.get("emoji", "")), int(d.get("w", 360) * self.s),
                            int(d.get("h", 200) * self.s), str(d.get("color", "cyan")), int(d.get("size", 40) * self.s),
                            str(d.get("face", "")), str(d.get("fill", "panel")))


def _face_card(size, seed):
    """Simple illustrated face (no real person): head, hair, shoulders."""
    rnd = random.Random(seed)
    img, d = _ss(size, size, 2)
    S = size * 2
    d.rectangle((0, 0, S, S), fill=(56, 66, 100))
    skin = rnd.choice(SKINS)
    hair = rnd.choice([(40, 30, 20), (90, 60, 30), (20, 20, 20), (150, 110, 60), (176, 74, 40)])
    top = rnd.choice([(214, 120, 90), (90, 140, 214), (120, 190, 110), (200, 160, 80), (170, 110, 170)])
    d.ellipse((S * .18, S * .72, S * .82, S * 1.3), fill=top)
    d.ellipse((S * .32, S * .22, S * .68, S * .66), fill=skin)
    d.chord((S * .3, S * .18, S * .7, S * .52), 180, 360, fill=hair)
    for sx in (.43, .57):
        d.ellipse((S * sx - S * .02, S * .42, S * sx + S * .02, S * .46), fill=(30, 30, 40))
    d.arc((S * .44, S * .48, S * .56, S * .56), 20, 160, fill=(120, 60, 60), width=int(S * .015))
    return _down(img, 2)


@lru_cache(maxsize=256)
def _card_cached(text, emoji, w, h, color, size, face, fill):
    img = Image.new("RGBA", (w + 24, h + 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fc = PANEL + (245,) if fill == "panel" else col(fill) + (255,)
    d.rounded_rectangle((12, 12, 12 + w, 12 + h), radius=int(min(w, h) * .14), fill=fc, outline=col(color),
                        width=max(3, int(h * .025)))
    y_text = 12 + h / 2
    if face:
        fimg = _face_card(int(min(w, h) * .62), int(face))
        img.alpha_composite(fimg, (12 + (w - fimg.width) // 2, 12 + int(h * .08)))
        y_text = 12 + h * .86
    elif emoji:
        es = int(min(w, h) * (.42 if text else .6))
        em = emoji_image(emoji, es)
        ey = 12 + int(h * (.08 if text else (h - em.height) / h / 2))
        img.alpha_composite(em, (12 + (w - em.width) // 2, ey))
        y_text = 12 + h * .8
    if text:
        f = font("title", size)
        lines = wrap_lines(text, size, int(w * .88))
        lh = size * 1.1
        y0 = y_text - lh * (len(lines) - 1) / 2
        for n, ln in enumerate(lines):
            d.text((12 + w / 2, y0 + n * lh), ln, font=f, fill=col(color) if color != "cyan" else WHITE, anchor="mm")
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, 120), (0, 6), img)
    sh = sh.filter(ImageFilter.GaussianBlur(8))
    sh.alpha_composite(img)
    return sh


class LineEl(El):
    """A line between two points that draws itself (cyan by default); can pulse."""
    animated = True

    def draw(self, frame, t):
        a, _ = self.fade(t)
        if a <= 0:
            return
        d = self.d
        x0, y0, x1, y1 = [float(v) for v in d["pts"]]
        p = _ease((t - self.t0) / float(d.get("grow", .4)))
        xa, ya = x0 * self.W, y0 * self.H
        xb, yb = _lerp(xa, x1 * self.W, p), _lerp(ya, y1 * self.H, p)
        c = col(d.get("color", "cyan"))
        width = int(float(d.get("width", 5)) * self.s)
        if d.get("flicker"):
            a *= 0.55 + 0.45 * abs(math.sin(t * 13 + self.seed))
        layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        dl = ImageDraw.Draw(layer)
        dl.line((xa, ya, xb, yb), fill=c + (int(255 * a),), width=width)
        if d.get("glow", True) and width >= 4:
            g = layer.filter(ImageFilter.GaussianBlur(width * 1.4))
            frame.alpha_composite(g)
        frame.alpha_composite(layer)
        if "pulse" in d:
            tp = self.shot.T(d["pulse"])
            stop = float(d.get("stop", 1.0))
            q = (t - tp) / float(d.get("pulse_len", 1.0))
            if 0 <= q <= 1:
                q = min(q, stop) if q < 1 else stop
                px, py = _lerp(xa, x1 * self.W, q), _lerp(ya, y1 * self.H, q)
                dd = ImageDraw.Draw(frame, "RGBA")
                for rr, al in ((22 * self.s, 60), (11 * self.s, 140), (5 * self.s, 255)):
                    dd.ellipse((px - rr, py - rr, px + rr, py + rr), fill=(255, 255, 255, al))


class GraphEl(El):
    """The forgetting curve, drawing itself; optional bumps that lift it back up."""
    animated = True

    def curve(self, u, t):
        y = 0.12 + 0.88 * math.exp(-u * 5.5) * (1 - 0.0) + 0.0
        bumps = [self.shot.T(b) for b in self.d.get("bumps", [])]
        lift = 0
        for n, tb in enumerate(bumps):
            if t >= tb:
                k = min(1, (t - tb) / .6)
                ub = [0.3, 0.6][n % 2]
                if u >= ub:
                    lift += k * (0.55 - 0.1 * n) * math.exp(-(u - ub) * (2.0 - n * 1.2))
        return min(0.98, y + lift)

    def draw(self, frame, t):
        a, _ = self.fade(t)
        if a <= 0:
            return
        d = self.d
        gx, gy = float(d.get("x", .5)) * self.W, float(d.get("y", .46)) * self.H
        gw, gh = float(d.get("w", .62)) * self.W, float(d.get("h", .5)) * self.H
        x0, y0 = gx - gw / 2, gy + gh / 2
        dr = ImageDraw.Draw(frame, "RGBA")
        A = int(255 * a)
        dr.line((x0, y0 - gh, x0, y0), fill=WHITE + (A,), width=int(4 * self.s))
        dr.line((x0, y0, x0 + gw, y0), fill=WHITE + (A,), width=int(4 * self.s))
        fy = font("body", int(30 * self.s))
        lab = _text_cached("REMEMBERED", int(30 * self.s), "white", "body", 800, "", "").rotate(90, expand=True)
        _paste(frame, lab, x0 - 45 * self.s, y0 - gh / 2, 1, a)
        ticks = d.get("ticks", ["20 MIN", "1 HOUR", "1 DAY", "1 WEEK"])
        for n, tk in enumerate(ticks):
            tx = x0 + gw * (0.12 + n * 0.28)
            dr.text((tx, y0 + 30 * self.s), tk, font=fy, fill=WHITE + (A,), anchor="mm")
        p = _ease((t - self.t0 - 0.2) / float(d.get("draw", 2.0)))
        if p <= 0:
            return
        pts = []
        for n in range(121):
            u = n / 120
            if u > p:
                break
            pts.append((x0 + gw * u, y0 - gh * self.curve(u, t)))
        if len(pts) > 1:
            layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).line(pts, fill=YELLOW + (A,), width=int(9 * self.s), joint="curve")
            frame.alpha_composite(layer.filter(ImageFilter.GaussianBlur(10 * self.s)))
            frame.alpha_composite(layer)
        if d.get("dot") and p > 0.3:
            u = 0.32
            px, py = x0 + gw * u, y0 - gh * self.curve(u, t)
            rr = 16 * self.s
            dr.ellipse((px - rr, py - rr, px + rr, py + rr), fill=PINK + (A,))
            lab = _text_cached(str(d["dot"]), int(40 * self.s), "pink", "title", int(700 * self.s), "", "")
            _paste(frame, lab, px + lab.width / 2 + 24 * self.s, py - 40 * self.s, 1, a * min(1, (p - .3) / .2))
        if d.get("slider"):
            ts = self.shot.T(d["slider"])
            q = (t - ts) / 2.2
            if 0 <= q <= 1:
                u = _ease(q) * 0.95
                px, py = x0 + gw * u, y0 - gh * self.curve(u, t)
                st = sticker_img(str(d.get("slider_name", "Jessica")), int(110 * self.s))
                _paste(frame, st, px, py - 50 * self.s, 1, a * (1 - max(0, q - .55) / .45), -25 * (1 - u))
                ddr = ImageDraw.Draw(frame, "RGBA")
                rnd = random.Random(int(t * 30))
                for _ in range(int(25 * q)):
                    rx, ry = px + rnd.uniform(-90, 90) * self.s, py - 50 * self.s + rnd.uniform(-60, 40) * self.s
                    rr = rnd.uniform(3, 7) * self.s
                    ddr.ellipse((rx - rr, ry - rr, rx + rr, ry + rr), fill=PINK + (int(200 * q),))


class RingEl(El):
    """A countdown ring that fills over 'len' seconds, with an optional label."""
    animated = True

    def draw(self, frame, t):
        a, sc = self.fade(t)
        if a <= 0:
            return
        d = self.d
        cx, cy = self.pos(t)
        r = float(d.get("r", 120)) * self.s * sc
        p = min(1, max(0, (t - self.t0) / float(d.get("len", 3.0))))
        c = col(d.get("color", "yellow"))
        dr = ImageDraw.Draw(frame, "RGBA")
        wd = int(14 * self.s)
        dr.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, int(50 * a)), width=wd)
        if p > 0:
            dr.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * p, fill=c + (int(255 * a),), width=wd)
        if d.get("label"):
            lab = _text_cached(str(d["label"]), int(d.get("size", 44) * self.s), str(d.get("color", "yellow")),
                               "title", int(900 * self.s), "", "")
            _paste(frame, lab, cx, cy + r + 40 * self.s, 1, a)
        if d.get("count"):
            n = int(d["count"]) - int(p * int(d["count"]))
            if p < 1:
                num = _text_cached(str(max(n, 1)), int(110 * self.s), "white", "title", 400, "", "")
                _paste(frame, num, cx, cy, 1, a)

    def sfx(self):
        ev = super().sfx()
        if self.d.get("ticks"):
            L = float(self.d.get("len", 3.0))
            n = int(self.d.get("count", 3))
            ev += [("tick", self.t0 + L * k / n, 1.0) for k in range(n)]
        return ev


class ChainEl(El):
    """Glowing chain links built left to right, a pulse runs along and stalls at the last one."""
    animated = True

    def draw(self, frame, t):
        d = self.d
        a, _ = self.fade(t)
        if a <= 0:
            return
        links = d.get("links", [])
        n = len(links)
        cx, cy = self.pos(t)
        span = float(d.get("w", .72)) * self.W
        xs = [cx - span / 2 + span * (k + .5) / n for k in range(n)]
        lw, lh = span / n * .78, 160 * self.s
        dr = ImageDraw.Draw(frame, "RGBA")
        times = [self.shot.T(l.get("at", self.t0)) for l in links]
        pulse = self.shot.T(d["pulse"]) if "pulse" in d else None
        crack = self.shot.T(d["crack"]) if "crack" in d else None
        for k, (lk, x, tk) in enumerate(zip(links, xs, times)):
            if t < tk:
                continue
            q = min(1, (t - tk) / .3)
            weak = bool(lk.get("weak"))
            c = CYAN if not weak else (120, 170, 190)
            width = int((12 if not weak else 5) * self.s)
            sc = 0.8 + 0.2 * _back(q)
            w2, h2 = lw / 2 * sc, lh / 2 * sc
            A = int(255 * a * q * (0.6 if weak else 1))
            layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            dl = ImageDraw.Draw(layer)
            dl.rounded_rectangle((x - w2, cy - h2, x + w2, cy + h2), radius=h2, outline=c + (A,), width=width)
            if k:
                dl.line((xs[k - 1] + lw / 2 * .9, cy, x - w2, cy), fill=c + (A,), width=width)
            frame.alpha_composite(layer.filter(ImageFilter.GaussianBlur(10 * self.s)))
            frame.alpha_composite(layer)
            if crack is not None and weak and t > crack:
                dr.line((x - w2 * .1, cy - h2, x + w2 * .15, cy - h2 * .1, x - w2 * .1, cy + h2 * .3),
                        fill=(255, 255, 255, 220), width=int(4 * self.s))
            if lk.get("emoji"):
                em = emoji_image(lk["emoji"], int(90 * self.s * sc))
                _paste(frame, em, x, cy, 1, a * q)
            if lk.get("emoji2"):
                em = emoji_image(lk["emoji2"], int(56 * self.s * sc))
                _paste(frame, em, x + 50 * self.s, cy, 1, a * q)
                em = emoji_image(lk["emoji"], int(56 * self.s * sc))
            lab = _text_cached(str(lk.get("label", "")), int(54 * self.s), "white" if not weak else "grey",
                               "title", int(600 * self.s), "", "")
            _paste(frame, lab, x, cy + h2 + 50 * self.s, 1, a * q)
        if pulse is not None and t >= pulse:
            q = (t - pulse) / 1.8
            stop = (n - 1) / n + .02
            u = min(q, stop)
            px = cx - span / 2 + span * u + span / n * .1
            fz = q > stop
            al = 1.0 if not fz else max(0, 1 - (q - stop) * 2.5)
            if al > 0:
                for rr, al2 in ((34 * self.s, 70), (16 * self.s, 160), (7 * self.s, 255)):
                    jitter = (random.random() - .5) * 14 * self.s if fz else 0
                    dr.ellipse((px - rr + jitter, cy - rr, px + rr + jitter, cy + rr), fill=CYAN[:2] + (255, int(al2 * al)))

    def sfx(self):
        ev = super().sfx()
        for l in ([] if self.d.get("quiet") else self.d.get("links", [])):
            ev.append(("clink", self.shot.T(l.get("at", self.t0)), 1.0))
        if "crack" in self.d:
            ev.append(("fizzle", self.shot.T(self.d["crack"]) - .4, 1.0))
        return ev


class InboxEl(El):
    """Short-term memory tray with 4 slots; cards fly in; overflow shakes; one card falls out."""
    animated = True

    def draw(self, frame, t):
        d = self.d
        a, sc = self.fade(t)
        if a <= 0:
            return
        cx, cy = self.pos(t)
        slots = int(d.get("slots", 4))
        tw, th = 700 * self.s * self.scale, 240 * self.s * self.scale
        cards = d.get("cards", [])
        times = [self.shot.T(c.get("at", self.t0)) for c in cards]
        n_in = sum(1 for tt in times if t >= tt)
        shake = n_in > slots
        sx = math.sin(t * 50) * 7 * self.s if shake else 0
        dr = ImageDraw.Draw(frame, "RGBA")
        layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        dl = ImageDraw.Draw(layer)
        A = int(255 * a)
        dl.rounded_rectangle((cx - tw / 2 + sx, cy - th / 2, cx + tw / 2 + sx, cy + th / 2), radius=28 * self.s,
                             outline=CYAN + (A,), width=int(8 * self.s), fill=(46, 230, 214, int(25 * a)))
        frame.alpha_composite(layer.filter(ImageFilter.GaussianBlur(14 * self.s)))
        frame.alpha_composite(layer)
        cw = tw / slots
        for k in range(slots):
            x = cx - tw / 2 + cw * (k + .5) + sx
            dr.rounded_rectangle((x - cw * .4, cy - th * .38, x + cw * .4, cy + th * .38), radius=16 * self.s,
                                 outline=(255, 255, 255, int(40 * a)), width=int(3 * self.s))
        lab = _text_cached(str(d.get("label", "SHORT-TERM MEMORY")), int(40 * self.s), "cyan", "title",
                           int(1000 * self.s), "", "")
        _paste(frame, lab, cx + sx, cy + th / 2 + 45 * self.s, 1, a)
        drop = self.shot.T(d["drop"]) if "drop" in d else None
        drop_i = int(d.get("drop_index", 0))
        for k, (c, tt) in enumerate(zip(cards, times)):
            if t < tt:
                continue
            q = min(1, (t - tt) / .45)
            slot = k if k < slots else slots - 1 - (k - slots) % slots
            tx = cx - tw / 2 + cw * (slot + .5) + sx
            ty = cy - (0 if k < slots else th * .45 * (1 + (k - slots)))
            fx, fy = self.W * (1.1 if k % 2 else -0.1), cy - self.H * .4
            x, y = _lerp(fx, tx, _out(q)), _lerp(fy, ty, _out(q))
            small = (k == drop_i)
            size = int((95 if not small else 66) * self.s * self.scale)
            img = _card_cached("", c.get("emoji", ""), size, size, "pink" if small else "cyan", 30, "", "panel") \
                if not c.get("tag") else sticker_img(str(c["tag"]), int(size * .7))
            alpha = a
            rot = 0
            if small and drop is not None and t > drop:
                f = (t - drop)
                y += 0.5 * 2200 * self.s * f * f
                x += 120 * self.s * f
                rot = -f * 120
                alpha *= max(0, 1 - f / 1.1)
            if small:
                alpha *= 0.75
            _paste(frame, img, x, y, 1, alpha, rot)

    def sfx(self):
        ev = super().sfx()
        if self.d.get("quiet"):
            return ev + ([("whistle", self.shot.T(self.d["drop"]), 1.0)] if "drop" in self.d else [])
        cards = self.d.get("cards", [])
        for k, c in enumerate(cards):
            ev.append(("pop", self.shot.T(c.get("at", self.t0)), 0.7 + 0.1 * k))
        if len(cards) > int(self.d.get("slots", 4)):
            ev.append(("rumble", self.shot.T(cards[int(self.d.get("slots", 4))].get("at", self.t0)), 1.0))
        if "drop" in self.d:
            ev.append(("whistle", self.shot.T(self.d["drop"]), 1.0))
        return ev


class CircleEl(El):
    """Top-down circle of people taking turns; a word card passes around."""
    animated = True

    def draw(self, frame, t):
        d = self.d
        a, _ = self.fade(t)
        if a <= 0:
            return
        cx, cy = self.pos(t)
        n = int(d.get("n", 8))
        R = float(d.get("r", 300)) * self.s
        hl = d.get("highlight")
        hl_at = self.shot.T(d.get("highlight_at", self.t0))
        grey = d.get("grey", [])
        grey_at = self.shot.T(d.get("grey_at", 1e9))
        dr = ImageDraw.Draw(frame, "RGBA")
        pos = []
        for k in range(n):
            ang = -math.pi / 2 + k / n * 2 * math.pi
            x, y = cx + math.cos(ang) * R, cy + math.sin(ang) * R
            pos.append((x, y))
            hcol = YELLOW if (hl is not None and k == hl and t >= hl_at) else None
            img = topdown_img(int(float(d.get("person", 150)) * self.s), k + 10, hcol)
            img = img.rotate(-math.degrees(ang) - 90, expand=True)
            _paste(frame, img, x, y, 1, a)
        # passing word card
        speed = float(d.get("speed", 1.2))
        k = int((t - self.t0) / speed) % n
        q = ((t - self.t0) / speed) % 1
        x0, y0 = pos[k]
        x1, y1 = pos[(k + 1) % n]
        px, py = _lerp(x0, x1, _ease(q)) * .6 + cx * .4, _lerp(y0, y1, _ease(q)) * .6 + cy * .4
        is_grey = t >= grey_at and (k in grey)
        card = _card_cached("WORD", "", int(120 * self.s), int(70 * self.s), "grey" if is_grey else "cyan",
                            int(26 * self.s), "", "panel")
        if is_grey:
            card = card.filter(ImageFilter.GaussianBlur(3))
        _paste(frame, card, px, py, 1, a)
        if grey and t >= grey_at:
            q = min(1, (t - grey_at) / 0.4)
            mx = sum(pos[g][0] for g in grey) / len(grey)
            my = sum(pos[g][1] for g in grey) / len(grey)
            rr = 150 * self.s
            dr.arc((mx - rr, my - rr, mx + rr, my + rr), -90, -90 + 360 * q, fill=PINK + (int(230 * a),),
                   width=int(10 * self.s))
            lab = _text_cached(str(d.get("grey_label", "~9 SECONDS")), int(56 * self.s), "pink", "title", 800, "", "")
            ox = mx + (mx - cx) * .55
            oy = my + (my - cy) * .55
            _paste(frame, lab, ox, oy, 1, a * q)


class CrowdEl(El):
    """A crowded room from above; one person gets a yellow outline."""
    animated = True

    def draw(self, frame, t):
        d = self.d
        a, _ = self.fade(t)
        if a <= 0:
            return
        rnd = random.Random(42)
        hl_at = self.shot.T(d.get("highlight_at", self.t0 + 1))
        n = int(d.get("n", 34))
        for k in range(n):
            x = rnd.uniform(.12, .88) * self.W
            y = rnd.uniform(.12, .78) * self.H
            if k == 0:
                x, y = .58 * self.W, .45 * self.H
            hcol = YELLOW if (k == 0 and t >= hl_at) else None
            img = topdown_img(int(105 * self.s), k + 100, hcol)
            img = img.rotate(rnd.uniform(0, 360), expand=True) if k else img
            _paste(frame, img, x + math.sin(t * .8 + k) * 6 * self.s, y + math.cos(t * .7 + k) * 4 * self.s, 1, a)


class WebEl(El):
    """A hub word with cyan lines shooting out to icons, each on its word."""
    animated = True

    def draw(self, frame, t):
        d = self.d
        a, sc = self.fade(t)
        if a <= 0:
            return
        cx, cy = self.pos(t)
        items = d.get("items", [])
        R = float(d.get("r", 260)) * self.s
        for k, it in enumerate(items):
            tk = self.shot.T(it.get("at", self.t0))
            if t < tk:
                continue
            ang = math.radians(float(it.get("ang", -150 + k * 300 / max(1, len(items) - 1))))
            ex, ey = cx + math.cos(ang) * R, cy + math.sin(ang) * R * .8
            q = _ease((t - tk) / .35)
            layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).line((cx, cy, _lerp(cx, ex, q), _lerp(cy, ey, q)), fill=CYAN + (int(230 * a),),
                                       width=int(6 * self.s))
            frame.alpha_composite(layer.filter(ImageFilter.GaussianBlur(8 * self.s)))
            frame.alpha_composite(layer)
            if q >= 1 or t > tk + .25:
                ic = _icon_cached(str(it["emoji"]), int(100 * self.s), "", "white", "cyan", "")
                pq = min(1, (t - tk - .25) / .3) if t > tk + .25 else 0
                _paste(frame, ic, ex, ey, 0.8 + .2 * _back(pq), a * pq)
        hub = _pill_cached(str(d.get("hub", "")), int(50 * self.s), str(d.get("color", "cyan")), "navy", "")
        _paste(frame, glow(hub, CYAN, int(12 * self.s), .5) if d.get("glow", True) else hub, cx, cy, sc, a)

    def sfx(self):
        ev = super().sfx()
        for it in self.d.get("items", []):
            ev.append(("pop", self.shot.T(it.get("at", self.t0)) + .25, 0.8))
        return ev


class BrainMapEl(El):
    """'chair' with 5 thick cables vs 'Jessica' with one thin thread to her sound blocks."""
    animated = True

    def draw(self, frame, t):
        d = self.d
        a, _ = self.fade(t)
        if a <= 0:
            return
        W, H, s = self.W, self.H, self.s
        pulse = self.shot.T(d["pulse"]) if "pulse" in d else None
        snap = self.shot.T(d["snap"]) if "snap" in d else None
        mode = d.get("mode", "both")
        layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        dl = ImageDraw.Draw(layer)
        A = int(255 * a)
        if mode in ("both", "chair"):
            hx, hy = W * .25, H * .3
            blocks = [(W * .16, H * .62, "CH"), (W * .34, H * .62, "AIR")]
            for bx, by, _lab in blocks:
                for k in range(5):
                    off = (k - 2) * 9 * s
                    dl.line((hx + off, hy + 30 * s, bx + off, by - 40 * s), fill=CYAN + (A,), width=int(9 * s))
        if mode in ("both", "jessica"):
            jx, jy = W * .72, H * .3
            jb = [(W * .6, H * .62, "JES"), (W * .72, H * .62, "SI"), (W * .84, H * .62, "CA")]
            fl = 0.45 + 0.55 * abs(math.sin(t * 9))
            for bx, by, _lab in jb:
                dl.line((jx, jy + 30 * s, bx, by - 40 * s), fill=(150, 200, 210, int(A * fl * .8)), width=max(2, int(3 * s)))
        frame.alpha_composite(layer.filter(ImageFilter.GaussianBlur(9 * s)))
        frame.alpha_composite(layer)
        if mode in ("both", "chair"):
            _paste(frame, _pill_cached("chair", int(50 * s), "cyan", "navy", ""), W * .25, H * .3, 1, a)
            for bx, by, lab in blocks:
                _paste(frame, _card_cached(lab, "", int(150 * s), int(90 * s), "cyan", int(40 * s), "", "panel"), bx, by, 1, a)
        if mode in ("both", "jessica"):
            _paste(frame, _pill_cached("Jessica", int(50 * s), "pink", "navy", ""), W * .72, H * .3, 1, a)
            fimg = person_img("jessica", "stand", int(170 * s))
            _paste(frame, fimg, W * .86, H * .22, 1, a)
            snapped = snap is not None and t >= snap
            for k, (bx, by, lab) in enumerate(jb):
                lit = snapped or (pulse is not None and t >= pulse + 0.9 and k == 0)
                c = "yellow" if snapped else ("cyan" if lit else "grey")
                txt = (lab if (lit or snapped) else "·" if k else "?")
                if not snapped and k == 0 and lit:
                    txt = "J"
                card = _card_cached(txt, "", int(150 * s), int(90 * s), c, int(40 * s), "", "panel")
                _paste(frame, card, bx, by, 1, a * (1 if lit else .6))
            if pulse is not None and pulse <= t < pulse + 1.6:
                q = (t - pulse) / 1.6
                bx, by, _lab = jb[0]
                u = min(q, .85)
                px, py = _lerp(jx, bx, u), _lerp(jy + 30 * s, by - 40 * s, u)
                al = 1 - max(0, (q - .7) / .3)
                dd = ImageDraw.Draw(frame, "RGBA")
                for rr, al2 in ((20 * s, 60), (9 * s, 150), (4 * s, 255)):
                    dd.ellipse((px - rr, py - rr, px + rr, py + rr), fill=(255, 255, 255, int(al2 * al * (1 - q * .6))))


class LettersEl(El):
    """'J _ _ _ _ _ _' behind frosted glass; snaps into the full word with a burst of light."""
    animated = True

    def draw(self, frame, t):
        d = self.d
        a, sc = self.fade(t)
        if a <= 0:
            return
        cx, cy = self.pos(t)
        word = str(d.get("word", "JESSICA"))
        snap = self.shot.T(d["snap"]) if "snap" in d else None
        size = int(d.get("size", 120) * self.s)
        if snap is not None and t >= snap:
            q = min(1, (t - snap) / .25)
            img = _text_cached(word, size, "yellow", "title", int(1800 * self.s), "", "yellow")
            _paste(frame, img, cx, cy, 0.7 + .3 * _back(q), a)
            dr = ImageDraw.Draw(frame, "RGBA")
            burst = max(0, 1 - (t - snap) / .7)
            if burst > 0:
                for k in range(16):
                    ang = k / 16 * 2 * math.pi
                    r0, r1 = 160 * self.s, (160 + 260 * (1 - burst)) * self.s
                    dr.line((cx + math.cos(ang) * r0, cy + math.sin(ang) * r0 * .6, cx + math.cos(ang) * r1,
                             cy + math.sin(ang) * r1 * .6), fill=YELLOW + (int(255 * burst),), width=int(6 * self.s))
            return
        first = _text_cached(word[0], size, "yellow", "title", 400, "", "yellow")
        rest = "_ " * (len(word) - 1)
        rimg = _text_cached(rest.strip(), size, "white", "title", int(1800 * self.s), "", "")
        total = first.width + rimg.width * .9
        x0 = cx - total / 2
        _paste(frame, first, x0 + first.width / 2, cy, sc, a)
        # frosted panel over the rest
        rx = x0 + first.width + rimg.width * .45
        _paste(frame, rimg, rx, cy, sc, a * .55)
        dr = ImageDraw.Draw(frame, "RGBA")
        pw, ph = rimg.width * .5, rimg.height * .45
        dr.rounded_rectangle((rx - pw, cy - ph, rx + pw, cy + ph), radius=20 * self.s,
                             fill=(200, 220, 255, int(70 * a)), outline=(255, 255, 255, int(90 * a)), width=2)


class NotebookEl(El):
    """Inside the brain: a cyan pen waits at a notebook; can write a name, or drop when the alarm flashes."""
    animated = True

    def draw(self, frame, t):
        d = self.d
        a, sc = self.fade(t)
        if a <= 0:
            return
        cx, cy = self.pos(t)
        s = self.s
        nb = _notebook_img(int(420 * s))
        _paste(frame, nb, cx, cy, sc, a)
        alarm = self.shot.T(d["alarm"]) if "alarm" in d else None
        write = self.shot.T(d["write"]) if "write" in d else None
        px, py, rot = cx + 120 * s, cy - 60 * s, 30
        if alarm is not None and t >= alarm:
            f = t - alarm
            py += min(1, f / .5) ** 2 * 260 * s
            px += f * 80 * s
            rot = 30 + min(1, f / .5) * 80
            if (int(f * 4) % 2 == 0) and f < 2.4:
                al = _text_cached("YOUR TURN!", int(70 * s), "navy", "title", 800, "yellow", "")
                _paste(frame, al, cx, cy - 250 * s, 1, a)
        elif write is not None and t >= write:
            q = min(1, (t - write) / 1.2)
            name = str(d.get("name", "Jessica"))
            shown = name[: int(round(len(name) * q))]
            if shown:
                txt = _hand_cached(shown, int(80 * s))
                _paste(frame, txt, cx - 40 * s + txt.width / 2 - 100 * s, cy - 10 * s, 1, a)
            px = cx - 140 * s + 260 * s * q
            py = cy - 40 * s + math.sin(q * 30) * 8 * s
        pen = _pen_img(int(220 * s))
        _paste(frame, pen, px, py, 1, a, rot)

    def sfx(self):
        ev = super().sfx()
        if "alarm" in self.d:
            ev.append(("alarm", self.shot.T(self.d["alarm"]), 1.0))
        if "write" in self.d:
            ev.append(("type", self.shot.T(self.d["write"]), 1.0))
        return ev


@lru_cache(maxsize=16)
def _notebook_img(w):
    h = int(w * .7)
    img, d = _ss(w, h, 2)
    W, H = w * 2, h * 2
    d.rounded_rectangle((0, 0, W, H), radius=W * .05, fill=(250, 248, 240))
    d.line((W / 2, 0, W / 2, H), fill=(200, 196, 186), width=4)
    for y in range(int(H * .15), H, int(H * .12)):
        d.line((W * .05, y, W * .95, y), fill=(160, 190, 230), width=2)
    return _down(img, 2)


@lru_cache(maxsize=8)
def _pen_img(h):
    img, d = _ss(h * .22, h, 2)
    W, H = h * .44, h * 2
    d.rounded_rectangle((W * .25, 0, W * .75, H * .8), radius=W * .2, fill=CYAN)
    d.polygon([(W * .25, H * .8), (W * .75, H * .8), (W * .5, H)], fill=(230, 230, 230))
    return glow(_down(img, 2), CYAN, 10, .6)


@lru_cache(maxsize=64)
def _hand_cached(text, size):
    f = font("hand", size)
    w = int(f.getlength(text)) + 20
    img = Image.new("RGBA", (w, int(size * 1.4)), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((10, 0), text, font=f, fill=(25, 35, 90))
    return img


class ClockEl(El):
    """A clock with fast-spinning hands (and a label)."""
    animated = True

    def draw(self, frame, t):
        d = self.d
        a, sc = self.fade(t)
        if a <= 0:
            return
        cx, cy = self.pos(t)
        r = float(d.get("r", 90)) * self.s * sc
        dr = ImageDraw.Draw(frame, "RGBA")
        dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(250, 250, 252, int(255 * a)), outline=YELLOW + (int(255 * a),),
                   width=int(8 * self.s))
        spin = float(d.get("spin", 6))
        ang = (t - self.t0) * spin * 2 * math.pi
        if d.get("jumps"):
            js = [self.shot.T(j) for j in d["jumps"]]
            ang = sum(1 for j in js if t >= j) * math.pi * .7 + min(1, max(0, (t - max([j for j in js if j <= t] or [-9])) / .3)) * 0
        dr.line((cx, cy, cx + math.sin(ang) * r * .75, cy - math.cos(ang) * r * .75), fill=NAVY + (int(255 * a),),
                width=int(7 * self.s))
        dr.line((cx, cy, cx + math.sin(ang / 12) * r * .5, cy - math.cos(ang / 12) * r * .5), fill=NAVY + (int(255 * a),),
                width=int(9 * self.s))
        if d.get("label"):
            lab = _text_cached(str(d["label"]), int(d.get("size", 44) * self.s), "yellow", "title", int(900 * self.s), "", "")
            _paste(frame, lab, cx, cy + r + 45 * self.s, 1, a)


class ConfettiEl(El):
    animated = True

    def draw(self, frame, t):
        if t < self.t0 or t > self.t0 + 2.5:
            return
        rnd = random.Random(self.seed)
        cx, cy = self.pos(t)
        dt = t - self.t0
        dr = ImageDraw.Draw(frame, "RGBA")
        for _ in range(90):
            vx, vy = rnd.uniform(-700, 700), rnd.uniform(-900, -300)
            c = rnd.choice([YELLOW, CYAN, PINK, WHITE])
            x = cx + vx * dt * self.s
            y = cy + (vy * dt + 900 * dt * dt) * self.s
            a = int(255 * max(0, 1 - dt / 2.5))
            sz = rnd.uniform(6, 13) * self.s
            dr.rectangle((x - sz, y - sz / 2, x + sz, y + sz / 2), fill=c + (a,))


class LogoEl(El):
    """MindBlip wordmark: white Montserrat with a yellow dot on the i, with a cyan pulse."""
    animated = True

    def draw(self, frame, t):
        d = self.d
        a, sc = self.fade(t)
        cx, cy = self.pos(t)
        s = self.s
        # pulse travelling along a neuron into the logo
        q = (t - self.t0 + 1.0) / 1.0
        dr = ImageDraw.Draw(frame, "RGBA")
        if d.get("pulse", True) and 0 < q < 1:
            x = _lerp(-0.05 * self.W, cx, _ease(q))
            layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).line((0, cy, x, cy), fill=CYAN + (200,), width=int(6 * s))
            frame.alpha_composite(layer.filter(ImageFilter.GaussianBlur(8 * s)))
            frame.alpha_composite(layer)
            for rr, al in ((30 * s, 70), (14 * s, 160), (6 * s, 255)):
                dr.ellipse((x - rr, cy - rr, x + rr, cy + rr), fill=(255, 255, 255, al))
        if a <= 0:
            return
        img = _logo_img(int(d.get("size", 150) * s))
        _paste(frame, img, cx, cy, sc, a)


@lru_cache(maxsize=8)
def _logo_img(size):
    f = font("title", size)
    text = "MindBlip"
    w = int(f.getlength(text)) + 40
    h = int(size * 1.5)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 20
    for n, ch in enumerate(text):
        if ch == "i":
            # dotless i + yellow dot
            d.text((x, size * .15), "ı", font=f, fill=WHITE)
            cw = f.getlength("ı")
            r = size * .09
            d.ellipse((x + cw / 2 - r, size * .22 - r, x + cw / 2 + r, size * .22 + r), fill=YELLOW)
            x += cw
        else:
            d.text((x, size * .15), ch, font=f, fill=WHITE)
            x += f.getlength(ch)
    return glow(img, CYAN, max(6, size // 10), .45)


class EndScreenEl(El):
    animated = True

    def draw(self, frame, t):
        a, sc = self.fade(t)
        if a <= 0:
            return
        s = self.s
        _paste(frame, _logo_img(int(110 * s)), self.W / 2, self.H * .14, sc, a)
        # subscribe button
        btn = _pill_cached("SUBSCRIBE", int(56 * s), "red", "white", "")
        _paste(frame, btn, self.W * .22, self.H * .5, sc * (1 + .04 * math.sin(t * 4)), a)
        dr = ImageDraw.Draw(frame, "RGBA")
        for k in range(2):
            x0 = self.W * (.45 + k * .27)
            dr.rounded_rectangle((x0, self.H * .33, x0 + self.W * .24, self.H * .33 + self.W * .135), radius=14 * s,
                                 outline=(255, 255, 255, int(110 * a)), width=int(4 * s))


ELEMENTS = {"text": TextEl, "title": TitleEl, "source": SourceEl, "sticker": StickerEl, "person": PersonEl,
            "blip": BlipEl, "juggler": JugglerEl, "spinner": SpinnerEl, "icon": IconEl, "bubble": BubbleEl, "mark": MarkEl, "pill": PillEl, "card": CardEl,
            "line": LineEl, "graph": GraphEl, "ring": RingEl, "chain": ChainEl, "inbox": InboxEl,
            "circle": CircleEl, "crowd": CrowdEl, "web": WebEl, "brainmap": BrainMapEl, "letters": LettersEl,
            "notebook": NotebookEl, "clock": ClockEl, "confetti": ConfettiEl, "logo": LogoEl,
            "endscreen": EndScreenEl}


# ----------------------------------------------------------------- looks + camera
def _look(img: Image.Image, look: str, t: float, rnd: random.Random) -> Image.Image:
    if look == "sepia":
        arr = np.asarray(img.convert("RGB")).astype(np.float32)
        g = arr.mean(2, keepdims=True)
        arr = np.clip(g * np.array([1.07, .9, .68]) + 12, 0, 255)
        out = Image.fromarray(arr.astype(np.uint8), "RGB")
        return out.convert("RGBA")
    if look == "film":
        arr = np.asarray(img.convert("RGB")).astype(np.float32)
        g = arr.mean(2, keepdims=True)
        arr = g * .75 + arr * .25
        arr *= 0.92 + 0.08 * math.sin(t * 37)
        H, W = arr.shape[:2]
        noise = np.random.default_rng(int(t * 30)).normal(0, 14, (H // 4, W // 4, 1))
        noise = np.repeat(np.repeat(noise, 4, 0), 4, 1)[:H, :W]
        arr = np.clip(arr + noise, 0, 255)
        out = Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")
        d = ImageDraw.Draw(out, "RGBA")
        if rnd.random() < .3:
            x = rnd.uniform(0, W)
            d.line((x, 0, x + rnd.uniform(-10, 10), H), fill=(230, 230, 230, 60), width=2)
        return out
    return img


def _camera(img: Image.Image, zoom: float, cx: float, cy: float) -> Image.Image:
    if zoom <= 1.0005:
        return img
    W, H = img.size
    cw, ch = W / zoom, H / zoom
    x0 = min(max(cx * W - cw / 2, 0), W - cw)
    y0 = min(max(cy * H - ch / 2, 0), H - ch)
    return img.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))


def _cam_at(shot: Shot, t: float):
    keys = shot.raw.get("cam")
    if not keys:
        push = float(shot.raw.get("push", 0.08))
        return 1 + push * min(1, t / max(shot.dur, .1)), .5, .5
    ks = [(shot.T(k[0]), float(k[1]), float(k[2]), float(k[3])) for k in keys]
    if t <= ks[0][0]:
        return ks[0][1:]
    for a, b in zip(ks, ks[1:]):
        if a[0] <= t <= b[0]:
            p = _ease((t - a[0]) / max(b[0] - a[0], 1e-3))
            return tuple(_lerp(a[i], b[i], p) for i in (1, 2, 3))
    return ks[-1][1:]


# ----------------------------------------------------------------- render
def render_track(raw_scenes: list[dict], timings: list[tuple[float, float]], speech: list[tuple[float, float]],
                 total: float, size: tuple[int, int], fps: int, out_video: Path, out_sfx: Path,
                 sfx_volume: float = 0.3, voice: Path | None = None) -> Path:
    W, H = size
    shots = [Shot(r, a, b, sp, i) for i, (r, (a, b), sp) in enumerate(zip(raw_scenes, timings, speech))]
    events: list[tuple[str, float, float]] = []
    built = []
    for sh in shots:
        els = []
        for d in sh.raw.get("els", []):
            cls = ELEMENTS.get(d.get("type", ""))
            if cls is None:
                log(f"Explainer: unknown element type {d.get('type')!r} in shot {sh.i}")
                continue
            el = cls(d, sh, size)
            els.append(el)
            for kind, at, g in el.sfx():
                events.append((kind, sh.start + at, g))
        for spec in sh.raw.get("sfx", []):
            events.append((spec[1], sh.start + sh.T(spec[0]), float(spec[2]) if len(spec) > 2 else 1.0))
        tr = sh.raw.get("tr", "dissolve" if sh.i else "fade")
        if tr == "zap":
            events.append(("zap", sh.start, 1.0))
        backdrop = Backdrop(str(sh.raw.get("bg", "navy")), size, seed=sh.i + 1)
        built.append((sh, els, backdrop))

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-pix_fmt", "yuv420p", str(out_video)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n_frames = int(round(total * fps))
    prev_last: Image.Image | None = None
    cur = 0
    rnd = random.Random(5)
    last_log = -60
    for f in range(n_frames):
        t_abs = f / fps
        while cur < len(built) - 1 and t_abs >= built[cur][0].end:
            cur += 1
        sh, els, bd = built[cur]
        t = t_abs - sh.start
        frame = bd.frame(t)
        for el in els:
            el.draw(frame, t)
        zoom, cx, cy = _cam_at(sh, t)
        frame = _camera(frame, zoom, cx, cy)
        frame = _look(frame, str(sh.raw.get("look", "")), t, rnd)
        tr = sh.raw.get("tr", "dissolve" if sh.i else "fade")
        if prev_last is not None and tr in ("zap", "dissolve") and t < (0.42 if tr == "zap" else 0.5):
            if tr == "dissolve":
                frame = Image.blend(prev_last, frame, _ease(t / 0.5))
            else:
                p = _ease(t / 0.42)
                xcut = int(p * (W + 60 * H / 1080))
                mix = prev_last.copy()
                if xcut > 0:
                    mix.paste(frame.crop((0, 0, min(xcut, W), H)), (0, 0))
                layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
                ImageDraw.Draw(layer).line((xcut, 0, xcut - 60 * H / 1080, H), fill=CYAN + (255,), width=int(10 * H / 1080))
                mix.alpha_composite(layer.filter(ImageFilter.GaussianBlur(18 * H / 1080)))
                mix.alpha_composite(layer)
                frame = mix
        elif tr == "fade" and t < 0.6:
            frame = Image.blend(Image.new("RGBA", frame.size, (0, 0, 0, 255)), frame, _ease(t / .6))
        if t_abs + 1 / fps >= sh.end - 1e-6 or (cur < len(built) - 1 and t_abs + 1 / fps >= built[cur][0].end):
            prev_last = frame.copy()
        proc.stdin.write(frame.convert("RGB").tobytes())
        if t_abs - last_log >= 60:
            log(f"Explainer: drawn {t_abs:.0f}s of {total:.0f}s")
            last_log = t_abs
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed while encoding the explainer video")
    write_sfx(events, total, out_sfx, sfx_volume, voice)
    return out_video


def thumbnail(spec: dict, size: tuple[int, int], out: Path) -> Path:
    """Thumbnail from a small spec: a shot made of elements, drawn at t = 5 s (everything popped in)."""
    shot = Shot({"text": "", "els": spec.get("els", [])}, 0, 10, (0, 0), 0)
    bd = Backdrop(str(spec.get("bg", "navy")), size, 9)
    frame = bd.frame(0)
    for d in spec.get("els", []):
        cls = ELEMENTS.get(d.get("type", ""))
        if cls:
            cls(d, shot, size).draw(frame, 5.0)
    frame.convert("RGB").save(out, quality=92)
    return out
