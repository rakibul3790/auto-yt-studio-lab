"""Whole-subject framing (mindblip-studio core/motion.md: "Never crop off heads/feet of
the subject: use keep-boxes, or show the image whole on a margin").

- find_boxes(): where the subject is in a picture, with an open-vocabulary detector
  (OWLv2, free, runs on the CPU). Any failure just means "no box" and the old centre
  framing is used, so nothing breaks.
- content_box(): the real picture inside black letterbox / pillarbox bars.
- wholeness(): how complete the subject is in the source (cut at the edge = bad).
- plan(): how to show a source on a 9:16 screen without cutting the subject:
  "fill" (crop a 9:16 window that holds the whole subject) or "fit" (show a wider
  window whole, smaller, over a blurred copy of itself).
- on_screen(): where a box of the source ends up on the screen (for bubbles, checks).
"""
from __future__ import annotations

import os

import numpy as np
from PIL import Image

from .common import log

MODEL = "google/owlv2-base-patch16-ensemble"
MIN_SCORE = 0.12          # detector confidence to count as "the subject is there"
PAD = 0.06                # breathing room kept around the subject (fraction of its size)
EDGE = 0.015              # a box this close to the picture edge counts as touching it

_det = None               # (processor, model) or False when unavailable


def _load():
    global _det
    if _det is None:
        if str(os.environ.get("STUDIO_DETECTOR", "on")).lower() in ("0", "off", "no"):
            _det = False
            return None
        try:
            import torch
            from transformers import Owlv2ForObjectDetection, Owlv2Processor
            torch.set_num_threads(max(1, os.cpu_count() or 1))
            proc = Owlv2Processor.from_pretrained(MODEL)
            model = Owlv2ForObjectDetection.from_pretrained(MODEL)
            model.eval()
            _det = (proc, model)
            log("Framing: subject detector loaded")
        except Exception as e:
            log(f"Framing: detector off ({type(e).__name__}: {str(e)[:160]}); centre framing")
            _det = False
    return _det or None


def available() -> bool:
    return _load() is not None


def _queries(subject: str) -> list[str]:
    s = " ".join(str(subject or "").lower().split())
    if not s:
        return []
    base = s[:-1] if s.endswith("s") and not s.endswith("ss") and len(s) > 3 else s
    return list(dict.fromkeys([f"a photo of a {base}", f"a {base}"]))


def find_boxes(img: Image.Image, subject: str, min_score: float = MIN_SCORE) -> list[tuple]:
    """[(score, x0, y0, x1, y1)] in 0..1 of the picture, best first."""
    d = _load()
    q = _queries(subject)
    if not d or not q:
        return []
    try:
        import torch
        proc, model = d
        im = img.convert("RGB")
        if max(im.size) > 960:
            k = 960 / max(im.size)
            im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))))
        inputs = proc(text=[q], images=im, return_tensors="pt")
        with torch.no_grad():
            out = model(**inputs)
        # OWLv2 pads the picture to a square: boxes come back relative to that square
        side = max(im.size)
        target = torch.tensor([[side, side]])
        res = proc.image_processor.post_process_object_detection(outputs=out, threshold=min_score, target_sizes=target)[0]
        boxes = []
        for s, b in zip(res["scores"].tolist(), res["boxes"].tolist()):
            x0, y0, x1, y1 = b
            x0, x1 = max(0.0, x0 / im.width), min(1.0, x1 / im.width)
            y0, y1 = max(0.0, y0 / im.height), min(1.0, y1 / im.height)
            if x1 - x0 > 0.02 and y1 - y0 > 0.02:
                boxes.append((float(s), x0, y0, x1, y1))
        boxes.sort(key=lambda b: -b[0])
        return _merge(boxes)
    except Exception as e:
        log(f"Framing: detection failed ({type(e).__name__}: {str(e)[:120]})")
        return []


def _iou(a, b) -> float:
    ix = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    iy = max(0.0, min(a[4], b[4]) - max(a[2], b[2]))
    inter = ix * iy
    ua = (a[3] - a[1]) * (a[4] - a[2]) + (b[3] - b[1]) * (b[4] - b[2]) - inter
    return inter / ua if ua > 0 else 0.0


