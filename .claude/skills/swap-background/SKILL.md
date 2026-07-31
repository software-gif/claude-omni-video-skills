---
name: swap-background
description: Swap the background of an existing video clip into a different scene, city, season or setting while keeping the subject, motion and framing untouched. Use when the user runs /swap-background or asks to change the background, relocate a shot, put a clip in a different place, make a seasonal or market variant, or reuse one shoot for several locations.
---

# Swap Background

One shoot becomes a set of locations. Feed in a clip you already have, describe
the new setting, and Gemini Omni repaints the background in place — subject,
motion and framing stay where they were.

Runs on `google/gemini-omni-flash/edit` via `scripts/omni.py`.

## Step 1 — Get the clip and the new scene

**The source must be a file path on disk or a public URL.** The script cannot
read a clip that was pasted into the chat; ask for the path.

Then get the one variable: the new setting. Push for something concrete. "A
different city" produces a generic result; *"a rainy Tokyo side street at night,
neon reflections on wet asphalt"* produces a usable one.

If the user is vague, offer three concrete options rather than asking an open
question. Good axes to vary:

| Axis | Example |
|---|---|
| Market | Tokyo side street, Berlin Altbau courtyard, Miami boardwalk |
| Season | fresh snow, autumn leaves, high summer haze |
| Setting | white studio cyclorama, industrial loft, sunlit kitchen |
| Time of day | golden hour, blue hour, hard midday sun |

## Step 2 — Run it

```bash
python3 scripts/omni.py swap-background \
  --input clip.mp4 \
  --to "a rainy Tokyo side street at night with neon reflections on wet asphalt" \
  --out ./out
```

For a set of market variants, run one call per scene rather than asking for
several at once — one instruction per call is the whole point of this endpoint.

`--runs 2` generates two takes of the same instruction. Use it when the first
result drifts; the model varies between attempts. `--dry-run` shows the prompt
and the rough cost without spending anything.

## Step 3 — Look at the result before reporting success

Download links and file sizes prove nothing. Read the output file and check:

1. **Subject unchanged** — same person or product, same position in frame, same
   size. Background swaps are where identity drift shows up first.
2. **Motion intact** — the camera move and the subject's movement are the ones
   from the source, not a new invention.
3. **Lighting matches** — a subject lit for a bright studio pasted into a night
   street reads as fake. If the light on the subject did not follow the new
   scene, say so.
4. **Nothing new appeared** — no extra props, no invented logo, no text.

If a run fails, re-run it before rewriting the prompt — the model varies.
If two runs fail the same way, make the scene description more specific about
light ("lit only by the neon signs") rather than adding more sentences.

## Prompt rules

The recipe lives in `scripts/omni.py` and is deliberately short:

> Change only the background to *&lt;scene&gt;*. Do not change the people or
> products in the shot: same faces, same clothing, same colours, same position
> in the frame, same movement. Keep everything else the same.

**That wording is the result of a failed run, not a style choice.** An earlier
version asked the model to "keep the main subject and the camera movement" and
to "match the lighting on the subject to the new background". On a clip with a
group of people it moved the Taj Mahal to a Tokyo street correctly — and
re-dressed everyone in the frame to suit the new scene. Naming faces, clothing
and colours explicitly is what stopped that.

So: do not extend this prompt and do not "improve" it without measuring the
result. Every extra sentence is another permission to rebuild something. If you
need a change the recipe does not cover, use `scripts/omni.py raw --prompt "…"`
and keep it to one or two sentences.

## Notes

- Cost is time-based: roughly **$0.13 per second** of 720p output. An 8-second
  clip is about **$1** per run.
- Output is 1280×720 at 24 fps, with audio, in the length of the source. Omni
  does not upscale.
- The edit endpoint takes **text only** — you cannot hand it a reference photo
  of the exact location. For that you need a reference-based model.
- fal documents the edit endpoint as unavailable in the EEA, UK and
  Switzerland. It worked from Germany in our runs. If you do hit the block, it
  is not a bug in the script — see the README.
