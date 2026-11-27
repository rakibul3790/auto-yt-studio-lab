---
name: mindblip-shorts-studio
description: Use when Rakib asks for MindBlip Shorts made with the mindblip-studio editing rules, a "shorts studio" pass, or a script or beat plan for the auto-yt-studio-lab test repo. Turns a Weird Facts Short (70-95 words, looping, 9:16) into a beat-by-beat plan (shot, camera, transition, sound, music mood, floating cards, name tag) that keeps the whole subject on screen and follows his mindblip-studio v5 principles adapted for Shorts. Lab version of mindblip-director; same JSON, stricter sound, cut and framing rules.
---

# MindBlip Shorts Studio

You direct and edit **MindBlip**, a faceless English YouTube Shorts channel of weird, surprising
science facts (9:16, about 30-40 seconds, shots of 2-3 seconds, a seamless loop). This skill is
Rakib's own **mindblip-studio v5** editing rules, read file by file and adapted for Shorts. It
lives in the test repo `rakibul3790/auto-yt-studio-lab` and writes the same JSON as
`mindblip-director`, so the "pro" renderer (`studio/pro.py`) reads it unchanged.

Never use this skill to change the main repo `rakibul3790/auto-yt-studio`. Everything here is a
lab test until Rakib approves it after watching a test video.

## 0. The eight principles (from mindblip-studio, adapted)

1. **The voice is king.** Nothing may cover a word. Music and sounds sit under the voice.
2. **Subtle beats loud.** Fewer, quieter sounds; never more than 2-3 sounds at the same moment.
3. **Hierarchy.** At most two layers on one graphic (footage plus one number, title or bar).
4. **One universe.** One grade, one music track and one family of sounds per Short.
5. **Motivated, not decorative.** Every sound and every styled transition needs a reason you
   could say in one line (a reveal, a change of idea, a count). No reason, no effect.
6. **Manufactured imperfection.** A little grain and a small handheld feel beat a sterile look.
7. **Duration creates meaning.** Hold for 0.3-0.5 s of quiet before the biggest reveal.
8. **Pacing and music first, effects last.** If a beat needs an effect to work, fix the beat.

Standing rules:

- A counter never sits idle at 0: a `number` beat starts counting at once.
- 1-2 showcase graphics (`number` or `compare`) per Short, 3 graphic beats at most in total.
- Never the same sound twice in a row; vary which sound marks which moment.
- **Never cut off the subject.** Its head, feet, tail and claws stay on screen in every shot
  (section 6b). Rakib's rule from the first sloth test, 27 Nov 2026.
- **2-3 floating showcase cards per Short**, each a different style (section 6c).

## 1. The script (if you also write it)

Follow `prompts/script-writing-prompt.md` exactly: 70-95 spoken words, hook in the first
sentence, a new idea every 2-3 seconds (8-12 scenes, one short sentence or phrase each),
escalate, human comparisons for big numbers, numbers written as spoken words, no call to
action in the script itself (in this lab there is no follow ending at all, see section 2b), and a seamless loop (the last scene is an unfinished sentence that the first scene
completes). No brands, trademarks or copyrighted names. Accurate facts only.

## 2. The director pass

Add to the script:

- `"style": "pro"` and `"format": "short"`.
- `"follow": false` (lab: no FOLLOW card, the Short loops; section 2b).
- `"music_mood"`: one of `mysterious`, `quirky`, `upbeat`, `calm`, `epic`.
- In every scene, a `"beats"` list (1 or 2 beats). A beat is one shot. Its `at_word` is the
  index of the word in that scene's `text` where the shot starts (the first beat is always 0).
  Split a scene in two when it is longer than about 9 words, at a natural word (a comma, "and",
  "but", "so"), so no shot lasts more than about 3 seconds.

### Beat fields

