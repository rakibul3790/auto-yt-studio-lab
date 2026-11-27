# Scribble — character canon (Fabelo Studio)

Scribble is the ONE main character of Fabelo Studio. Every video uses the same Scribble, drawn by
`lib/scribble.js`. He is never redrawn by hand, never replaced, never "reimagined".

## Locked (never changes)

| Trait | Value |
| --- | --- |
| Build | Ink stick figure: round head, single-line torso, two-segment arms and legs, small feet |
| Rig proportions | torso 50 · neck 16 · head radius 30 · upper arm 28 · forearm 28 · thigh 29 · shin 29 · foot 10 |
| Line | Ink `#1B1B1B`, main stroke 7 units, round caps; the ink "draws itself" on entrance |
| Head | Plain round head (paper-white inside), simple dot eyes + small brows + one-line mouth |
| Hair | The single curl **tuft** on top (`hair: 'tuft'`). Only hidden when a costume hat covers it |
| Signature | **Red scarf `#E63946`** with knot and swinging tail. ALWAYS on. Red is the channel's only accent colour |
| World | Warm paper background `#FBF7EE`, handwritten Caveat titles, ink props that draw themselves |
| Personality | Curious, kind, hopeful, a little clumsy. In emotional shorts he **does not speak** — he acts; others (narrator, side characters, his inner critic) speak |

## Allowed to change (outer changes only)

- Costumes: `caveman peasant knight egyptian roman scientist office king explorer graduate` + any new costume registered with `Scribble.registerCostume` (worn ON TOP of Scribble — the scarf stays visible).
- Held props, poses, expressions, scale, position, facing, rotation (lying down, falling).
- Scene tint / lighting (night, rain, dawn) via overlays — never recolour Scribble himself.
- Age framing ("little Scribble") = smaller `scale` only — same design.

## Never

- No colour change of the scarf, no second accent colour on Scribble, no realistic or 3D style.
- No new face style (no big anime eyes, no nose, no ears, no fingers drawn in).
- No other character with a red scarf. Side characters use `scarf: false` (or a non-red colour) and a different `hair` (`none bun long spiky bald`) or a costume (`grandpa`, `coach`, `judge` style), so Scribble is always the one you recognise.

## Side characters (examples)

- Grandpa / mentor: `hair:'bald'`, `scarf:false`, warm voice `am_onyx` -2 st.
- Inner critic: an ink-blob shadow with red eyes (custom renderer, see `examples/stand/`), voice `am_fenrir` -6 st "demon".
- Narrator: `af_heart` (calm, warm) or `am_michael`.
