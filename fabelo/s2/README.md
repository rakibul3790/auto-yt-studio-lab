# Smooth Scribble (s2): the thumbnail-style character

Fabelo Studio has **two** main characters. Rakib picks one for each video:

| | Classic Scribble | Smooth Scribble (this folder) |
|---|---|---|
| Look | ink line stick figure, tuft hair, thin scarf | big shaded white head, smooth solid black body, puffy knitted red scarf with fringe (matches the AI thumbnails) |
| Library | `fabelo/lib/scribble.js` (+ v2 engine `fabelo/v2/lib/fabelo2.js`) | `fabelo/s2/lib/scribble2.js` + `fabelo/s2/lib/sets2.js` |
| Build | v1 `tools/` or v2 `v2/tools/render.sh` | `s2/tools/render_s2.sh` (uses the v2 recorder, mixer and finisher read-only) |

Never mix the two characters in one film unless Rakib asks for it.
Never change the Classic files from here. Smooth Scribble lives only in `fabelo/s2/`.

## 1. Character lock (approved by Rakib on 2026-11-26, front view "B")

The look was approved step by step: head and scarf first, then body/arms/legs, then proportions "B".
`sheets/front_approved.png`, `sheets/turnaround.png`, `sheets/expressions.png`, `sheets/walkrun.png` and `sheets/actions.png` are the model sheets.

**Locked:**
- Head: a big perfect circle (r 122 at scale 1), soft white radial shading, a soft grey shade inside the lower-left rim, a clean dark outline (0.062 r).
- Face: tall black oval eyes with a tiny white highlight, thin short brows, a thin one-line mouth. No nose, ears, hair or fingers.
- Body: solid black, smooth tapered torso (rounded shoulders, slight waist, rounded hips), tapered arms and legs, round mitten hands with a thumb, small rounded shoes.
- Scarf: puffy two-roll knitted red scarf (`#F45B4E` → `#D83A30`) with fringed tails. It is always on. Red is the only accent colour.
- Proportions B: `Scribble2.B` = { r 122, torsoL 205, torsoW 60, legW 24, armW 17.5, thigh 155, shin 151, upper 104, fore 96 }.
- Warm paper world; night scenes use the blue night grade with phone light (`S2.night`).

**Never:**
- Draw him by hand or outside `scribble2.js`.
- Recolour him or the scarf.
- Make him speak in emotional shorts (he acts; others narrate).
- Give a side character a scarf: side characters use `scarf:false` (and can differ in scale).

## 2. API (`lib/scribble2.js`)

```js
Scribble2.defs()                       // put once at the top of the SVG
Scribble2.draw({ view, f, x, y, scale, pose, face, look, hands, phone, glow, wind, phase, over, blink, scarf })
Scribble2.head(cx, cy, r, { view, f, face, look, tilt, glow, blink })   // head only (close-ups, expression sheets)
Scribble2.POSES.idleFront / idleQ / idleSide,  Scribble2.WALK (8 keys),  Scribble2.RUN (8 keys)
Scribble2.LAST  // after draw(): { phone:[x,y] or null, head:[x,y,r], hand:{1:[x,y],2:[x,y]} } for light layers and props in hands
Scribble2.arm({ x, y, deg, bend, scale, hand, k, phone, glow })   // one arm alone (in bed under a blanket, behind a counter)
// draw({ ..., noHead: true }) draws the body only, so a head can be placed on a pillow with Scribble2.head
```

- `view`: `front`, `q` (3/4), `side`, `back`. `f`: 1 faces right, -1 faces left (q and side).
- `x, y`: the ground point between the feet. `scale`: about 0.92 for 1920x1080, about 1.05 for 1080x1920.
- `pose` (angles in degrees, 0 = hanging straight down):
  - `a1`, `a2`: arm `[shoulder, elbowBend, upperScale?, foreScale?]`. `l1`, `l2`: leg `[hip, kneeBend]`.
  - front/back: 1 = screen-left limb, 2 = screen-right, + = outward.
  - q/side: 1 = near limb, 2 = far limb, + = forward.
  - `ft1`, `ft2`: foot tilt (+ = toe up). `lean`: torso lean. `tilt`: head tilt (+ = looks down/forward).
  - `seat`: hip height when sitting (bed ≈ 166, chair ≈ 150). Without `seat` the lowest foot is put on the ground automatically.
  - `lift`: raise after grounding (jumps, run flight).