| field | values | notes |
|---|---|---|
| `shot` | `clip`, `photo`, `number`, `compare`, `text`, `card` | what fills the screen. `card` = a floating picture card over a background (section 6c). |
| `query` | 2-4 English words | stock search for `clip`/`photo` (Pexels, then Pixabay). Concrete and filmable: "octopus crawling rocks", not "strange animal". |
| `subject` | 1 word | the thing the footage must be tagged with, e.g. `octopus` |
| `camera` | `push_in`, `pull_out`, `pan_left`, `pan_right`, `tilt_up`, `tilt_down`, `punch`, `drift`, `static` | move on the footage. `punch` = fast snap zoom, for reveals. |
| `transition` | `cut`, `whip_left`, `whip_right`, `zoom`, `slide_up`, `flash`, `fade` | how we enter this shot. Ignored on the very first beat. `glitch` is off in this lab test (section 7). |
| `sfx` | list of `riser`, `impact`, `ding`, `tick`, `shimmer`, `thud` | sounds at the start of this shot (`riser` is placed so it peaks at the cut). `pop`, `glitch`, `whoosh` and `swish` are off in this lab test (section 7). |
| `number` | `{"to": 243, "from": 0, "suffix": " days", "prefix": "", "label": "ONE SPIN"}` | for `shot: number`: big animated count-up over blurred footage of `query` |
| `compare` | `{"left": {"label": "1 SPIN", "value": 243}, "right": {"label": "1 YEAR", "value": 225}, "unit": "days"}` | for `shot: compare`: two bars that grow |
| `text` | 1-4 words, caps | for `shot: text`: a kinetic title card ("IT GETS WEIRDER") |
| `card` | `{"style": "polaroid", "query": "dolphin swimming underwater", "subject": "dolphin", "caption": "Dolphin"}` | for `shot: card`: the picture on the card is a Pixabay photo of `query`. Styles: `polaroid`, `print`, `rounded`, `torn`, `letterbox`, `bubble`. `caption` only on `polaroid` (1-2 words, handwritten). |
| `bg` | `prev` or `new` | for `shot: card`: `prev` keeps the previous shot's footage running (dimmed, blurred) behind the card; `new` uses footage of the beat's own `query`. |
| `tag` | `{"title": "Sloth", "sub": "Rainforests of Central and South America"}` | a lower-third name tag (yellow bar, name, where it lives). Once per Short, on the 2nd-4th beat, on a clip that shows the subject whole. |

Keep the scene's `visual`, `subject`, `on_screen` and `highlight` fields too: they are the
fallback when the renderer runs a script without beats. `highlight` (1-3 words copied exactly
from `text`) is what the captions put on the yellow pill, so pick the words that carry the
surprise: numbers with their unit, the twist word, the contrast.

## 2b. Voice and emotion (eleven_v3)

The voice is ElevenLabs `XA3P1cj7XJexe6Zq0ATX` on `eleven_v3`, read in ONE take for the whole
Short (stability 0.0, similarity 0.8). v3 has no timestamps, so the renderer gets word times
from a free Whisper pass and maps them onto `text`.

Add to every scene:

- `"say"`: the line v3 reads. It is `text` word for word, plus inline audio tags in square
  brackets. With the tags removed it must equal `text` exactly (captions and `at_word` come
  from `text`).
- `"look"` (optional): `excited`, `sad`, `angry` or `whisper`. It drives the picture and music:
  - excited: richer colour, music up (x1.15);
  - sad: low saturation, cool blue tint, music down (x0.45);
  - angry: red tint, more contrast, music up (x1.25), camera shake on the first shot;
  - whisper: softer colour, slightly lifted, music down (x0.6).
  Leave it out for a neutral line.

Tags v3 understands: `[excited]`, `[curious]`, `[laughs]`, `[chuckles]`, `[gasps]`, `[sighs]`,
`[sad]`, `[softly]`, `[warmly]`, `[serious]`, `[worried]`, `[nervous laugh]`, `[whispers]`,
`[angry]`, `[shouts]`.

Rules:

1. One or two tags per scene, at the start of the line or before the twist word. Never stack
   three.
2. Let the emotion follow the fact: wonder or a gasp for the reveal, a sigh or `[sad]` for
   something unfair, `[angry]` or `[shouts]` only for a genuinely outrageous line, `[whispers]`
   for a secret, `[laughs]`/`[chuckles]` for something funny.
3. Change the feeling at least three times across a Short, so it never sounds flat.
4. Pick `look` from the same feeling as the tag, and choose `music_mood` for the whole Short.
5. Keep `say` under about 650 characters (credits are billed per character).

### The follow ending (off in this lab)

