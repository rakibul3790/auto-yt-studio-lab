# Fabelo Studio: "Why Your Mistakes Are Secretly Making You Smarter"

**Production bible for an 8-minute animated explainer with Scribble**

| | |
|---|---|
| **Length** | 480 s (8:00), including a 20 s end screen |
| **Format** | 16:9 at 1920×1080, 30 fps. Responsive: all key content stays inside the safe square [-500, 500] |
| **Style** | Fabelo ink: black ink on warm paper `#FBF7EE`. Red `#E63946` is used ONLY for Scribble's scarf and the "mistake" marks. Ochre `#E9B44C` is for light, gold and ideas |
| **Main character** | Scribble, rendered by `fabelo/lib/scribble.js`. In explainers he is the guide and **he talks**: the narrator voice is his voice, with `s.talk(t0, t1)` running during every line |
| **Audience** | US, 13–45, curious, self-improvement and psychology viewers |
| **Category** | 27 (Education) |
| **Channel callback** | Continues the theme of "Don't Throw Away Your Mistakes" (the paper-ball staircase and the ink-blob inner critic come back) |

---

## 1. Concept

**Logline:** Every mistake you make sends a tiny electric signal through your brain. Science says that signal, used right, is the fastest way to learn. Scribble walks through the brain science, a surprising "15% rule", three world-changing accidents, and a simple 3-step method. In the end, his old pile of crumpled mistakes turns into a staircase again.

**Promise in the first 30 s:** "By the end of this video, you'll know the exact percentage of mistakes that makes learning fastest, and how to use it."

### Retention plan

- **Hook at 0:00.** A baby falls over and over. The surprising number (17 falls an hour) appears on screen by 0:08.
- **Open loop.** The "15% rule" is teased at 0:25 but only paid off at 2:50. A second loop is "the mistake that saved millions", teased at 3:40 and paid off at 3:55.
- **A new visual idea every 20–40 s.** This could be a costume change, a new prop or a camera move (scaleTo, moveTo).
- **Chapter cards.** Each chapter opens with a handwritten title, 1.5 s on screen.
- **The inner critic returns at 5:30.** This is the emotional peak, followed by the payoff.
- **End screen (7:40–8:00).** Scribble points to two slots: the long film "Don't Throw Away Your Mistakes" and the Short "She Always Held the Umbrella".

### YouTube chapters (paste into the description)

```
0:00 Babies fall 17 times an hour
0:50 Your brain's "oops" signal
1:50 The 15% rule
2:50 Why confident mistakes stick
3:50 3 mistakes that changed the world
5:30 Why mistakes still hurt
6:40 How to use your mistakes
7:30 Stand on them
```

---

## 2. Voices, music and sound palette

| Role | Kokoro voice | Settings |
|---|---|---|
| Scribble / narrator (explainer guide) | `am_michael` | speed 0.92, room, gain 0.9 |
| Inner critic (5:30 scene) | `am_fenrir` | speed 0.84, -6 st, demon, gain 0.95 |
| Baby giggle | no voice | `pop` + `boing` SFX only |
| Little Alice (book scene) | `af_bella` | speed 1.05, +3 st, room, gain 0.8 |

**Music palette (`soundtrack.py` styles):**
- `sparse` for curiosity
- `warm` for discovery
- `build` before reveals
- `tension` for the critic
- `triumph` for payoffs
- `tender` for the ending

**Music level:** 0.045. It ducks under the voice automatically.

**Signature sounds:**

| Sound | When it plays | SFX |
|---|---|---|
| Ink draw-on | Every new prop | `scribble` (d 0.6–1.2) |
| Fact reveal | Every on-screen number | `ding` (f 1320) + `pop` |
| Mistake | Every red X | `boing` at low gain + `thud` |
| Idea | Every lightbulb | `chime` |
| Chapter card | Each chapter title | `whoosh` (d 0.6) + `scribble` (d 0.8) |
| Transition | Each scene change | `swoop` (d 0.8) or a crumple wipe (`crumple` + `whoosh`) |