- `face`: neutral smile happy sad worried cry surprised angry focused sleepy closed. `look`: `[dx, dy]` eye direction (-1..1).
- `hands`: `[h1, h2]`, each relax | fist | open | point | phone. `phone`: `{ ang, dx, dy }` placement next to the phone hand. `glow`: phone light.
- `wind`: scarf tails trail back (walk 0.3, run 0.85); `phase` animates the flutter.
- `over`: arms drawn on top of the head, for hand-to-face poses (`[1]` near arm in q/side, `[1,2]` in front).

Staging rules (learned while building him):
- A raised arm in front view must stay outside the head: waving = `a2: [100, 48 ± 15]`, cheering = `[118, 30]`. Bigger angles hide the arm behind the head.
- Front-view knee bends cross the legs. Show crouches and kneels in q or side view.
- Keep the walk speed at about `460 * scale` px per walk cycle so the feet don't slide.
- Turn between views through `q` for 3–5 frames (side → q → front).
- Hand-to-face poses (think, facepalm, cry) need `over`.

## 3. Scene helpers (`lib/sets2.js`)

`S2.lp` (blend poses), `S2.walkAt(phase)`, `S2.runAt(phase)`, `S2.prog(t, a, b)` (eased), `S2.blinkAt(t)`,
`S2.room(st, {night})`, `S2.bed / chair / table(x, st, scale, mirror)`, `S2.night(alpha, light, st)` (draw after the figure),
`S2.caption(t, TIMING, st)` (word-by-word captions with the spoken word in red; use them in every Short),
`S2.title(text, x, y, size, opts)` (handwritten Caveat).
`st` is the stage `{ W, H, GY }` (GY is the floor line), so the same scene can render 16:9 and 9:16.

## 4. Workflow

1. Copy `templates/film.src.html` and `templates/film.audio.json` to `fabelo/work/<slug>/`. Fix the two `<script src>` paths if the folder depth differs.
2. Write the voices in `film.audio.json` with emotion (see the header of `tools/emo_voice.py`). Free Kokoro by default; ElevenLabs v3 only when Rakib says yes.
   - Emotion comes from phrases: per-phrase speed and pitch, real pauses, breaths, a tone per emotion (warm, happy, sad, whisper, hopeful, tense, child) and trailing endings. Keep it natural, never over-acted.
3. Make the voices first and time the scene to them:
   ```bash
   python3 s2/tools/emo_voice.py --spec work/<slug>/film.audio.json --models "$FABELO_MODELS" --out work/<slug>/voice
   python3 s2/tools/build_s2.py work/<slug>/film.src.html work/<slug>/film.html --timing work/<slug>/voice/timing.json
   node s2/tools/preview_s2.js work/<slug>/film.html work/<slug>/prev.png "1,3,5,8,12" --w 1920 --h 1080
   ```
   Look at every tile and fix problems before recording.
4. Render the whole film:
   ```bash
   bash s2/tools/render_s2.sh work/<slug> --w 1920 --h 1080 --fps 30 --blur 2 --workers 3
   ```
   For a Short use `--w 1080 --h 1920`. For 4K use `--w 3840 --h 2160 --scale 2` with at most 3 workers.
5. QC: `render_s2.sh` writes 2 fps contact sheets to `qc/`; check every tile.
   - Prepared voices (ElevenLabs v3): put `voice/line_XX.wav` + `voice/timing.json` in the film folder; the Kokoro step is skipped.
   - Real effect files: list them in `"sfx_files"` (files in `sfx/`); `tools/overlay_files.py` lays them over the mix.
   - Cloud render (nothing heavy on Rakib's PC): put the film folder in `fabelo/v2/renders/<slug>/` with a `RENDER` file
     (`--w 1080 --h 1920 --fps 30 --blur 4`), push a `fabelo-v2-render-<slug>` branch; `v2/tools/render.sh` sees `scribble2.js`
     and runs this pipeline, then the workflow commits `final.mp4` and `qc/` back to the branch. To fix one span, re-record only it with `--start/--end` and splice it in by frame number.

`examples/meet-scribble/` is the approved 40 s test film: walk in, wave, phone, night on the bed, looking up, a jump, and an end card.