Rakib's decision, 27 Nov 2026: no FOLLOW card. Set `"follow": false` and let the last line
loop into the first (the last scene is an unfinished sentence the first scene completes, e.g.
"So the next time you call someone slow, remember," then "A sloth can hold its breath for
forty minutes."). The paragraph below is how the main renderer behaves without the switch.

Do not write it yourself. The renderer appends `[chuckles] Follow for more weird facts!` to the
last scene's `say`, drops shots that would fall on those words, and puts a `FOLLOW FOR MORE`
title card (flash, shimmer) under it, with a short pause after.

### What the renderer does by itself

- Each shot gets its scene's `look` colour; dark clips are brightened, and if still too dark
  the QC step catches them. Music volume follows each scene's `look` with smooth 0.6 s ramps.
- If no mood words match, `music_mood` rotates between quirky, upbeat, mysterious and calm.
- If v3 fails, it falls back to `eleven_multilingual_v2` with the clean `text`, then to the
  free voice, so a video always comes out.


## 3. Directing rules (Shorts version)

1. **Visual anchor first.** Beat 1 shows the subject itself, literally (the creature, the
   planet, the organ), `camera: punch`, `sfx: ["impact"]`. Never open on a generic or abstract
   shot. This is the only big punch zoom in the Short.
2. **Clue, then reveal.** Before the key fact, give one beat that raises the question (a close
   shot, a hint, "but here's the thing"); the reveal beat follows it.
3. **B-roll with intent.** Each clip is either the thing itself (primary) or a clear visual
   metaphor for the line. No wallpaper footage that only fills time.
4. **Change the picture every 2-3 seconds.** Never two beats in a row with the same query or
   the same camera move.
5. **Hard cut is the default.** At least 6 in 10 transitions are `cut`. Cut on the moment of
   fastest motion in the clip, and use a match cut (same shape, colour or direction in both
   shots) whenever two queries allow it.
6. **Styled transitions only where the idea changes:** `smash` energy comes from a plain `cut`
   onto a `punch` shot at the hook and at the reveal; `zoom` for going deeper; `slide_up` for a
   new fact; `whip_left`/`whip_right` at most twice per Short (they are silent in this test);
   `flash` once, for the twist; `fade` only for a calm or sad line. No `glitch` (section 7).
7. **Show numbers, don't just say them.** A surprising number becomes a `number` beat; two
   numbers set against each other become a `compare` beat.
8. **The loop.** The last beat leads visually back to the first (same subject, `cut`, no
   outro), so the replay feels continuous.
9. **Queries that find footage.** Common, filmable subjects and actions ("whale swimming",
   "heart rate monitor"). Avoid what stock sites can't have. Never imply a real, named person.
   If the action is rare on stock sites (a sloth swimming), use `shot: photo` or show the
   subject doing something common while the line is spoken; never let the beat fall back to
   empty scenery with no subject in it (sloth v2 showed plain jungle for "swims faster").
10. **Whole-body queries.** Ask for the whole animal: "sloth hanging from branch", "sloth
    climbing tree", not "sloth fur" or "sloth face close up". Graphic beats (`number`,
    `compare`, `text`) sit over footage too, so their `query` must also show the subject
    whole (sloth v2's "40 MIN" sat over a fur close-up with no head).

## 4. Sound

Allowed sounds in this test: `impact`, `thud`, `riser`, `ding`, `tick`, `shimmer`.

- **The decision test:** before adding a sound, ask "would the moment lose something without
  it?" If not, leave it out. Most cuts have no sound. 4-8 sounds per Short.
- **The hook:** beat 1 gets `impact` (the renderer's impact already has a crack, a body and a
  low tail).
- **The reveal:** `riser` on the beat before the twist (it peaks on the cut), then `impact` or
  `thud` on the reveal. Use the riser once per Short.
- **Counts:** `tick` on a `number` or `compare` beat (the renderer adds the ticks and a `ding`).
- **Signature:** `shimmer` marks the single most wonderful moment and the follow card, so it
  becomes the channel's recognisable sound. Do not use it elsewhere.
- **Tension by subtraction:** the beat right before the biggest reveal has no sound at all.
- **Sound arc:** busier at the start, quiet in the middle, one last lift at the reveal.

Mix targets from mindblip-studio: voice peaks near −6 dBFS; music 18-22 dB under the voice
and ducked while the voice speaks; sounds −20 to −10 dBFS; master −14 LUFS, true peak −1.5 dB.
The renderer already ducks the music and normalises to −14 LUFS; finer sound-level rules are a
later renderer change, not something a script can set.

## 5. Music

- `music_mood` from the topic: mysterious (deep sea, space, body secrets), quirky (funny
  animals), upbeat (records, speed), calm (gentle nature), epic (giant scales, history).
- Thinking vs feeling: a fact that makes you think gets mysterious or calm; a fact that makes
  you laugh or gasp gets quirky or upbeat.
- The first line should land almost dry: keep the hook words clear of busy music (a later
  renderer change will hold the music back for the first second).
- Leave a short gap (0.3-0.5 s) before the last reveal: end the scene before it on a full
  stop so the voice pauses there.
- No long reverb tail at the end: it would break the loop. The renderer's short fade stays.

## 6. Picture

- **Camera:** gentle, always eased moves (push_in, pull_out, pans, tilts, drift). `punch` only
  on beat 1 and at most once more on the reveal. Never the same move twice in a row.
- **Settle and hold:** give numbers and titles a beat long enough to read (about 2 s or more).
- **Grade:** one grade family per Short. Use `look` sparingly: at most two scenes with a
  strong look (sad, angry); most scenes neutral.
- **No glitch or RGB-split look** in this test.
- **Captions:** unchanged MindBlip captions (Montserrat ExtraBold, 1-3 words, active word
  yellow, key words on the yellow pill). Do not add a second word bar.

## 6b. Whole subject on screen (framing)

Rakib's rule: **never crop the subject's head, feet, tail or claws.** The lab renderer
(`config.yaml` → `video.pro_framing: keep`) does this by itself:

- **Find the subject.** A detector (OWLv2, `studio/framing.py`) finds the box around
  `subject` in each picture; the shot picker (`studio/shotpick.py`) prefers footage where that
  box is whole, not touching the frame edges, and not tiny or filling everything. Black bars
  and flat, empty frames are rejected.
- **fill:** when the whole box fits a 9:16 window, the window frames the subject with a 6 %
  margin, and the camera move is clamped so the subject never leaves the frame (zoom at most
  about 1.08x).
- **fit:** when it does not fit (a wide photo of a long animal), the whole picture is shown
  smaller, never cropped, over a blurred, dimmed copy of itself.
- **Framecheck:** the first and last frame of every clip shot are checked again; a shot whose
  subject touches the top, the bottom or both sides is re-rendered in fit. The run writes a
  `*.framecheck.jpg` sheet next to the video. Look at it, and at one frame per second of the
  video, before showing Rakib anything.

Known limit (sloth v2): the detector sometimes finds only part of an animal (a head, a second
animal half out of frame, one hidden behind a branch), so framecheck passes a shot that is
still cut. Check the frames by eye; when a clip is cut, change its `query` or make it a
`photo`.

To go back to the old crop, set `pro_framing: cover`.

## 6c. Floating showcase cards and the name tag

Rakib saw these in sloth v2 and said they are perfect (27 Nov 2026). Keep them as they are.

- **What:** a picture card (`shot: card`) that floats over the running footage, for a thing
  the voice compares or mentions (the dolphin the sloth beats, the algae in its fur, the moths
  that live there). The card's picture is a Pixabay photo; the renderer crops it so the
  subject inside is never cut.
- **How many:** 2-3 per Short, each a **different style**, never the same image twice.
- **Styles:** `polaroid` (white frame, handwritten caption), `print` (thin white border),
  `rounded` (rounded corners, soft shadow), `torn` (torn paper edge), `letterbox` (wide
  strip), `bubble` (rounded bubble with a small trail of dots toward the subject).
- **Motion:** settle and hold: the card drops in, settles with a slight tilt (2-4.5°) over
  about 9 frames, then holds still long enough to read. No spinning or bouncing.
- **Background:** `bg: prev` keeps the previous shot running behind the card (dimmed and
  blurred), so the picture flows; `bg: new` when the previous shot does not fit.
- **Sound:** a soft `tick` as the card lands (the renderer adds it if the beat has no sfx).
- **Picture choice:** the card's `query` must find a clear, well-lit photo of the thing (a
  moth on a dark table reads badly); prefer "moth on leaf" over "small brown moth".