**Transitions (built with `sc.custom`):**
1. **Ink wipe.** A thick black brush stroke sweeps left to right (0.5 s) and reveals the next scene.
2. **Paper flip.** The whole frame scales on X from 1 to 0 to 1 (0.4 s) with a `rustle`.
3. **Crumple wipe.** The frame shrinks into a paper ball that flies off screen. Used only twice, for emphasis.
4. **Zoom-through.** The camera scales into an object (the brain, a petri dish) and the next scene starts inside it.

---

## 3. New assets to register in the scene file

| Name | Type | Look |
|---|---|---|
| `baby` | character | `sc.character({ scale: 1.0, scarf: false, hair: 'tuft' })` with a round diaper body costume `baby` (white fill) |
| `brain` | prop | Two-lobe ink outline, wavy folds, light pink fill `#F6D6D6`. It can pulse with an `opts.glow` ochre halo |
| `spark` | custom | A zig-zag electric line travelling along a path (ochre). Used for the brain signal |
| `eegcap` | costume | A cap with dots and little wires, worn by a side character |
| `meter` | prop | A semicircle gauge from 0 to 100% with a needle. `opts.v` sets the needle |
| `dartboard` | prop | Three rings. A red dart shows an "error" |
| `petri` | prop | A shallow dish (ellipse) with dot colonies and a fuzzy ochre mold patch with a clear halo |
| `stickynote` | prop | A square note in ochre-yellow `#F3D36B`, slightly curled corner. **No brand names or logos** |
| `hymnal` | prop | A thick book with a note sticking out of the top |
| `manuscript` | prop | A stack of typed pages with a paperclip |
| `letter` | prop | An envelope with a red X "rejected" stamp |
| `paperball` | prop | Copy from `examples/stand` |
| `step` | prop | Copy from `examples/stand` |
| Critic blob | custom | Copy `criticSVG` from `examples/stand` (the ink shadow with red eyes) |
| `journal` | prop | A small notebook with the handwritten heading "MISTAKES I LEARNED FROM" |

---

## 4. Full script, scene by scene

Times are in seconds from the start (mm:ss in brackets).
- **VO:** narration, spoken by Scribble. Run `s.talk()` during it.
- **TXT:** on-screen handwritten text (`sc.text`).
- **SFX / MUSIC / TRANSITION:** what to add.

### SCENE 1: Cold open, "17 falls an hour" (0–30 s, 0:00–0:30)

| Time | Visual | VO / TXT | SFX / Music |
|---|---|---|---|
| 0.0–1.0 | The scene fades and scales in. Empty paper, the floor line draws itself | | Music `sparse` starts (Am F C G, 64 bpm, gain 0.8) |
| 1.0–4.0 | A **baby** (scale 1.0) at x=-200 stands up wobbling (rotateTo ±6°) and takes two steps, then falls (rotateTo 70°, anchor hip). Gets back up, falls again | | `step` ×2, `thud` 0.3 on each fall, `boing` 0.1 |
| 4.0–8.0 | The falls repeat faster (3 more). A tally counter in the top right counts 1…5 with each fall | VO 4.2–7.8: "This little human just fell five times in ten seconds." | `pop` on each tally |
| 8.0–12.0 | The counter flips to a big **17**. TXT "17 falls / hour" (size 90, y -330) | VO 8.4–11.8: "Scientists filmed toddlers learning to walk. They fell about seventeen times every hour." | `ding` 0.3 at 8.4, `scribble` 0.8 |
| 12.0–17.0 | The baby gets up a 6th time and walks across the screen successfully. **Scribble** walks in from the right (scale 2.3), sees it, and gives a `cheer` | VO 12.4–16.6: "And not one of them ever thought, 'I guess I'm just bad at walking.'" | `step` every 0.4 s |
| 17.0–25.0 | Scribble faces the camera, pose `explain`. Behind him a red X turns into a ladder rung (custom morph) | VO 17.4–24.6: "Somewhere along the way, we start treating mistakes like proof that we're failing. But your brain sees them very differently." | Music: `build` starts at 22 |
| 25.0–30.0 | Scribble pose `pointUp`. TXT "?% of mistakes = fastest learning" with the question mark pulsing in red | VO 25.2–29.6: "In fact, there's a number, a percentage of mistakes, that makes you learn fastest." | `riser` 0.8 at 28.6 |

