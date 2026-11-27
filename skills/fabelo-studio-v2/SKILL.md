---
name: "fabelo-studio-v2"
description: "Use when Rakib asks for a Fabelo Studio Version 2 (v2) video or a professional, pro-level Scribble video with pro animation, camera, transitions, sound and finishing. Two characters: Classic Scribble or Smooth Scribble; always ask which one first."
---

# Fabelo Studio Version 2: professional Scribble films from a prompt

Fabelo Studio is Rakib's animated YouTube channel for a US audience, in English.
It has TWO main characters and Rakib picks one for every video (section 0):
- **Classic Scribble**: an ink stick figure with a red scarf on warm paper.
- **Smooth Scribble**: the thumbnail-style Scribble with a big shaded head, a smooth black body and a puffy knitted red scarf (`fabelo/s2/`).

Version 2 keeps Classic Scribble and the whole Fabelo look exactly as in Version 1, and adds the craft of a
professional studio around him:
- pro animation;
- camera and editing;
- transitions;
- sound design and mixing;
- picture finishing;
- Shorts captions;
- quality control.

Version 1 (the `fabelo-studio` skill and its files) stays as it is. Never change it from this skill.

Everything lives in his private GitHub repo:
- Repo: `rakibul3790/auto-yt-studio`
- Branch: `main`

| Path | What it is |
|---|---|
| `fabelo/lib/scribble.js` | The character library (v1). Use it read-only. It is the ONLY way to draw Scribble. |
| `fabelo/v2/lib/fabelo2.js` | The v2 engine: films, shots, camera, transitions, captions, pro motion. |
| `fabelo/v2/tools/` | voices.py, preview.js, build2.py, record2.js, mix.py, finish.py, qc.js, render.sh |
| `fabelo/v2/templates/` | Starter `film.src.html` and `film.audio.json`. |
| `fabelo/v2/examples/plane/` | "Learn the Wind", a 44 s reference Short. |
| `.github/workflows/render-fabelo-v2.yml` | Cloud render. It never uploads. |
| `fabelo/s2/` | Smooth Scribble kit: `lib/scribble2.js` (character), `lib/sets2.js` (sets, night light, captions), `tools/` (emo_voice.py, build_s2.py, preview_s2.js, render_s2.sh), `templates/`, `examples/meet-scribble/`, `sheets/` (approved model sheets). |

**Language:**
- Talk to Rakib in Bengali.
- Everything in the video is in English: titles, on-screen text, captions and voices.

## 0. FIRST message: which character? (long videos AND Shorts)

Fabelo Studio has **two** main characters. Whenever Rakib asks you to make anything (a film, a Short, an explainer, a test), your FIRST reply asks which one, in Bengali, and you wait for the answer. Use AskUserQuestion when it is available:

1. **Classic Scribble:** the ink line stick figure with the tuft and the thin red scarf. Library `fabelo/lib/scribble.js`; build with the classic workflow in this skill.
2. **Smooth Scribble (new, thumbnail style):** big shaded white head, smooth solid black body, puffy knitted red scarf with fringe. Library `fabelo/s2/lib/scribble2.js`; kit and workflow in `fabelo/s2/README.md`.

- Skip the question only when the request already names the character ("Smooth দিয়ে বানাও", "Classic Scribble").
- After the pick, write the full A–Z script as Markdown (`SCRIPT.md` in the project folder, and show it in chat): logline, character, cast and voices with the emotion of each line, then a scene-by-scene table (time, action, camera 🎥, line, SFX 🔊, music 🎵). Then build the video with the chosen character, following the production rules below.
- Never mix the two characters in one film unless Rakib asks. Smooth-style side characters use `scarf:false`.
- The same question and flow apply to Shorts (1080x1920).

## 0.1 Production rules (read before every video: long films AND Shorts)

