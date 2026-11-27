# Fabelo Studio v2

Professional-grade Scribble films. Same character, same look: v2 only adds the craft around him.
Scribble is still drawn ONLY by `fabelo/lib/scribble.js` (v1, untouched). v2 imports it read-only.

| Area | What v2 adds |
|---|---|
| Animation | richer easing, overshoot and settle on every pose change, follow-through on arms and scarf, anticipation, breathing (`Fabelo2.enhance`, on by default for `shot.character()`) |
| Camera and editing | shots with an aspect-aware camera box (push-in, pan, follow, tilt, shake, handheld), parallax layers, cuts on the music beat (`film.beat(n)`) |
| Transitions | cut, smash, dissolve, dip, whip pan, iris, ink splash, page turn, match cut (`film.cut(at, type)`), each with its own sound |
| Sound | voices first (real line lengths, word times), stereo mix with reverb sends, layered and varied SFX, rain/wind/birds/room-tone beds, widened score with risers, sidechain ducking, two-pass -14 LUFS / -1 dBTP |
| Picture | real motion blur (sub-frame averaging), paper texture, brand-safe grade, film grain, soft vignette, x264 slow crf 15, optional 4K |
| Shorts | animated word-by-word English captions, the spoken word in red (`film.captions`) |
| QC | every shot and transition checked at 16:9, 9:16 and 1:1 in Chrome (nothing half cut off, fades in and out), contact sheets, loudness report |

## Files

```
v2/lib/fabelo2.js          engine: Film, Shot, Camera, transitions, captions, pro motion, bg helpers
v2/tools/voices.py         1. voices first → voice/line_XX.wav + timing.json (word times)
v2/tools/preview.js        quick layout check without a browser (SVG → PNG, contact sheets, --cues)
v2/tools/build2.py         2. self-contained film.html (inlines scribble.js, fabelo2.js, font, timing)
v2/tools/record2.js        3. frame-exact master with motion blur, parallel workers, --scale 2 for 4K, writes cues.json
v2/tools/mix.py            4. stereo mix (+ --stems)
v2/tools/finish.py         5. paper, grade, grain, vignette, encode, loudness → final.mp4 + report
v2/tools/qc.js             6. QC at 16:9, 9:16, 1:1 + audio measurement → qc/report.md
v2/tools/render.sh         runs 1–6 in order for one folder
v2/templates/              starter film.src.html + film.audio.json
v2/examples/plane/         "Learn the Wind", a 44 s test Short
v2/renders/<slug>/         cloud renders (see renders/README.md)
.github/workflows/render-fabelo-v2.yml   cloud render on a fabelo-v2-render-* branch; never uploads
```

## Workflow

```bash
bash tools/setup.sh && source .env.sh                      # v1 setup: Kokoro models, puppeteer-core, Chrome
mkdir -p work/myfilm && cp v2/templates/* work/myfilm/      # write the script in film.audio.json
python3 v2/tools/voices.py --spec work/myfilm/film.audio.json --models "$FABELO_MODELS" --out work/myfilm/voice
#   → copy the printed start/end times into LINES in film.src.html and time the shots to them
node v2/tools/preview.js work/myfilm/film.src.html work/myfilm/prev "1,3,5,8" --timing work/myfilm/voice/timing.json --sheet
bash v2/tools/render.sh work/myfilm --w 1080 --h 1920 --fps 30 --blur 4
```

No Chrome on the machine? Put the folder in `v2/renders/<slug>/` with a `RENDER` file and push it to a
`fabelo-v2-render-<slug>` branch: GitHub Actions renders it and commits `final.mp4` and `qc/` back.

## Scene API in one screen

```js
const film = Fabelo2.film(document.body, { duration: 44, bpm: 72, fadeIn: 1.0, fadeOut: 1.6 });
const B = (n) => film.beat(n);
const s1 = film.shot(0, B(8), { name: 'desk', frame: [cx, cy, w, h], handheld: 0.5 });
s1.layer(0.4, (t, view) => Fabelo2.bg.hills(view, {...}));      // depth < 1 = far, > 1 = foreground (blur option)
const k = s1.character({ x, y, scale, pose, expr, hold });       // a Scribble character, pro motion on
k.pose(t, 'throw', { dur: 0.16 }).expr(t, 'excited').look(t, [dx, dy]);
s1.prop(name, {...}); s1.custom(fn, 'back'|'front'); s1.tint(at, dur, color, opacity);
s1.cam.push(at, dur, 1.2, [x, y]).frame(at, dur, [cx, cy, w, h], 'quintOut').follow(t0, t1, k).shake(at, 0.3, 10);
film.cut(B(8), 'ink', { center: [x, y] });                        // cut smash dissolve dip whip iris ink page match
film.cue('sfx', t, { name: 'swish', gain: 0.4, pan: 0.2 });       // sound cue → mix.py
film.title('Learn the wind.', { at, until, y: -380 });
film.captions(LINES, { speakers: ['narrator'] });
film.ready(LINES);
```

Smooth camera: zoom and pan are written to the SVG with 5-decimal precision (never the 0.01 rounding used
for drawing, which made slow push-ins jump in visible steps), zoom moves in log space, `inOut` / `quintInOut`
camera moves are swapped for easings with continuous acceleration, a move added while another is running
continues from the current framing instead of snapping, and `handheld` is a slow two-octave drift that calms
down while the camera zooms. For a clean zoom prefer `sineInOut` and at least 0.8 s; keep `quintOut`/`expoOut`
snap zooms for impacts only.


Keep what matters inside each shot's camera box: the box is fitted to every aspect ratio.