**TRANSITION 29.6–30.4:** ink wipe, with `whoosh`.

### SCENE 2: Title + promise (30–50 s, 0:30–0:50)

| Time | Visual | VO / TXT | SFX / Music |
|---|---|---|---|
| 30.4–36.0 | Title writes itself: **"Why Your Mistakes Are Secretly Making You Smarter"** (size 72, two lines). Scribble sits on the word "Mistakes" (pose `sit`) | | `scribble` 1.4, `chime` at 34. Music `warm` (F C G Am) |
| 36.0–49.5 | Scribble hops off. Three icons draw in, one after another: a brain, a "%" sign, a lightbulb | VO 36.4–49.0: "By the end of this video, you'll know what your brain does in the quarter second after a mistake, the exact mistake rate that speeds up learning, and three accidents that changed the world. Let's go." | `pop` on each icon (37.8, 40.6, 43.4), `whoosh` at 49 |

**TRANSITION:** zoom-through into the brain icon (scaleTo ×6 over 0.6 s).

### SCENE 3: Chapter 1, "Your brain's 'oops' signal" (50–110 s, 0:50–1:50)

| Time | Visual | VO / TXT | SFX / Music |
|---|---|---|---|
| 50.0–52.0 | Chapter card "1 · The 'oops' signal" | | `whoosh` + `scribble` 0.8. Music `sparse` |
| 52.0–62.0 | Scribble (costume `scientist`) stands beside a big **brain** prop (scale 2.4, x 220). A volunteer (side character, hair `bun`, costume `eegcap`) sits on a stool, tapping a button | VO 52.4–61.6: "In 2011, researchers at Michigan State put caps on people's heads that record the brain's electrical activity, then gave them a boring task that's easy to mess up." | `click` every 0.7 s from 55–61 |
| 62.0–72.0 | The screen shows the letters "MMMMM" and "NNMNN". The volunteer gets one wrong: a red X, and the face goes `shocked` | VO 62.4–71.6: "Pick the middle letter. Again. And again. Until your mind drifts, and you get one wrong." | `boing` 0.15 + `thud` 0.2 at 67.2 |
| 72.0–86.0 | Zoom on the brain: **two sparks** fire. Spark 1 (small, red) is labelled "Oops!". Spark 2 (bigger, ochre) is labelled "Pay attention!". A timer shows "< 0.25 s" | VO 72.4–85.6: "Within a quarter of a second, the brain fires two quick signals. The first one basically says, 'Something went wrong.' The second says, 'I noticed. Pay attention.'" | `ding` 0.25 at 75, `ding` (f 1760) 0.25 at 80, `swoop` |
| 86.0–100.0 | Split screen. LEFT: a Scribble-sized figure with a small spark 2 (label "fixed mindset"). RIGHT: a big spark 2 (label "growth mindset"). The right figure's next answer gets a check mark | VO 86.4–99.6: "Here's the surprise: people who believed intelligence can grow had a stronger second signal, and they got more answers right right after a mistake." | `chime` at 97 |
| 100.0–110.0 | Scribble takes off the scientist costume (poof) and holds up a lightbulb | VO 100.4–109.4: "So a mistake isn't the end of learning. For a growth-minded brain, it's the moment learning switches on." | `poof`, `chime` 0.2. Music `warm` from 100 |

**TRANSITION:** paper flip, with `rustle`.

### SCENE 4: Chapter 2, "The 15% rule" (110–170 s, 1:50–2:50)