Before anything else, read `fabelo/PRODUCTION_RULES.md` in the repo and follow it; it overrides older lines here where they differ.
- Stages with Rakib's OK at each: ideas, full A-Z script, raw cut, full-frame QC (1 fps + close-up crops, 16:9 and 9:16), review, full edit, 1080p review, then 4K (`--w 3840 --h 2160 --scale 2`, at most 3 workers on 15 GB RAM), Shorts, thumbnail and EN/BN SRT. Projects live in `F:\video for yt\Fabelo Studio\Project File N\` (MindBlip videos: `F:\video for yt\MindBlip\`; keep big renders and scratch files off the C drive) (never touch `Project 2`).
- Voices: ask first. ElevenLabs **Eleven v3** only with consent; otherwise the free model (Kokoro).
- Mood on every line, free or paid, natural and never over-acted (v3 audio tags; for Kokoro use per-line speed/pitch/pauses/processing and breath sounds). Best of 3 takes.
- Upload: long videos are saved to the output folder only and uploaded only when Rakib says so; Shorts go up straight away as **Public** after QC. `ready-fabelo` uploads are Public by default (`"privacy": "private"` in the JSON makes one Private).

## 1. Get the kit (every new chat)

1. Call `add_repo` with owner `rakibul3790` and repo `auto-yt-studio`. Use `access: "push"`; you push render branches, and uploads when he asks.
2. Clone the repo and run the setup:
   ```bash
   git clone https://github.com/rakibul3790/auto-yt-studio ~/ays
   cd ~/ays/fabelo
   bash tools/setup.sh && source .env.sh
   ```
   `setup.sh` is the v1 setup. It installs kokoro-onnx, downloads the Kokoro models (about 120 MB), installs puppeteer-core and finds Chrome. It is safe to re-run.
3. If the repo can't be reached, tell Rakib in one line and stop. Never invent a look-alike character.
4. Read these before writing a scene:
   - `fabelo/CHARACTER.md`: the canon.
   - `fabelo/API.md`: the v1 library reference.
   - `fabelo/v2/README.md`: the v2 engine and tools.
   - `fabelo/v2/templates/film.src.html`
   - `fabelo/v2/examples/plane/film.src.html`
   - Smooth Scribble instead: `fabelo/s2/README.md`, `fabelo/s2/templates/film.src.html`, `fabelo/s2/examples/meet-scribble/film.src.html`, and look at `fabelo/s2/sheets/*.png`.
5. If `CHROME_PATH` is empty after setup, don't install a browser some other way. Record in the cloud instead (step 4.7).

## 2. Character lock: Classic Scribble (same as Version 1)

**Locked:**
- Ink `#1B1B1B` stick figure with stroke 7.
- Round paper-white head, dot eyes, small brows, a one-line mouth.
- The single curl `tuft` hair.
- The red scarf `#E63946`, always on. Red is the channel's only accent colour.
- Warm paper `#FBF7EE` background.
- Rig proportions from `Scribble.RIG`.

**Can change (outer changes only):**
- Costumes, worn on top of him. The scarf stays visible.
- Held props, poses, expressions.
- Scale, position, facing, rotation.
- Scene tint or lighting overlays.
- Register new costumes, props or poses with `Scribble.registerCostume / registerProp / registerPose` inside the scene file.

**Never:**
- Recolour the scarf or Scribble himself.
- Add a nose, ears, fingers or anime eyes.
- Use a 3D or realistic style.
- Give any other character a red scarf.
- Draw Scribble by hand or in any file other than `fabelo/lib/scribble.js`.

Side characters use `scarf:false` and a different hair style (`none bun long spiky bald`) or a costume.

**The v2 finishing must not change his colours either.** The grades in `finish.py` are built to keep the ink, the scarf and the paper within a few RGB steps. Don't add stronger grades or colour filters.

**Library names (v1.1):**
- Poses: idle wave point pointUp explain shrug shocked think sad cheer facepalm sit write carry scared hold crouch victory pray lie sitUp
- Expressions: neutral happy shocked sad angry thinking smirk scared sleepy excited confused proud calm
- Costumes: caveman peasant knight egyptian roman scientist office king explorer graduate
- Props: campfire spear torch tree hut rock book scroll lightbulb question exclaim clock coin phone sun cloud arrow heart pyramid castle house stool sign money globe
- Holdable props: spear torch book scroll phone lightbulb coin money heart globe clock
- Hair styles: tuft none bun long spiky bald
- Extras: `rotateTo(at,dur,deg)`, `anchor:'hip'` (for lying or sitting), `custom(fn,'back'|'front')` for anything else.

