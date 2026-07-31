---
name: swap-background
description: Swap the background of an existing video clip into a different scene, city, season or setting while keeping the subject, motion and framing untouched. Use when the user runs /swap-background or asks to change the background, relocate a shot, put a clip in a different place, make a seasonal or market variant, or reuse one shoot for several locations.
---

# Swap Background

One shoot becomes a set of locations. Feed in a clip you already have, describe
the new setting, and Gemini Omni repaints the background in place — subject,
motion and framing stay where they were.

Runs on `google/gemini-omni-flash/edit` via `scripts/omni.py`.

## Step 0 — Read the brand file

If `brand/brand.md` exists, read it first. Section 4 lists the scenes that suit
the brand and the ones that do not; section 6 describes the talent that has to
survive the swap; section 7 lists what must never appear. Propose scenes from
that list rather than inventing your own, and say which entry you used.

No brand file? Carry on and ask the user directly — but mention once that
filling in `brand/brand.md` means not having to answer this every time.

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

**For a market set, repeat `--to`.** Each one is its own model call — the
endpoint takes exactly one instruction — but the script handles the sequence,
uploads the clip once instead of once per scene, and writes an overview strip
across all variants at the end:

```bash
python3 scripts/omni.py swap-background --input clip.mp4 \
  --to "a rainy Tokyo side street at night" \
  --to "a snowy alpine village at dusk" \
  --to "a Miami boardwalk at golden hour" \
  --out ./out
```

Always show the user `--dry-run` output first when the batch is larger than
about three scenes — that is real money per variant.

`--runs 2` generates two takes of *each* scene. Use it when a result drifts;
the model varies between attempts.

## Step 3 — Look at the result before reporting success

Download links and file sizes prove nothing. Every run writes a
`…-compare.jpg` next to the video (source on top, result below); a batch also
writes `…-overview.jpg` across all variants. **Read those images** and check:

1. **Subject unchanged** — same person or product, same position in frame, same
   size. Background swaps are where identity drift shows up first.
2. **Motion and action intact** — the camera move and what the subject *does*
   are the ones from the source, not a new invention. This is not only a
   `/change-angle` problem: in a four-market batch the Miami variant had the
   subject start drinking from the bottle in the last third, while the Tokyo and
   alpine variants from the same command did not. It shows up near the end, so
   the first tile of the contact sheet always looks fine — check the last one.
3. **Lighting** — read this one knowing the trade the recipe makes. Because the
   prompt locks the people and products, the light *on them* does not adapt to
   the new scene. That is deliberate: identity stability was worth more than
   perfect integration. So if a subject lit for hard midday sun ends up in a
   night street and reads as pasted in, the run did not fail — the scene was a
   bad match for this clip. Pick a scene with similar light and time of day, and
   tell the user that is why.
4. **Nothing new appeared** — no extra props, no invented logo, no text. Check
   this against section 7 of the brand file if there is one.

In a batch, check **every** variant. One good scene does not vouch for the
others, and the overview strip makes an outlier easy to spot.

If a run fails, re-run it before rewriting the prompt — the model varies.
If two runs fail the same way, make the scene description more specific about
light ("lit only by the neon signs") rather than adding more sentences.

## Prompt rules

The recipe lives in `scripts/omni.py` and is deliberately short:

> Change only the background to *&lt;scene&gt;*. Do not change the people or
> products in the shot: same faces, same clothing, same colours, same position
> in the frame, same action and movement. Keep everything else the same.

**Every clause in there is the result of a failed run, not a style choice.**

An early version asked the model to "keep the main subject and the camera
movement" and to "match the lighting on the subject to the new background". On a
clip with a group of people it moved the Taj Mahal to a Tokyo street correctly —
and re-dressed everyone in the frame to suit the new scene. Naming faces,
clothing and colours explicitly stopped that.

"Same **action**" came later, from a four-market batch where the Miami variant
had the subject start drinking from a bottle she only holds in the source. The
same scene re-run with "action" in the instruction kept her holding it.

So: do not extend this prompt and do not "improve" it without measuring the
result. Every extra sentence is another permission to rebuild something. If you
need a change the recipe does not cover, use `scripts/omni.py raw --prompt "…"`
and keep it to one or two sentences.

## Notes

- Cost, measured rather than quoted: an 8-second edit costs **1.71 USD**, i.e.
  **0.213 USD per second**. The 0.13 USD/s on fal's model page is the output
  share only; an edit also pays input tokens for the clip going in. A shorter or
  smaller source is cheaper.
- Output is 720p at 24 fps, with audio, in the length of the source — 1280×720
  for a landscape source, 720×1280 for a portrait one. Omni does not upscale.
- The edit endpoint takes **text only** — you cannot hand it a reference photo
  of the exact location. For that you need a reference-based model.
- Google blocks editing *uploaded* videos in the EEA, UK and Switzerland, but
  allows editing model-generated ones. Calls routed through fal do not originate
  in the EEA at all, which is why runs from Germany went through. If you do hit
  the block, it is not a bug in the script — see the README.
