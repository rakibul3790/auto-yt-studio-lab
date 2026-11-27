---
name: "fabelo-studio"
description: "Use when Rakib asks for a Fabelo Studio video, a Scribble video, or any animated explainer or emotional short from a prompt. Two main characters: Classic Scribble (ink stick figure) or Smooth Scribble (thumbnail style); always ask which one first."
---

# Fabelo Studio: make a Scribble video from a prompt

Fabelo Studio is Rakib's animated YouTube channel for a US audience, in English.
It has TWO main characters and Rakib picks one for every video (section 0):
- **Classic Scribble**: an ink stick figure with a red scarf on warm paper.
- **Smooth Scribble**: the thumbnail-style Scribble with a big shaded head, a smooth black body and a puffy knitted red scarf (`fabelo/s2/`).

The characters, the engine and the tools all live in his private GitHub repo:
- Repo: `rakibul3790/auto-yt-studio`
- Branch: `main`
- Folder: `fabelo/`

Never redraw either character by hand. Classic Scribble is rendered only with `fabelo/lib/scribble.js`, Smooth Scribble only with `fabelo/s2/lib/scribble2.js`, so each looks identical in every video.

## 0. FIRST message: which character? (long videos AND Shorts)

Fabelo Studio has **two** main characters. Whenever Rakib asks you to make anything (a film, a Short, an explainer, a test), your FIRST reply asks which one, in Bengali, and you wait for the answer. Use AskUserQuestion when it is available:

1. **Classic Scribble:** the ink line stick figure with the tuft and the thin red scarf. Library `fabelo/lib/scribble.js`; build with the classic workflow in this skill.
2. **Smooth Scribble (new, thumbnail style):** big shaded white head, smooth solid black body, puffy knitted red scarf with fringe. Library `fabelo/s2/lib/scribble2.js`; kit and workflow in `fabelo/s2/README.md`.

- Skip the question only when the request already names the character ("Smooth দিয়ে বানাও", "Classic Scribble").
- After the pick, write the full A–Z script as Markdown (`SCRIPT.md` in the project folder, and show it in chat): logline, character, cast and voices with the emotion of each line, then a scene-by-scene table (time, action, camera 🎥, line, SFX 🔊, music 🎵). Then build the video with the chosen character, following the production rules below.
- Never mix the two characters in one film unless Rakib asks. Smooth-style side characters use `scarf:false`.
- The same question and flow apply to Shorts (1080x1920).

## 0.1 Production rules (read before every video: long films AND Shorts)