### 2.1 Character lock: Smooth Scribble

The full canon is in `fabelo/s2/README.md` §1 (approved by Rakib on 2026-11-26, proportions "B"). In short:
- Draw him ONLY with `Scribble2.draw` / `Scribble2.head` from `fabelo/s2/lib/scribble2.js`. Never hand-draw or restyle him.
- Locked: big shaded white round head with a clean outline; tall oval eyes, thin brows, one-line mouth; solid black tapered body with mitten hands and small shoes; puffy two-roll red knitted scarf with fringe, always on.
- Never: nose, ears, hair, fingers, recolouring, a scarf on side characters (`scarf:false`), mixing him with Classic Scribble in one film.
- Staging: raised arms stay outside the head (wave `a2:[100,48±15]`); hand-to-face poses use `over`; crouches in q/side view, not front; turn side → q → front; night scenes use `S2.night` after the figure.

## 3. Pick the format from the prompt (same as Version 1)

**A. Emotional short** (Day One Films style, 30–140 s, 9:16 or 16:9)
- Scribble NEVER speaks. He acts through pose, expression and timing.
- Others speak:
  - narrator: `af_heart`
  - mentor or grandpa: `am_onyx`, -2 st, `warm`
  - inner critic or imagination: `am_fenrir`, -6 st, `demon`. Draw it as an ink-blob shadow with red eyes.
  - minor roles: `af_bella`, `am_puck`
- Story arc: hook in the first 3 s → struggle → the lowest moment (rain, night tint, drone) → a turn (a mentor or a realisation) → triumph → a tender ending with one line of meaning.
- The music follows the arc: sparse → dark → warm → build → triumph → tender.

**B. Explainer** (Ink Explainer style, 2–10 min, 16:9)
- Scribble is the guide. The narrator voice is his voice (`am_michael` or `af_heart`). Use `talk(t0,t1)` exactly during his lines.
- Costumes change for each era or topic. Show handwritten key words.
- Verify every fact with a web search first. Hook in the first 5 s.

If the prompt is unclear about format, length or aspect ratio, pick the best fit and say which you picked.

**Defaults:**
- Shorts: 1080x1920 at 30 fps.
- Long videos: 1920x1080 at 30 fps.
- 4K only when Rakib asks: `--scale 2` with the same layout.

## 4. Build (Version 2 workflow)

Work in `fabelo/work/<slug>/`. Start from `v2/templates/` (Classic) or `s2/templates/` (Smooth).

### 4.0 Smooth Scribble: use the s2 workflow

For Smooth Scribble, skip the Fabelo2 engine steps (4.2–4.4, 4.6–4.7) and follow `fabelo/s2/README.md` §4. The sound spec, the QC and the delivery rules below stay the same.
```bash
python3 s2/tools/emo_voice.py --spec work/<slug>/film.audio.json --models "$FABELO_MODELS" --out work/<slug>/voice   # free Kokoro, emotion-shaped
python3 s2/tools/build_s2.py work/<slug>/film.src.html work/<slug>/film.html --timing work/<slug>/voice/timing.json
node s2/tools/preview_s2.js work/<slug>/film.html work/<slug>/prev.png "1,3,5,8" --w 1920 --h 1080   # Shorts: --w 1080 --h 1920
bash s2/tools/render_s2.sh work/<slug> --w 1920 --h 1080 --fps 30 --blur 2 --workers 3
```
- Time every action to `voice/timing.json`. Write positions from the stage `{W, H, GY}` so one file renders 16:9 and 9:16.
- Shorts always get `S2.caption(...)` word-by-word captions.
- ElevenLabs v3 only if Rakib says yes; then write its line files and a matching `timing.json` in the same `voice/` format.

### 4.1 Script and audio spec first

Write `film.audio.json` with `voices` and `lines`. A line's end may be `null`.

### 4.2 Voices FIRST: the animatic lock

```bash
python3 v2/tools/voices.py --spec work/<slug>/film.audio.json --models "$FABELO_MODELS" --out work/<slug>/voice
```