| Time | Visual | VO / TXT | SFX / Music |
|---|---|---|---|
| 110.0–112.0 | Chapter card "2 · The 15% rule" | | `whoosh` + `scribble` |
| 112.0–126.0 | Scribble at a **dartboard**. Throw 1: every dart hits the center (too easy) and he yawns (expr `sleepy`). Throw 2: the board is tiny and far away, every dart misses (expr `angry`) | VO 112.4–125.6: "Imagine practicing darts. If the board is huge and right in front of you, you never miss, and you learn nothing. If it's tiny and miles away, you always miss, and you learn nothing either." | `whoosh` (d 0.3) per throw, `wood` hits, `boing` misses |
| 126.0–140.0 | A **meter** prop appears, with the needle sweeping 0→100%. The sweet-spot arc between 80 and 90% glows ochre | VO 126.4–139.6: "In 2019, scientists asked exactly where the sweet spot is. Using learning machines and models of how animals learn, they found an answer." | `riser` 1.2 at 137.8 |
| 140.0–150.0 | The needle snaps to **85%**. TXT big "85% right" then "15% wrong" (the "15%" in red). Confetti of tiny ink dots | VO 140.4–149.6: "Learning was fastest when you get about eighty-five percent right, and about fifteen percent wrong." | `burst` 0.5 at 140.6, `ding` |
| 150.0–162.0 | Scribble pose `explain`. Three panels draw in: "too easy", "just right (85%)", "too hard". The middle one is circled | VO 150.4–161.6: "Not zero mistakes. Not constant failure. Just enough mistakes to keep your brain on the edge of what it can do." | `scribble` 0.6 per panel |
| 162.0–170.0 | Scribble winks (expr `smirk`) | VO 162.4–169.4: "Researchers think this mainly applies to simple skills, but the idea is powerful: if you never miss, you're not stretching." | Music `build` from 166 |

**TRANSITION:** ink wipe.

### SCENE 5: Chapter 3, "Why confident mistakes stick" (170–230 s, 2:50–3:50)

| Time | Visual | VO / TXT | SFX / Music |
|---|---|---|---|
| 170.0–172.0 | Chapter card "3 · The confident mistake" | | `whoosh` + `scribble` |
| 172.0–186.0 | A quiz-show set. Scribble (costume `office`) at a podium with a sign "100% SURE". A question card reads "What's the capital of Australia?" Scribble confidently writes "SYDNEY" | VO 172.4–185.6: "Quick quiz. You're absolutely sure you know the answer. You'd bet money on it." | `tick` every 0.5 s, `click` |
| 186.0–196.0 | A big red X stamps over "SYDNEY". The answer "CANBERRA" writes in. Scribble: expr `shocked`, pose `facepalm` | VO 186.4–195.6: "And you're wrong. It's embarrassing. It stings. But here's the weird part." | `thud` 0.4 + `boing` 0.15 at 186.6 |
| 196.0–214.0 | A side-by-side "memory" jar animation. "Low-confidence error" puts a small ball in a jar. "HIGH-confidence error" puts a big glowing ball in a jar that stays bright | VO 196.4–213.6: "Psychologists call it the hypercorrection effect. When people are surprised by being confidently wrong, they're actually more likely to remember the correct answer next time than when they were just guessing." | `chime` 0.18 at 206 |
| 214.0–230.0 | Scribble (normal again) taps his head and gives a thumbs-up pose (`cheer`). TXT "Surprise = memory" | VO 214.4–229.4: "The shock of being wrong grabs your attention, and attention is what writes things into memory. Being wrong out loud isn't the worst thing for learning. Sometimes it's the best." | `pop`, music `warm` from 220 |

**TRANSITION:** zoom-through into a petri dish that pops onto the screen at 229.

### SCENE 6: Chapter 4, "3 mistakes that changed the world" (230–330 s, 3:50–5:30)