def _merge(boxes: list[tuple]) -> list[tuple]:
    keep: list[tuple] = []
    for b in boxes:
        if all(_iou(b, k) < 0.5 for k in keep):
            keep.append(b)
    return keep


def keep_box(boxes: list[tuple]) -> tuple | None:
    """The part that must stay on screen: the best box, plus any other strong one
    (a mother and baby, two animals) that scored close to it."""
    if not boxes:
        return None
    best = boxes[0]
    group = [b for b in boxes if b[0] >= max(best[0] * 0.75, MIN_SCORE)][:3]
    return (min(b[1] for b in group), min(b[2] for b in group),
            max(b[3] for b in group), max(b[4] for b in group))


def wide_box(boxes: list[tuple], ratio: float = 0.4) -> tuple | None:
    """Everything that might be the subject: every box that scored at least `ratio` of the
    best one (a second animal half in the frame, a head the detector boxed on its own).
    Used to frame a shot and to check it, so a partly found animal is not cut."""
    if not boxes:
        return None
    best = boxes[0]
    group = [b for b in boxes if b[0] >= max(best[0] * ratio, MIN_SCORE)][:6]
    return (min(b[1] for b in group), min(b[2] for b in group),
            max(b[3] for b in group), max(b[4] for b in group))


def cut_edges(box: tuple | None, region: tuple = (0.0, 0.0, 1.0, 1.0), edge: float = 0.012) -> list[str]:
    """Which edges of `region` (x0, y0, x1, y1 in 0..1 of the frame) the box touches:
    a subject that touches any edge is cut there."""
    if not box:
        return []
    x0, y0, x1, y1 = region
    out = []
    if box[0] <= x0 + edge:
        out.append("left")
    if box[1] <= y0 + edge:
        out.append("top")
    if box[2] >= x1 - edge:
        out.append("right")
    if box[3] >= y1 - edge:
        out.append("bottom")
    return out


def union(boxes: list[tuple | None]) -> tuple | None:
    bs = [b for b in boxes if b]
    if not bs:
        return None
    return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))


def content_box(imgs: list[Image.Image]) -> tuple:
    """(x0, y0, x1, y1) in 0..1 without black bars on the edges (same bars on every frame)."""
    best = [0.0, 0.0, 1.0, 1.0]
    first = True
    for im in imgs:
        a = np.asarray(im.convert("L").resize((160, 160)), dtype=np.float32)
        rows = (a.mean(axis=1) > 20) | (a.std(axis=1) > 10)
        cols = (a.mean(axis=0) > 20) | (a.std(axis=0) > 10)
        if not rows.any() or not cols.any():
            continue
        r = np.where(rows)[0]
        c = np.where(cols)[0]
        b = [c[0] / 160, r[0] / 160, (c[-1] + 1) / 160, (r[-1] + 1) / 160]
        if first:
            best, first = b, False
        else:   # keep only bars that are there on every frame
            best = [min(best[0], b[0]), min(best[1], b[1]), max(best[2], b[2]), max(best[3], b[3])]
    # ignore slivers: only bars of 3% or more are real
    x0, y0, x1, y1 = best
    x0 = x0 if x0 >= 0.03 else 0.0
    y0 = y0 if y0 >= 0.03 else 0.0
    x1 = x1 if x1 <= 0.97 else 1.0
    y1 = y1 if y1 <= 0.97 else 1.0
    if x1 - x0 < 0.4 or y1 - y0 < 0.4:
        return (0.0, 0.0, 1.0, 1.0)
    return (round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4))


def to_content(box: tuple | None, content: tuple) -> tuple | None:
    """A box in whole-picture coordinates, re-expressed inside the content area."""
    if not box:
        return None
    cx0, cy0, cx1, cy1 = content
    cw, ch = cx1 - cx0, cy1 - cy0
    x0 = min(max((box[0] - cx0) / cw, 0.0), 1.0)
    y0 = min(max((box[1] - cy0) / ch, 0.0), 1.0)
    x1 = min(max((box[2] - cx0) / cw, 0.0), 1.0)
    y1 = min(max((box[3] - cy0) / ch, 0.0), 1.0)
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def touching(box: tuple | None, edge: float = EDGE) -> dict:
    if not box:
        return {}
    return {"left": box[0] <= edge, "top": box[1] <= edge, "right": box[2] >= 1 - edge,
            "bottom": box[3] >= 1 - edge}