This prints each line's real start and end and writes `voice/timing.json` with word times. Copy the real times into `LINES` in the scene and time every action and cut to them. Never time a scene to guessed lengths.

### 4.3 Scene (`film.src.html`)

Build it as shots on the beat grid:
```js
const film = Fabelo2.film(document.body, { duration, bpm, fadeIn, fadeOut });
const s = film.shot(t0, t1, { frame: [cx, cy, w, h] });
// ... then film.cut(at, type), film.captions(LINES), film.ready(LINES)
```

The v2 craft rules:

- **Animation.** `shot.character()` turns on pro motion: overshoot and settle, follow-through on the forearms and scarf, anticipation, breathing.
  - Give every big action an anticipation pose (windup), a fast action (0.12–0.2 s) and a settle.
  - Hold key poses long enough to read (at least 0.4 s).
  - Use the v2 easings (`quintOut`, `expoOut`, `backOut`, `settle`, `sineInOut`) instead of linear moves.
- **Camera and editing.**
  - Every shot has a camera box `[cx, cy, w, h]`. It is fitted to every aspect ratio, so keep everything important inside it.
  - Vary shot sizes: wide to set the place, medium for action, close-up for emotion.
  - Use slow push-ins for feeling, `follow` for movement, a short `shake` for impacts and a light `handheld` for tension.
  - Zooms must glide, never shake. Give every push-in or reframe `sineInOut` (or the default) and at least 0.8 s.
    Keep `quintOut` / `expoOut` snap zooms and `shake` for impacts only, and don't start a new camera move on top of a running one.
    The engine writes camera moves at full precision; check a zoom frame by frame in preview before rendering if it looks stepped.
  - Add parallax with `shot.layer(depth, fn)`: depth < 1 is far away, and > 1 is a blurred foreground. Keep a foreground layer below the caption area.
  - Cut on the beat with `film.beat(n)`. Cut on action, and keep most shots 2–6 s long.
- **Transitions.** Pick one for a reason, not for decoration:
  - `cut` (default), `smash` (shock)
  - `whip` (energy, time jump), `page` (next day or chapter)
  - `ink` (a mood change, the dark moment)
  - `iris` (an ending or a focus)
  - `dip` (time passing), `dissolve` (soft memory)
  - `match` (link two shapes or moments, with `from`/`to` screen points)
  - Use at most one showy transition every 8–10 s. Each one gets its sound automatically.
- **Sound cues.** Put `film.cue('sfx', t, { name, gain, pan })` on every action: swish on throws, thump_soft on landings, paper_fold, flap, plane_fly, pluck(note), chime, impact, and so on.
- **Shorts captions.** Use `film.captions(LINES, { speakers: [...] })` for every Short. They show word by word, with the spoken word in red, and stay inside the frame at every ratio.
- **Responsive at every ratio.** Every scene must work at 16:9, 9:16 and 1:1 with nothing important cut off. It must fade or scale in at the start and fade out at the end; `fadeIn`/`fadeOut` handle that.

### 4.4 Preview without a browser (fast, approximate)

```bash
node v2/tools/preview.js work/<slug>/film.src.html work/<slug>/prev "1,3,5,8,..." --timing work/<slug>/voice/timing.json --sheet
```

- It writes `sheet_9x16.png`, `sheet_16x9.png` and `sheet_1x1.png`. Look at all three.
- Fix anything that is cut off, overlapping (captions over the ground, titles over clouds) or hidden before recording.

### 4.5 Sound spec

Complete `film.audio.json`. The format is in the header of `v2/tools/mix.py`.

- **sfx:** extra sounds that are not scene cues.
- **beds:** roomtone, rain, wind, birds, crickets, drone, heartbeat and so on, with start and end times.
- **music:** sections that follow the arc on the same bpm as the scene, plus `hits` (a riser ending on the triumph, a swell into the turn, a boom).
- **mix:** `duck_db` 9, `bed_duck_db` 4 by default.

### 4.6 Render locally (when Chrome is available)

```bash
bash v2/tools/render.sh work/<slug> --w 1080 --h 1920 --fps 30 --blur 4
```

