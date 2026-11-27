# Scribble — character library (v1.0)

One recurring character for the channel: **Scribble**, an ink stick figure with a red scarf on warm paper.
Every video is built from this same code. Everything on screen is a pure function of time, so a headless
browser can seek to any frame and record it exactly.

## Files

| File | What it is |
| --- | --- |
| `scribble.js` | The library: rig, poses, expressions, costumes, props, scene engine. No dependencies. |
| `demo.html` | 34-second demo that uses almost everything. Copy it as a starting point for each video. |
| `sheet.html` | Reference sheet: every pose, expression, costume and prop with its exact code name. |
| `record.js` | Records any scene page to MP4 (Puppeteer + ffmpeg), frame-accurate, any size. |

## Quick start

```html
<script src="scribble.js"></script>
<script>
  const sc = Scribble.createScene(document.body, { duration: 12 });   // seconds
  const s  = sc.character({ x: 0, scale: 2.3 });                      // Scribble

  s.drawOn(0.8, 1.5);                                  // ink draws itself
  s.pose(2.5, 'wave', { expr: 'happy' }).wave(2.5, 4.5).talk(2.6, 4.2);
  sc.text('What did ancient humans do all day?', { y: -400, size: 70, at: 1, until: 5 });

  s.costume(5, 'caveman').hold(5, 'spear').pose(5, 'hold', { expr: 'proud' });
  sc.prop('campfire', { x: -250, at: 5.5, draw: 0.8 });
  s.walk(7, 9.5, -120);                                // walks to x = -120
  s.face(9.6, 1).pose(9.6, 'sit', { expr: 'thinking' });

  sc.exposeForRecording();   // lets record.js drive it
  sc.play();
</script>
```

Open `demo.html` in a browser to watch. Add `?t=12.5` to the URL to freeze at 12.5 s.

## Coordinates (works on every screen ratio)

- The **safe area** is the square from **-500 to 500** on both x and y, centred on the screen.
- It is always fully visible on **16:9, 9:16, 1:1** or any other ratio. The paper extends beyond it on the longer side.
- Keep everything important inside that square: nothing is ever cut off.
- The floor is at `y = 300` by default (`ground` option). Text titles sit well at `y = -400`, labels at `y = 430`.
- A character at `scale: 2.3` is about 425 units tall.

## Scene

`Scribble.createScene(container, options)`

| Option | Default | Meaning |
| --- | --- | --- |
| `duration` | 10 | Length in seconds |
| `ground` | 300 | Floor y |
| `fadeIn` / `fadeOut` | 0.8 | Whole scene fades + scales in at the start and out at the end |
| `groundLine` | true | Sketchy floor line that draws itself |
| `wobble` | false | Slight hand-drawn wobble on all ink (looks nice, but makes recording about 3× slower) |
| `loop` | true | Loop when playing in a browser |

Methods: `character(o)`, `prop(name, o)`, `text(str, o)`, `custom(fn, layer)`, `play()`, `pause()`, `seek(t)`, `render(t)`, `exposeForRecording()`.

- `prop(name, { x, y, scale, at, draw, out, outDur, front, flip, opts })` — `draw` = seconds of draw-on (0 = pop in), `out` = time to fade away.
- `text(str, { x, y, size, at, until, write, color, weight })` — handwritten, writes itself on and fades out.
- `custom((t, scene) => svgString, 'back' | 'front')` — draw anything else; use `Scribble.svg` helpers so it can draw itself too.

## Character

`sc.character({ x, y, scale, facing, pose, expr, costume, hold, blink })`

All methods take a start time first and can be chained.

| Method | Example | Notes |
| --- | --- | --- |
| `pose(at, name, { expr, dur, tweak })` | `s.pose(3, 'point', { expr: 'happy' })` | Smooth blend, default 0.35 s |
| `expr(at, name)` | `s.expr(4, 'shocked')` | Switches the face |
| `talk(t0, t1)` | `s.talk(3, 6)` | Mouth moves with natural pauses |
| `wave(t0, t1)` | `s.wave(2, 4)` | Waving hand |
| `walk(t0, t1, toX)` / `run(t0, t1, toX)` | `s.walk(5, 8, 300)` | Legs, arms, scarf and facing are automatic |
| `face(at, 1 / -1)` | `s.face(9, -1)` | Turn right / left |
| `moveTo(at, dur, x, y)` | `s.moveTo(2, 1, 100)` | Slide (no walking) |
| `scaleTo(at, dur, s)` | `s.scaleTo(4, 0.6, 3)` | Zoom the character |
| `costume(at, name)` | `s.costume(5, 'knight')` | `null` removes it. A small "poof" pop plays |
| `hold(at, prop)` | `s.hold(5, 'torch')` | Prop in the right hand. `null` drops it |
| `look(at, [x, y])` | `s.look(3, [4, -3])` | Eye direction |
| `drawOn(at, dur)` | `s.drawOn(0.5, 1.5)` | Ink draws itself, then fills appear |
| `fade(at, dur, opacity)` | `s.fade(10, 0.5, 0)` | |

Blinking is automatic. Several characters can share a scene (for extras), and each blinks on its own rhythm.

## Names

**Poses (18):** idle, wave, point, pointUp, explain, shrug, shocked, think, sad, cheer, facepalm, sit, write, carry, scared, hold, crouch, victory

**Expressions (12):** neutral, happy, shocked, sad, angry, thinking, smirk, scared, sleepy, excited, confused, proud

**Costumes (10):** caveman, peasant, knight, egyptian, roman, scientist, office, king, explorer, graduate

**Props (25):** campfire, spear, torch, tree, hut, rock, book, scroll, lightbulb, question, exclaim, clock, coin, phone, sun, cloud, arrow, heart, pyramid, castle, house, stool, sign, money, globe

Props that can be held: spear, torch, book, scroll, phone, lightbulb, coin, money, heart, globe, clock.

Open `sheet.html` to see all of them.

## Adding your own

```js
Scribble.registerPose('dab', { lean: 8, head: 20, aL: [-100, -100], aR: [120, 150], lL: [-12, -14], lR: [12, 14] });
Scribble.registerExpression('wink', { eyes: 'dot', brows: { lift: 0, tilt: 0 }, mouth: 'smirk' });
Scribble.registerCostume('pirate', { head: '<path .../>', body: '<path .../>', hideHair: true });
Scribble.registerProp('anchor', (t) => Scribble.svg.path('M0 0 L0 -80', { w: 6 }), { s: 0.5, dx: 0, dy: 10, rot: 0 });
```

Pose angles are in degrees: 0 = straight down, 90 = toward screen right, 180 = straight up.
Arms are `[upper, lower]` relative to the torso, legs are `[thigh, shin]`. Hips adjust automatically
so the feet stay on the floor (sitting and crouching just work).

## Colours

Ink `#1B1B1B`, paper `#FBF7EE`, accent red `#E63946` (the scarf: the channel's only accent).
Ochre `#E9B44C` is only for fire, light and gold.

## Recording to video

```bash
npm i puppeteer
node record.js demo.html demo_16x9.mp4 --w 1920 --h 1080 --fps 30
node record.js demo.html demo_9x16.mp4 --w 1080 --h 1920 --fps 30   # Shorts
```

Needs `ffmpeg`. The recorder steps through every frame with `window.__seek(t)`, so timing is exact
even on a slow machine. Voiceover and music are added afterwards with ffmpeg.

**Fonts:** titles use the free Google font *Caveat*. When recording offline, install Caveat on the machine
(or self-host the font file next to the page), otherwise the browser falls back to a system font.