| Time | Visual | VO / TXT | SFX / Music |
|---|---|---|---|
| 230.0–232.0 | Chapter card "4 · Mistakes that changed the world" | | `whoosh` + `scribble`. Music `warm` |
| **Story A: the messy lab (232–262)** | | | |
| 232.0–244.0 | 1928, London. TXT "London, 1928". A messy lab bench with stacked **petri** dishes. A scientist (side character, costume `scientist`, hair `none`, `scarf:false`) waves goodbye with a suitcase. A calendar flips 14 pages | VO 232.4–243.6: "London, 1928. Scientist Alexander Fleming leaves for a two-week holiday, with dishes of bacteria still sitting on his messy bench." | `rustle` for the calendar flips, `step` |
| 244.0–254.0 | He returns. One dish has a fuzzy ochre **mold** patch, with a clear empty ring around it where the bacteria died. The scientist leans in, expr `thinking` | VO 244.4–253.6: "When he gets back, one dish is ruined, contaminated by mold. But around the mold, the bacteria had died." | `chime` 0.2 at 249 |
| 254.0–262.0 | Zoom on the ring. TXT "penicillin" writes in. A tiny heart with a "millions of lives" label | VO 254.4–261.6: "That 'ruined' dish led to penicillin, the first antibiotic, which went on to save millions of lives." | `triumph` sting: `burst` 0.35 |
| **Story B: the glue that failed (262–296)** | | | |
| 262.0–274.0 | TXT "1968". A chemist (side character, hair `spiky`) tests a glue: papers stick, then peel off easily. Expr `sad`. A sign "FAILED: too weak" | VO 262.4–273.6: "In 1968, a chemist named Spencer Silver tries to make a super-strong adhesive, and accidentally makes a weak one that peels right off." | `rustle`, `boing` 0.1 |
| 274.0–286.0 | TXT "1974". A choir: a singer (side character, costume `graduate` robe) opens a **hymnal**, and paper bookmarks fall out (fly arcs). He gets an idea (lightbulb) | VO 274.4–285.6: "Years later, his colleague Art Fry keeps losing his paper bookmarks from his choir hymnal, and remembers the 'useless' glue." | Soft choir hum bed: strings section, `chime` at 283 |
| 286.0–296.0 | Yellow **sticky notes** multiply across the screen (pop-pop-pop) until they tile a whole wall. TXT "1980: in stores" | VO 286.4–295.6: "The failed glue became the sticky note, launched in stores in 1980. Today they're everywhere." | `pop` ×12 (every 0.25 s) |
| **Story C: twelve rejections (296–330)** | | | |
| 296.0–308.0 | A writer at a desk (side character, hair `long`) mails a **manuscript**. **Letters** come back one by one, each stamped with a red X, piling up: 1, 2, … 12 (a counter) | VO 296.4–307.6: "In the mid-1990s, a struggling writer sends out her first novel. Rejected. Rejected. Twelve publishers say no." | `pop` + small `thud` per letter (12×, every 0.6 s) |
| 308.0–320.0 | A publisher brings the pages home. His 8-year-old daughter (side character, scale 1.3, hair `bun`) reads, expr `excited`, and tugs his sleeve | VO 308.4–313.0: "Then a publisher takes a chapter home to his eight-year-old daughter." ALICE 314.0–316.4: "Dad, I need the next chapter!" VO 316.8–319.6: "She loved it." | `rustle`, `chime` |
| 320.0–330.0 | The book is published; a tiny book grows into a tall tower of copies. TXT "J.K. Rowling's first book" (no wizard imagery, no logos). Scribble returns and points at all three stories side by side | VO 320.4–329.6: "That rejected manuscript became one of the best-selling book series in history. Three 'failures'. Three world-changing successes." | `riser` + `burst` 0.4 at 328. Music `triumph` 320–330 |

**TRANSITION:** crumple wipe (the screen crumples into a ball), with `crumple` + `whoosh`.

### SCENE 7: Chapter 5, "Why mistakes still hurt" (330–400 s, 5:30–6:40), the emotional peak