This runs voices → build2 → record2 → mix → finish → qc.
- `record2.js` adds real motion blur (4 sub-frames, 180° shutter, never across a hard cut), parallel workers and `--scale 2` for 4K.
- `finish.py` adds a light paper texture, a brand-safe grade, fine grain and a soft vignette. It encodes at x264 slow crf 15 and normalises to -14 LUFS with true peak -1 dBTP.
- Optional finish settings go in `work/<slug>/FINISH`, for example `--grade warm --size 2160x3840`.

### 4.7 Render in the cloud (no Chrome here)

1. Put `film.src.html`, `film.audio.json` and a `RENDER` file in `fabelo/v2/renders/<slug>/`. The `RENDER` file holds the record options, for example `--w 1080 --h 1920 --fps 30 --blur 4`.
2. Commit to a new branch `fabelo-v2-render-<slug>` and push. Don't push the render folder to `main`.
3. The workflow **Render Fabelo v2 film** renders it and commits `final.mp4`, `timing.json`, `finish.json` and `qc/` back to that branch.
4. Watch it via `https://api.github.com/repos/rakibul3790/auto-yt-studio/actions/runs?branch=fabelo-v2-render-<slug>`. Keep polling in the same turn until it finishes; don't end the turn while it is pending.
5. Pull the branch when it finishes. It never uploads anything.

### 4.8 Thumbnail (optional)

1280x720. Scribble big, 2–4 bold words, red as the only accent colour.

## 5. Quality control before delivery

Open `qc/report.md` and look at `qc/sheet_16x9.png`, `qc/sheet_9x16.png` and `qc/sheet_1x1.png`.

QC passes only when:
- nothing is cut off at any ratio;
- the film fades in and out;
- loudness is -14 LUFS ±1 and the true peak is at most -1 dBTP;
- the file length matches the film.

Also check by eye:
- Scribble on model in every frame.
- The red scarf visible.
- Captions readable and not covering his face.
- Cuts landing on the beat.
- No shot that reads as a mistake (half a character at an edge, an empty frame).

If QC finds problems, fix the scene and render again before delivering.

## 6. Deliver

- Send `final.mp4` (and the thumbnail) to Rakib.
- Always state the exact video duration in seconds, from ffprobe or `finish.json`.
- End with a ✅ line confirming the scene is responsive at every ratio (16:9, 9:16, 1:1). Only say it when the QC frames show it.
- Upload to the **Fabelo Studio** channel (Public by default): long videos ONLY when Rakib asks; Shorts automatically after QC:
  1. Copy `final.mp4` and `thumb.jpg` into `ready-fabelo/<slug>.mp4` and `ready-fabelo/<slug>.jpg` on `main`.
  2. Write `ready-fabelo/<slug>.json`: `{video, title, description, tags, category_id, thumbnail}`.
     - `category_id`: `"1"` (Film & Animation) for emotional shorts, `"27"` (Education) for explainers.
     - Title, description and tags are SEO-written for a US audience.
  3. Commit and push to `main`. The workflow **Upload Fabelo Studio video** (`.github/workflows/upload-fabelo.yml`) uploads it (Public unless the JSON says "privacy": "private") with the `FABELO_YT_REFRESH_TOKEN` secret.
  4. Watch the run through `https://api.github.com/repos/rakibul3790/auto-yt-studio/actions/runs`.
  5. When it finishes, read the YouTube link written back into the JSON and give Rakib the link.
  - If the run fails with "FABELO_YT_REFRESH_TOKEN secret is missing", tell him to do the one-time setup in the README section "Fabelo Studio চ্যানেল".
- NEVER put a Fabelo Studio video in `ready/`. That folder uploads to his MindBlip channel.
- Never make a video Public or Unlisted from this skill.
- Never ask for secret values or show them in chat. They live only in GitHub Secrets.
- Never sign in to his accounts without asking first.
- Improve v2 only inside `fabelo/v2/` (engine, tools, templates). Commit those improvements to `main` so every future v2 film gets them. A new pose, prop or costume for Scribble goes into the scene file with `register…`, not into `fabelo/lib/`, unless Rakib asks to update the v1 library.