def wholeness(box: tuple | None) -> float:
    """1.0 = the whole subject sits inside the picture with room around it;
    lower when it is cut at the edges, tiny, or fills everything (an extreme close-up)."""
    if not box:
        return 0.0
    t = touching(box)
    area = (box[2] - box[0]) * (box[3] - box[1])
    s = 1.0
    s -= 0.35 * t["top"] + 0.25 * t["bottom"] + 0.15 * t["left"] + 0.15 * t["right"]
    if area > 0.8:
        s -= 0.3
    if area < 0.03:
        s -= 0.3
    return max(s, 0.0)


def _pad(box: tuple, aspect_px: float, pad: float = PAD) -> tuple:
    """Box grown by pad of its size (at least a little), still inside 0..1.
    aspect_px = source width / height, so the pad looks even on screen."""
    bw, bh = box[2] - box[0], box[3] - box[1]
    px = max(bw * pad, 0.01)
    py = max(bh * pad, 0.01 * aspect_px)
    return (max(box[0] - px, 0.0), max(box[1] - py, 0.0), min(box[2] + px, 1.0), min(box[3] + py, 1.0))


def fits_fill(box: tuple | None, content_w: float, content_h: float, size: tuple[int, int] = (1080, 1920)) -> bool:
    """True when the whole subject (with a small margin) fits a full-screen 9:16 window of
    the picture, so it can fill the screen without being cut or shrunk."""
    if not box:
        return False
    target = size[0] / size[1]
    ww, wh = (content_h * target, content_h) if content_w / content_h > target else (content_w, content_w / target)
    pb = _pad(box, content_w / content_h, 0.015)
    return (pb[2] - pb[0]) * content_w <= ww + 0.5 and (pb[3] - pb[1]) * content_h <= wh + 0.5


def cover_plan(src_w: int, src_h: int, content: tuple, box: tuple | None, size: tuple[int, int],
               zoom: float = 1.04) -> dict:
    """A full-screen 9:16 window centred on the subject, even if part of it falls outside.
    Only for blurred backgrounds behind a graphic or card, never for a shot of its own."""
    W, H = size
    cx0, cy0, cx1, cy1 = content
    cw, ch = (cx1 - cx0) * src_w, (cy1 - cy0) * src_h
    ox, oy = cx0 * src_w, cy0 * src_h
    target = W / H
    ww, wh = (ch * target, ch) if cw / ch > target else (cw, cw / target)
    bcx, bcy = (((box[0] + box[2]) / 2) * cw, ((box[1] + box[3]) / 2) * ch) if box else (cw / 2, ch / 2)
    x = min(max(bcx - ww / 2, 0.0), cw - ww)
    y = min(max(bcy - wh / 2, 0.0), ch - wh)
    return {"mode": "fill", "crop": (ox + x, oy + y, ww, wh), "zmax": zoom, "focus": (0.5, 0.5),
            "box": None, "wbox": None}


