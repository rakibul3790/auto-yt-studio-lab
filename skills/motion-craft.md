# Motion craft (shared by MindBlip and Fabelo Studio)

The timing rules both channels follow. They are adapted, in our own words, from the motion
reference of HyperFrames by HeyGen (Apache-2.0), which was measured frame by frame from
professional launch films. A rule that a script or a scene breaks on purpose, for a reason you
can say in one line, wins for that beat.

## Easing: pick by role, never one ease for everything

| Role | Ease | Fabelo name | GSAP name |
|---|---|---|---|
| Something arrives and lands | long tail ease-out | `power4Out`, `expoOut` | `power4.out`, `expo.out` |
| Camera move, colour change, position move | eases both ways | `power2InOut`, `sineInOut` | `power2.inOut` |
| Exit, zoom-through, dive | accelerates | `power3In` | `power3.in` |
| A landing with life (position or size only) | premium spring, damping 0.78 | `springPremium` | `back.out(1.4)` |
| Playful bounce (rare) | spring, damping 0.5 | `springPlayful` | `elastic.out(1, 0.5)` |

- Opacity and colour never bounce. Only position and size may overshoot.
- Linear only for rotation, progress bars and constant speed that is the point.
- The flat default (the same short ease-out on everything) is what makes a video look generated.

## Timing

- **Arrive slowly, leave cleanly.** A landing takes longer than a leaving. An exit is one smooth
  motion, 40-50 % shorter than its entrance. Never slide, stop, then leave.
- **Overlap.** The next element starts when the one before is 30-50 % done. Fully one-after-another
  looks robotic; everything at once looks cheap.
- **Stagger.** Letters about 1 frame apart, words 60-120 ms, list items 40-80 ms.
- **A landed title is dead still.** No creeping scale, no float, no breathing on titles or
  graphics after they land. The motion moves on to the next element, the camera or the world.
- **Holds.** A line the viewer must read holds about 0.5 s plus 0.3 s per word. The last line
  of a video holds at least 2 s. Hold 0.3-0.75 s of quiet before the payoff.
- **Fast moves** take 0.3-0.6 s and carry motion blur only while they are fast.
- **Rhythm.** Contrast speeds: quick cuts against longer holds. Shots of 1.8-3 s with motion inside.

## Title entrances (vary them, never the same one twice in a row)

- Each word blurs in (6 px to sharp) and fades up, about 0.07 s apart, with no movement (`enter: 'words'`).
- The line appears light grey and each word inks in, about 0.08 s apart (`enter: 'ink'`).
- Each letter fades from 0.3 to 1 with a slight blur, about 0.05 s apart, for a name (`enter: 'letters'`).
- MindBlip kinetic title card: each word slams in from 1.4x and out of focus, 90 ms apart, and
  lands dead still.
- One word may carry the accent colour (Fabelo red, MindBlip yellow) when it carries the meaning.

## Transitions: 3-5 kinds in a video, each with a cause on screen

| Transition | Use when | Fabelo | MindBlip |
|---|---|---|---|
| Hard cut | inside a scene, punch-ins; at most a third of the seams between ideas | `cut` | `cut` |
| Whip | a fast move or throw carries us across | `whip` | `whip_left/right` |
| Zoom-through | we dive into an object to see what is inside | `zoomthrough` | `zoom` |
| Object becomes the world | a card or object grows past the frame and the next shot lives inside it | `grow` | |
| Blur swap | same place, new idea or a time jump; the ground never cuts | `blurswap` | |
| Dip cut | the old frame darkens about 40 % for a few frames, then a hard cut | `dipcut` | |
| Iris / ink / page | storybook moments | `iris`, `ink`, `page` | |

- Cut on the fastest frame of a move, with the same direction and speed on both sides.
- The new shot may arrive slightly large and settle on a long tail.
- Worlds never crossfade into each other; a dissolve is for time passing, used once at most.

## Camera

- A camera move must be smooth to the sub-pixel. MindBlip with `"motion": "v2"` renders zooms and
  pans through ffmpeg's perspective filter (cubic, between pixels), not zoompan, which steps on
  whole pixels and reads as shake. Fabelo writes the camera with 5-decimal precision.
- Every move has a meaning: push in = focus or emotion; pull out = context or surprise; pan =
  sequence or geography; tilt = tall things or a reveal.
- Snap zooms and shake are for impacts only.

## Things that look generated (avoid)

Breathing, floating or pulsing loops standing in for motion; titles that keep moving after they
land; every scene entering the same way; every element fading and sliding up; bounce on text
or UI; a slow creeping push late in a scene with no reason.