Before anything else, read `fabelo/PRODUCTION_RULES.md` in the repo and follow it. It overrides older lines in this skill wherever they differ. In short:
- **Stages, each needs Rakib's OK:** ideas, then a full A-Z script, then a raw cut (locked camera), then a full-frame QC by you (one frame per second plus close-up crops, at 16:9 and 9:16), then Rakib's review, then the full edit (camera, meaningful transitions, typography with word-by-word captions and sparse red keyword underlines, flashback, end card, grade/paper/grain), then a 1080p review copy, then 4K (`--w 3840 --h 2160 --scale 2`, at most 3 workers on 15 GB RAM), Shorts, thumbnail and EN/BN SRT. Each project lives in `F:\video for yt\Fabelo Studio\Project File N\` (MindBlip videos: `F:\video for yt\MindBlip\`; keep big renders and scratch files off the C drive) (never touch `Project 2`).
- **Voices:** ask at the start whether to use ElevenLabs. Yes means ElevenLabs **Eleven v3** (voices + SFX). No, or no answer, means the free model (Kokoro + synthesized SFX). Never use ElevenLabs without consent.
- **Mood on every line, free or paid:** natural and never over-acted (soft laughs, restrained anger, a slightly heavy voice in sad moments). v3 uses audio tags where the feeling changes. Kokoro uses per-line speed, pitch, pauses, warm/soft processing and breath/sigh sounds. Pick the best of 3 takes.
- **Staging lessons:** realistic prop grips (phone in front of the chest, screen toward the face); people enter and leave from off screen; people outside a window are drawn inside the window clip; no overlapping bodies; gestures never hidden by the face or long hair; light glows use the overlay blend (never screen).
- **Upload:** long videos are only saved to the project's output folder and are uploaded ONLY when Rakib says so. Shorts are uploaded straight away as **Public** after a full QC. `ready-fabelo` uploads are Public by default (the JSON `"privacy": "private"` makes one Private).

**Language:**
- Talk to Rakib in Bengali.
- Everything in the video is in English: titles, on-screen text and voices.

## 1. Get the kit (every new chat)

1. Call `add_repo` with owner `rakibul3790` and repo `auto-yt-studio`. Use `access: "read"`, or `"push"` if you will upload.
2. Clone the `main` branch:
   ```bash
   git clone https://github.com/rakibul3790/auto-yt-studio ~/ays
   cd ~/ays/fabelo
   bash tools/setup.sh && source .env.sh
   ```
   `setup.sh` installs kokoro-onnx, downloads the Kokoro TTS models (about 120 MB, from GitHub releases), installs puppeteer-core and finds Chrome. It is safe to re-run.
3. If the repo can't be reached, tell Rakib in one line and stop. Do not invent a look-alike character.
4. Read these before writing a scene:
   - `CHARACTER.md`: the canon.
   - `API.md`: the library reference.
   - `templates/scene.src.html`: the starter scene.
   - For emotional shorts, also `examples/stand/stand.src.html`.
   - For explainers, also `examples/night/night.src.html`.
   - Smooth Scribble instead: `s2/README.md` (canon, API, workflow), `s2/templates/`, `s2/examples/meet-scribble/`, and look at `s2/sheets/*.png`.

## 2. Character lock: Classic Scribble (never break this)

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

Side characters use `scarf:false` and a different hair style (`none bun long spiky bald`) or a costume.

**Library names (v1.1):**
- Poses: idle wave point pointUp explain shrug shocked think sad cheer facepalm sit write carry scared hold crouch victory pray lie sitUp
- Expressions: neutral happy shocked sad angry thinking smirk scared sleepy excited confused proud calm
- Costumes: caveman peasant knight egyptian roman scientist office king explorer graduate
- Props: campfire spear torch tree hut rock book scroll lightbulb question exclaim clock coin phone sun cloud arrow heart pyramid castle house stool sign money globe
- Holdable props: spear torch book scroll phone lightbulb coin money heart globe clock
- Hair styles: tuft none bun long spiky bald
- Extras: `rotateTo(at,dur,deg)`, `anchor:'hip'` (for lying or sitting in bed), `sc.custom(fn,'back'|'front')` for anything else (shadows, rain, tints).

### 2.1 Character lock: Smooth Scribble

The canon is in `fabelo/s2/README.md` §1 (approved 2026-11-26, proportions "B").
- Draw him only with `Scribble2.draw` / `Scribble2.head`.
- Locked: big shaded white head with a clean outline, tall oval eyes, a solid black tapered body, mitten hands, and the puffy red knitted scarf with fringe, always on.
- Never: nose, ears, hair, fingers, recolouring, a scarf on side characters (`scarf:false`), mixing him with Classic Scribble.

## 3. Pick the format from the prompt

**A. Emotional short** (Day One Films style, 60–140 s, 16:9 or 9:16)
- Scribble NEVER speaks. He acts through pose, expression and timing.
- Others speak:
  - narrator: `af_heart`
  - mentor or grandpa: `am_onyx`, -2 st, `warm`
  - inner critic or imagination: `am_fenrir`, -6 st, `demon`. Draw it as an ink-blob shadow with red eyes, as in `examples/stand`.
  - minor roles: `af_bella`, `am_puck`
- Story arc: hook in the first 3 s → struggle → the lowest moment (rain, night tint, drone, heartbeat) → a turn (a mentor or a realisation) → triumph → a tender ending with one line of meaning.
- Place SFX deliberately on every action: crumple, steps, thud, whoosh, chime, riser, burst.
- The music follows the arc: sparse → dark → warm → build → tension → triumph → tender.

**B. Explainer** (Ink Explainer style, 2–10 min, 16:9)
- Scribble is the guide. The narrator voice is his voice (`am_michael` or `af_heart`).
- Use `s.talk(t0,t1)` exactly during his lines.
- Costumes change for each era or topic.
- Show handwritten key words with `sc.text`.
- Verify every fact with a web search first. Keep it curious and surprising, with a hook in the first 5 s.

If the prompt is unclear about format, length or aspect ratio, pick the best fit and say which you picked.

**Defaults:**
- Shorts: 1080x1920.
- Long videos: 1920x1080.

## 4. Build

Work in `fabelo/work/<slug>/`.

**Smooth Scribble:** use the s2 workflow in `fabelo/s2/README.md` §4 instead of steps 2–6 below: `s2/tools/emo_voice.py` (free emotional Kokoro voices) → `build_s2.py` → `preview_s2.js` → `render_s2.sh`. Shorts use `--w 1080 --h 1920` and `S2.caption` captions. Delivery (section 5) is the same.

**Classic Scribble:**

1. **Script.** Write the script as a `LINES` array of `[speaker, start, end, text]`. Plan timing at about 2.6 words per second for each line.
2. **Scene.** Copy `templates/scene.src.html` and write the scene.
   - Keep everything important inside the safe square [-500, 500]. Then it fits 16:9, 9:16, 1:1 and any other ratio with nothing cut off.
   - For Shorts-first videos, use a larger character `scale` (about 2.8–3.2) rather than placing things outside the square.
   - The scene must fade/scale in at the start and fade out at the end. `fadeIn`/`fadeOut` handle this.
3. **Self-contained HTML.**
   ```bash
   python3 tools/build.py work/<slug>/film.src.html work/<slug>/film.html
   ```
4. **Preview frames.** Screenshot `film.html?t=<sec>` at several key moments in BOTH 1280x720 and 540x960 (Playwright with `$CHROME_PATH`), and look at them. Fix anything that overlaps, is cut off or is hidden (arms behind the head and so on) before recording.
5. **Record.**
   ```bash
   node tools/record.js work/<slug>/film.html work/<slug>/silent.mp4 --w 1920 --h 1080 --fps 30 --chrome "$CHROME_PATH"
   ```
   Recording runs at about 13–14 frames per second at 1080p.
6. **Audio.** Write `film.audio.json`. The format is in the header of `tools/soundtrack.py`: voices, lines, sfx (with `every`/`until` for repeats), beds and music sections. Then run:
   ```bash
   python3 tools/soundtrack.py --spec work/<slug>/film.audio.json --video work/<slug>/silent.mp4 --models "$FABELO_MODELS" --out work/<slug>/final.mp4
   ```
   - If a line prints "longer than its slot", retime the scene and re-record.
   - The target is about -14 LUFS. The script prints the loudness.
7. **Thumbnail (optional).** 1280x720. Scribble big, 2–4 bold words, red as the only accent colour.

## 5. Deliver

- Send `final.mp4` (and the thumbnail) with SendUserFile.
- Always state the exact video duration in seconds.
- If you also give the HTML scene, end with a ✅ line confirming it is responsive at every ratio (16:9, 9:16, 1:1).
- Upload to the **Fabelo Studio** channel (Public by default): long videos ONLY when Rakib asks; Shorts automatically after QC:
  1. Copy `final.mp4` and `thumb.jpg` into `ready-fabelo/<slug>.mp4` and `ready-fabelo/<slug>.jpg`.
  2. Write `ready-fabelo/<slug>.json`: `{video, title, description, tags, category_id, thumbnail}`.
     - `category_id`: `"1"` (Film & Animation) for emotional shorts, `"27"` (Education) for explainers.
     - Title, description and tags are SEO-written for a US audience.
  3. Commit and push to `main`. The workflow **Upload Fabelo Studio video** (`.github/workflows/upload-fabelo.yml`) uploads it with the `FABELO_YT_REFRESH_TOKEN` secret.
  4. Watch the run through `https://api.github.com/repos/rakibul3790/auto-yt-studio/actions/runs`.
  5. When it finishes, read the YouTube link that was written back into the JSON, and give Rakib the link.
  - If the run fails with "FABELO_YT_REFRESH_TOKEN secret is missing", tell him to do the one-time setup in the README section "Fabelo Studio চ্যানেল".
- NEVER put a Fabelo Studio video in `ready/`. That folder uploads to his MindBlip channel.
- Never ask for secret values or show them in chat. They live only in GitHub Secrets.
- If you improve the library (a new pose, prop or costume), commit it to `fabelo/` on `main` so every future video gets it.