def plan(src_w: int, src_h: int, content: tuple, box: tuple | None, size: tuple[int, int],
         zoom: float = 1.06, force_fit: bool = False, grow: float = 1.0) -> dict:
    """How to show a source on the screen.

    Returns {"mode": "fill"|"fit", "crop": (x, y, w, h) in source pixels (the window that
    is shown), "zmax": safe extra zoom inside the window, "focus": (fx, fy) 0..1 of the
    window, "show": (w, h) on-screen size of the window in fit mode}.
    box is in content coordinates (0..1 of the content area)."""
    W, H = size
    cx0, cy0, cx1, cy1 = content
    cw, ch = (cx1 - cx0) * src_w, (cy1 - cy0) * src_h
    ox, oy = cx0 * src_w, cy0 * src_h
    target = W / H
    if not box:                                   # nothing found: the old centre crop, gently
        if cw / ch > target:
            ww, wh = ch * target, ch
        else:
            ww, wh = cw, cw / target
        return {"mode": "fill", "crop": (ox + (cw - ww) / 2, oy + (ch - wh) / 2, ww, wh), "zmax": zoom,
                "focus": (0.5, 0.5), "box": None, "wbox": None}
    # the biggest 9:16 window inside the content
    if cw / ch > target:
        ww, wh = ch * target, ch
    else:
        ww, wh = cw, cw / target
    for pad in (PAD, 0.015):                      # a tighter margin before giving up on full screen
        pb = _pad(box, cw / ch, pad)
        bx0, by0, bx1, by1 = pb[0] * cw, pb[1] * ch, pb[2] * cw, pb[3] * ch
        bw, bh = bx1 - bx0, by1 - by0
        if bw <= ww and bh <= wh:
            break
    bcx, bcy = (bx0 + bx1) / 2, (by0 + by1) / 2
    if not force_fit and bw <= ww and bh <= wh:   # whole subject fits a 9:16 window (moves only if room)
        # a closer window when the subject is small, so it isn't lost on the screen
        tight = max(bw / ww, bh / wh) * zoom
        k = min(max(tight / 0.55, 0.62), 1.0) if tight < 0.55 else 1.0
        ww2, wh2 = ww * k, wh * k
        x = min(max(bcx - ww2 / 2, 0.0), cw - ww2)
        y = min(max(bcy - wh2 / 2, 0.0), ch - wh2)
        zmax = max(1.0, min(ww2 / bw, wh2 / bh, 1.12))
        return {"mode": "fill", "crop": (ox + x, oy + y, ww2, wh2), "zmax": zmax,
                "focus": ((bcx - x) / ww2, (bcy - y) / wh2), "box": pb,
                "wbox": ((bx0 - x) / ww2, (by0 - y) / wh2, (bx1 - x) / ww2, (by1 - y) / wh2)}
    # fit: the narrowest window (closest to 9:16, so the biggest on screen) that holds the subject
    a = min(max(bw / bh, target), cw / ch)
    wh2 = max(bh, bw / a)
    ww2 = wh2 * a
    if ww2 > cw:
        ww2, wh2 = cw, cw / a
    if wh2 > ch:
        wh2, ww2 = ch, ch * a
    if grow > 1.0:                                # room around the subject for soft edges
        ww2, wh2 = min(ww2 * grow, cw), min(wh2 * grow, ch)
        a = ww2 / wh2
    x = min(max(bcx - ww2 / 2, 0.0), cw - ww2)
    y = min(max(bcy - wh2 / 2, 0.0), ch - wh2)
    show_w = W
    show_h = int(round(show_w / a / 2)) * 2
    if show_h > H * 0.78:                         # a tall window: keep a margin top and bottom
        show_h = int(H * 0.78) // 2 * 2
        show_w = int(round(show_h * a / 2)) * 2
    zmax = max(1.0, min(ww2 / bw, wh2 / bh, 1.06))
    return {"mode": "fit", "crop": (ox + x, oy + y, ww2, wh2), "zmax": zmax,
            "focus": ((bcx - x) / ww2, (bcy - y) / wh2), "show": (show_w, show_h), "box": pb,
            "wbox": ((bx0 - x) / ww2, (by0 - y) / wh2, (bx1 - x) / ww2, (by1 - y) / wh2)}


def on_screen(p: dict, box: tuple | None, src_w: int, src_h: int, content: tuple,
              size: tuple[int, int]) -> tuple | None:
    """Where a content-coordinates box lands on the screen (pixels), at zoom 1."""
    if not box:
        return None
    W, H = size
    cx0, cy0, cx1, cy1 = content
    cw, ch = (cx1 - cx0) * src_w, (cy1 - cy0) * src_h
    ox, oy = cx0 * src_w, cy0 * src_h
    x, y, ww, wh = p["crop"]
    if p["mode"] == "fill":
        sx, sy, offx, offy = W / ww, H / wh, 0.0, 0.0
    else:
        sw, sh = p["show"]
        sx, sy = sw / ww, sh / wh
        offx, offy = (W - sw) / 2, fit_top(p, size)
    bx0 = (ox + box[0] * cw - x) * sx + offx
    by0 = (oy + box[1] * ch - y) * sy + offy
    bx1 = (ox + box[2] * cw - x) * sx + offx
    by1 = (oy + box[3] * ch - y) * sy + offy
    return (bx0, by0, bx1, by1)


def fit_top(p: dict, size: tuple[int, int]) -> int:
    """Top of the picture in fit mode: a little above the middle, clear of the captions."""
    W, H = size
    sh = p["show"][1]
    return int(max(H * 0.10, min((H - sh) * 0.42, H * 0.80 - sh)))