| Time | Visual | VO / TXT | SFX / Music |
|---|---|---|---|
| 330.0–332.0 | Chapter card "5 · The voice in your head". The tint goes dim (`#9FAAC4` multiply 0.6) | | `whoosh`, `drone` bed starts (gain 0.08). Music `tension` |
| 332.0–346.0 | Scribble makes a small mistake (spills a cup of ink: a blot). The **ink-blob critic** (red eyes) rises behind him | CRITIC 335.0–337.6: "You always mess things up." CRITIC 339.0–341.8: "Maybe you're just not smart enough." | `dark_whoosh` 0.5 at 333, `heartbeat` bed 336–346 (bpm 76, gain 0.3) |
| 346.0–362.0 | Scribble pose `sad`, sitting. The critic looms bigger (scale 1.3) | VO 346.4–361.6: "Even knowing all this, mistakes can still hurt. Psychologist Carol Dweck calls this a fixed mindset: the belief that your abilities are set in stone, so every mistake feels like a verdict on who you are." | |
| 362.0–380.0 | Scribble looks up, takes a pencil, and writes **"yet"** at the end of a sign that says "I can't do this". The word "yet" glows ochre. The critic shrinks | VO 362.4–379.6: "A growth mindset adds one tiny word. Not 'I can't do this.' 'I can't do this yet.' Mistakes stop being a verdict and become directions." | `scribble` 0.8 at 369, `chime` 0.25 at 371, `riser` at 377 |
| 380.0–400.0 | The critic dissolves into ink particles (reuse the dissolve from `examples/stand`). The light warms up (tint off, warm `#F3C98B` 0.3). Scribble stands, pose `victory` | VO 381.0–399.4: "And remember that second brain signal, the one that says 'pay attention'? Believing you can grow makes it stronger. Your mindset literally changes how your brain handles mistakes." | `burst` 0.5 at 380.4, `hiss` 0.3. Music `triumph` from 381 |

**TRANSITION:** paper flip.

### SCENE 8: Chapter 6, "How to use your mistakes" (400–450 s, 6:40–7:30)

| Time | Visual | VO / TXT | SFX / Music |
|---|---|---|---|
| 400.0–402.0 | Chapter card "6 · The 3-step mistake method" | | `whoosh` + `scribble`. Music `warm` |
| 402.0–416.0 | **Step 1: NOTICE.** Big "1" writes in. Scribble with a magnifying lens (costume `explorer`) looks at a red X | VO 402.4–415.6: "Step one: notice it. Don't rush past the mistake. Pause, and ask, what exactly went wrong? That's your brain's 'pay attention' signal, so use it." | `ding`, `pop` |
| 416.0–430.0 | **Step 2: NAME IT.** Big "2". Scribble writes in a **journal** headed "MISTAKES I LEARNED FROM". Three lines appear | VO 416.4–429.6: "Step two: name it. Write it down in one line: what happened, and what you'll try next time. A mistake you name is a lesson. A mistake you hide is a repeat." | `scribble` 1.2 ×3 |
| 430.0–450.0 | **Step 3: AIM FOR 85.** Big "3". The meter shows 85%. Scribble picks a slightly harder book off a shelf (`hold` book), and the needle stays near 85 | VO 430.4–449.6: "Step three: aim for eighty-five. Choose practice where you get most things right, but not everything. If you never make mistakes, make it harder. If you fail constantly, make it easier." | `ding` at 432, `pluck` notes as the needle settles |

**TRANSITION:** ink wipe.

### SCENE 9: Ending, "Stand on them" (450–480 s, 7:30–8:00)

| Time | Visual | VO / TXT | SFX / Music |
|---|---|---|---|
| 450.0–462.0 | The paper-ball pile from the first film appears. Balls float up and become **steps** (the `step` prop, rising one by one). Scribble climbs, and a star glows at the top | VO 450.4–461.6: "So the next time you mess up, don't throw it away. Every mistake you keep becomes a step." | `pluck` scale (C D E G A C) on each step, `chime` at 461. Music `tender` |
| 462.0–466.0 | Scribble stands at the top, scarf blowing. TXT "Don't throw your mistakes away. Stand on them." | VO 462.4–465.8: "Don't throw your mistakes away. Stand on them." | `burst` 0.3 at 462.2 |
| 466.0–480.0 | **END SCREEN.** Scribble walks down to the left side and points right. Two empty rounded rectangles (end-screen slots, 16:9 ratio, at x 120..440 and y -260..-80 / 20..200) draw in, plus a subscribe circle. Keep the slots clear of other drawings | VO 466.4–473.6: "If this helped, watch the story that started it all, right here. And subscribe for more little ink stories with big hearts." | Music `tender` with final chord, fade-out 478–480 |