- **Name tag:** one `tag` per Short (section 2), on a clip where the subject is whole.

## 7. Lab test switches (Rakib's decision, 27 Nov 2026)

For this test Rakib turned off the pop, glitch and transition sounds that mindblip-studio
bans, and the glitch transition with them. After he watches a test video he keeps it or goes
back to the old sound.

- `config.yaml` → `video.pro_banned_sfx: [pop, glitch, whoosh, swish]`: the renderer drops
  these sounds, including the automatic pops on graphics and caption pills.
- `config.yaml` → `video.pro_banned_transitions: [glitch]`: a banned transition becomes a
  plain cut.
- To go back to the old sound, set both lists to `[]`. Do not write banned sounds or
  transitions into new scripts while the lists are on.

## 8. Left out on purpose

From mindblip-studio, these do not fit Shorts and are not used: 4-7 second average shots,
reverb per location, parallax, 12 fps graphics, the punch-word bar (captions already do it),
the PC pipeline (compose.py, Flow, local drives) and the historical category look (paper,
typewriter, archival film and sound). Planned for later, not in this test: callout arrows,
ambience beds, and a weird-facts category file.

## 9. Output

Reply with only the JSON (a list of Shorts, or one Short object), in a code block, ready to
save as `scripts/queue/batch-NN.json`. Before replying, check:

- every `at_word` is a valid word index of that scene's `text`, first beat 0, increasing;
- every `highlight` phrase is copied exactly from `text`;
- 1-3 graphic beats, first beat is footage of the main subject with `impact`;
- no `pop`, `glitch`, `whoosh` or `swish` sound and no `glitch` transition (lab test, section 7);
- at least 6 in 10 transitions are `cut`, whips at most twice, no type more than twice in a row;
- 4-8 sounds in the whole Short, never more than 2-3 in the same moment;
- word count 70-95, last line completes into the first.
- every scene has `say`, and `say` with the [tags] removed equals `text` exactly;
- 1-2 tags per scene, at least three different feelings, `look` matches the tag;
- no follow line written in the script, and `"follow": false` (lab);
- every `query` (graphics included) asks for the whole subject, and no beat can fall back to
  scenery without the subject;
- 2-3 `card` beats, each a different style, different pictures; one `tag`.

After the render, before showing Rakib: look at the framecheck sheet and one frame per second.
No head, foot, tail or claw may be cut, and no shot may be missing its subject.

### Example (two scenes)

```json
{
  "title": "On Venus, One Spin Takes Longer Than a Year",
  "format": "short",
  "style": "pro",
  "music_mood": "mysterious",
  "scenes": [
    {
      "text": "On Venus, you'd celebrate a birthday before a single day is over.",
      "say": "[excited] On Venus, you'd celebrate a birthday [laughs] before a single day is over.",
      "look": "excited",
      "visual": "planet venus", "subject": "venus", "on_screen": "Birthday before bedtime",
      "highlight": ["before a single day"],
      "beats": [
        {"at_word": 0, "shot": "clip", "query": "planet venus", "subject": "venus",
         "camera": "punch", "sfx": ["impact"]},
        {"at_word": 3, "shot": "clip", "query": "birthday cake candles", "subject": "cake",
         "camera": "push_in", "transition": "cut"}
      ]
    },
    {
      "text": "that one full turn takes two hundred and forty three Earth days.",
      "say": "[whispers] that one full turn takes [gasps] two hundred and forty three Earth days.",
      "look": "whisper",
      "visual": "planet rotating space", "subject": "planet", "on_screen": "1 spin = 243 days",
      "highlight": ["forty three Earth days"],
      "beats": [
        {"at_word": 0, "shot": "number", "query": "planet rotating", "subject": "planet",
         "camera": "drift", "transition": "zoom", "sfx": ["tick"],
         "number": {"from": 0, "to": 243, "suffix": " DAYS", "label": "ONE SPIN"}}
      ]
    }
  ]
}
```

## 10. Working with Rakib on this skill

- Show him the test video first. Only after he says he likes it do the fixes go into this
  skill.
- After every round of fixes, say on your own which fixes would be good to add to this skill,
  and add them only after he says yes (his rule, 27 Nov 2026).
- Never touch the main repo `rakibul3790/auto-yt-studio`; ask before every GitHub Actions run
  and before any ElevenLabs use. Reuse a saved voice (`voice_cache`) for re-renders when the
  text is unchanged, so no new credits are spent.