---

## 5. On-screen text style rules

- Handwritten Caveat 700.
- Titles: 72–92 px.
- Labels: 46–56.
- Captions: 44, near y=420.
- Numbers (17, 85%, 15%, 12) must be big (90+). Each one gets a `ding`.
- Max 6 words per text card.
- Red only for mistakes and Xs. Ochre for ideas and light.
- No brand names, logos or trademarked imagery. Use a generic yellow sticky note, a generic book cover and a generic glue.

---

## 6. Audio spec skeleton (`work/mistakes/film.audio.json`)

```json
{
  "duration": 480,
  "voices": {
    "scribble": {"voice": "am_michael", "speed": 0.92, "semitones": 0, "fx": "room", "gain": 0.9},
    "critic":   {"voice": "am_fenrir",  "speed": 0.84, "semitones": -6, "fx": "demon", "gain": 0.95},
    "alice":    {"voice": "af_bella",   "speed": 1.05, "semitones": 3, "fx": "room", "gain": 0.8}
  },
  "lines": [["scribble", 4.2, 7.8, "This little human just fell five times in ten seconds."]],
  "sfx":   [["thud", 2.6, 0.3], ["ding", 8.4, 0.3, {"f": 1320}]],
  "beds":  [["drone", 330, 400, 0.08], ["heartbeat", 336, 346, 0.3, {"bpm": 76}]],
  "music": {"level": 0.045, "final_chord": true, "sections": [
    [0, 22, ["Am","F","C","G"], 4, 64, "sparse", 0.8],
    [22, 30, ["C","G","Am","F"], 2, 76, "build", 0.9],
    [30, 50, ["F","C","G","Am"], 4, 66, "warm", 0.85],
    [50, 100, ["Am","F","C","G"], 4, 64, "sparse", 0.75],
    [100, 166, ["F","C","G","Am"], 4, 66, "warm", 0.8],
    [166, 170, ["C","G","Am","F"], 2, 76, "build", 0.9],
    [170, 220, ["Am","F","C","G"], 4, 64, "sparse", 0.75],
    [220, 320, ["F","C","G","Am"], 4, 66, "warm", 0.8],
    [320, 330, ["C","G","Am","F"], 4, 76, "triumph", 1.0],
    [330, 381, ["Am"], 8, 60, "tension", 0.6],
    [381, 400, ["C","G","Am","F"], 4, 76, "triumph", 1.0],
    [400, 450, ["F","C","G","Am"], 4, 66, "warm", 0.8],
    [450, 480, ["C","Am","F","G"], 4, 66, "tender", 0.85]
  ]}
}
```

Fill in every VO line from section 4 (speaker `scribble`, plus the `critic` and `alice` lines), and every SFX from the tables.

---

## 7. Build steps (Fabelo kit)

1. `cp templates/scene.src.html work/mistakes/film.src.html`. Set `DUR = 480`.
2. Register the assets from section 3. Copy `paperball`, `step` and the critic from `examples/stand`, and the rain/tint helpers from `examples/umbrella`.
3. Build the 9 scenes in order. After each scene, preview frames at 1280×720 and 540×960.
4. `python3 tools/build.py work/mistakes/film.src.html work/mistakes/film.html`
5. `node tools/record.js work/mistakes/film.html work/mistakes/silent.mp4 --w 1920 --h 1080 --fps 30 --chrome "$CHROME_PATH"` (about 18 minutes for 480 s)
6. `python3 tools/soundtrack.py --spec work/mistakes/film.audio.json --video work/mistakes/silent.mp4 --models "$FABELO_MODELS" --out work/mistakes/final.mp4`
7. Thumbnail (section 9) → `ready-fabelo/mistakes-make-you-smarter.jpg`, metadata (section 8) → `.json`, push to upload as Private.

---

## 8. Upload metadata

**Title options (pick one):**
1. Why Your Mistakes Are Secretly Making You Smarter
2. Why Failing 15% of the Time Makes You Learn Faster
3. Your Brain on Mistakes (The Science of Failing Forward)

**Description:**

```
Every mistake sends a tiny signal through your brain, and science says that signal is one of the fastest ways to learn.

In this animated explainer, Scribble walks you through:
• why toddlers fall 17 times an hour (and never give up)
• your brain's quarter-second "oops" signal
• the 15% rule: the mistake rate that makes learning fastest
• why confident mistakes are the easiest to fix
• three "failures" that changed the world
• a simple 3-step method to learn from every mistake

0:00 Babies fall 17 times an hour
0:50 Your brain's "oops" signal
1:50 The 15% rule
2:50 Why confident mistakes stick
3:50 3 mistakes that changed the world
5:30 Why mistakes still hurt
6:40 How to use your mistakes
7:30 Stand on them

▶ Watch the story that started it all: https://youtu.be/bVGsCqn6W8M

Subscribe to Fabelo Studio for more little ink stories with big hearts.

#psychology #growthmindset #learning #animation #selfimprovement
```

**Tags:** why mistakes make you smarter, growth mindset, psychology of mistakes, how to learn from mistakes, 85 percent rule, learning science, brain science, hypercorrection effect, famous accidental inventions, animated explainer, Fabelo Studio

**category_id:** "27"

---

## 9. Thumbnail prompt (for an image generator; choose the ratio in the tool)

```
YouTube thumbnail in a clean hand-drawn ink animation style on warm cream paper. On the right third: a friendly stick figure character named Scribble — perfectly round white head outlined in thick black ink, two dot eyes, a single curl of hair on top, a bright red scarf blowing to the side — standing proudly on top of a staircase made of crumpled paper balls, pointing up at a large glowing pink brain floating above him. The brain has tiny golden electric sparks crackling across it and a small red "X" mark turning into a golden check mark. Around the stairs, a few crumpled papers have faint red X marks. On the left: huge bold black brush-ink handwritten text "MISTAKES" with a thick red line through it, and below it in golden-yellow ink "= SMARTER?". High contrast, simple composition, lots of clean cream space, black ink + red + gold only, cinematic soft glow behind the brain. No 3D, no realistic style, no clutter, no extra text.
```

If the AI tool gets the text wrong, remove the two text sentences from the prompt and add the text yourself in Canva or Photoshop: "MISTAKES" (black, with a red strike) / "= SMARTER?" (gold).

---

## 10. Fact sources (checked before writing)

- Adolph et al. (2012), *Psychological Science*: "How Do You Learn to Walk? Thousands of Steps and Dozens of Falls per Day". 12–19-month-olds averaged 2,368 steps and 17 falls per hour.
- Moser et al. (2011), *Psychological Science*: "Mind Your Errors". Two fast error signals; growth mindset linked to a larger error positivity (Pe) and better accuracy after mistakes.
- Wilson, Shenhav, Straccia & Cohen (2019), *Nature Communications*: "The Eighty Five Percent Rule for optimal learning". Optimal training error rate is about 15.87% (≈85% accuracy). Shown in machine-learning models and models of animal learning; most likely to apply to perceptual learning in humans.
- Butterfield & Metcalfe (2001): the hypercorrection effect. High-confidence errors are more likely to be corrected after feedback.
- Fleming, 1928, St Mary's Hospital London: a two-week holiday, a contaminated dish, and a mold that stopped bacterial growth (Science History Institute, PBS).
- Post-it history: Spencer Silver's low-tack adhesive in 1968, Art Fry's hymnal bookmark idea in 1974, US launch in 1980 (Lemelson-MIT, MNopedia, History.com).
- Harry Potter manuscript: about 12 publisher rejections; Bloomsbury chairman Nigel Newton's 8-year-old daughter Alice read the chapters (widely reported, e.g. TIME, The Guardian oral history).
- Carol Dweck, *Mindset* (2006): fixed vs growth mindset; "not yet".
