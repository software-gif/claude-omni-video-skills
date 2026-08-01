---
name: transform-object
description: Change the material, finish or colourway of an object inside an existing video clip — chrome, glass, matte, a new colour — without reshooting. Use when the user runs /transform-object or asks to restyle a product in footage, test a finish or SKU variant on screen, recolour something in a clip, or change what a thing is made of.
---

# Transform Object

Same footage, new finish. Point at something in a clip you already have,
describe the swap, and Omni restyles it in place — no reshoot, no physical
sample needed just to see how a colourway reads on screen.

Runs on `gemini-omni-flash-preview` through the Google Gemini API, via
`scripts/omni.py`.

## Step 0 — Read the brand file

If `brand/brand.md` exists, it answers both variables for you. Section 2 gives
the exact phrase to pass as `--object` (the "So heißt es im Prompt" column) —
use it verbatim, it was chosen because the model reliably finds that object.
Section 3 lists the colourways worth testing. Section 7 says what must not
appear.

## Step 1 — Get the clip, the object and the target

**The source must be a clip from a previous `create` or `animate` run.** Pass
its path; the script chains automatically via the manifest beside it.

**No video, only product photos?** That is the common case, not an edge case.
Point them at `animate`: a packshot plus a motion description becomes the source
clip, and this skill then runs on that.

```bash
python3 scripts/omni.py animate --image packshot.jpg \
  --prompt "slow push-in on the product, soft studio light" --aspect 9:16 --duration 5
```

Two variables, and both need to be precise:

**`--object`** — how the model finds the thing. Use the plainest visual
description that is unambiguous in that frame: `"the sneaker"`, `"the bottle on
the table"`, `"the car's wheels"`. If there are two similar objects, add the
distinguishing detail (`"the left bottle"`). Do not use internal names or SKU
codes — the model has never seen them.

**`--to`** — the new material, finish or colour. Concrete beats evocative:

| Family | Works |
|---|---|
| Metal | `brushed chrome`, `matte black anodised aluminium`, `polished brass` |
| Surface | `matte rubber`, `glossy lacquer`, `frosted glass` |
| Colour | `deep forest green`, `off-white with a beige sole` |
| Material | `transparent glass`, `woven fabric`, `raw concrete` |

## Step 2 — Run it

```bash
python3 scripts/omni.py transform-object \
  --input clip.mp4 \
  --object "the sneaker" \
  --to "brushed chrome" \
  --out ./out
```

**For a colourway range, repeat `--to`.** Everything else stays identical
between variants, which is exactly what makes them comparable:

```bash
python3 scripts/omni.py transform-object --input clip.mp4 \
  --object "the black insulated bottle" \
  --to "brushed stainless steel" \
  --to "deep forest green" \
  --to "sand beige with a black lid" \
  --out ./out
```

The overview strip the script writes at the end is the deliverable here — it is
the range on one page.

`--runs 2` for a second take of each finish. `--dry-run` to show the plan and
rough cost.

## Step 3 — Look at the result before reporting success

Every run writes a `…-compare.jpg` next to the video (source on top, result
below); a colourway batch also writes `…-overview.jpg` with the whole range side
by side. **Read those images** and check, in this order:

1. **The right object changed.** The most common failure is the model
   restyling a neighbouring object, or the whole scene, instead of the one you
   named. If that happens, make `--object` more specific and re-run.
2. **Shape and size are untouched.** A chrome sneaker that is subtly a
   different shoe is useless for a colourway test.
3. **Branding survived.** Logos and label text on the object are the first
   thing to smear when the surface is re-rendered. Look at them at full size.
   If the product carries small print, expect it to break at 720p — say so.
4. **Burned-in overlay text is still there — and still there at the end.**
   Changing a material used to drop unrelated on-screen text partway through
   the clip: a brushed-steel take lost its "STAY SHARP" overlay from the middle
   onwards while the forest-green take from the same command kept it. Adding
   "label, branding" to the recipe fixed that in a direct re-test, but it is a
   cheap thing to check and an expensive thing to miss. Compare the middle and
   last tiles against the source row; the first frame looks fine either way.
5. **The finish is physically plausible in that light** — chrome that does not
   reflect the room reads as a flat grey sticker.
6. **Motion intact** — the object still moves the way it did.

If branding breaks and the shot matters, this is the point to say the honest
thing: use it for internal look-tests, not as a finished asset.

## Prompt rules

> Change *&lt;object&gt;* to *&lt;target&gt;*. Keep its shape, position, label,
> branding and motion the same. Keep everything else in the scene the same.

**"label, branding" earns its place.** Without those two words, a
brushed-steel run lost the clip's burned-in headline from the middle of the
clip onwards. Same source, same target material, the version above kept the
headline all the way through. Asking to *preserve* branding is not the same as
mentioning a logo out of nowhere — see the next point.

- **Do not name a logo that is not in the shot.** Preserving "branding" is
  safe; asking the model to do something *to* a logo it cannot see invites it
  to invent one. The sibling `/localize` skill learned that the hard way.
- **One object, one property, one call.** "Chrome and put it on a marble table"
  is two jobs; the second one is `/swap-background`.

## Notes

- Cost: roughly **0.13 USD per second** generated, **0.14 USD per second** for
  an edit. Every response carries its real token usage, so each run prints what
  it actually cost — no estimating. A shorter clip is proportionally cheaper.
- Output is 720p at 24 fps, with audio, in the length of the source — 1280×720
  for a landscape source, 720×1280 for a portrait one. 720p is the ceiling, so
  fine label text on a small object will not hold up.
- The edit endpoint is text-only: you cannot supply a swatch or a reference
  photo of the exact material. Describe it instead.
- **The source clip must come from `create` or `animate`.** Google does not
  allow editing *uploaded* videos from the EEA, Switzerland or the UK, only
  model-generated ones. `--input` chains automatically via the manifest next to
  the video, so this is invisible in normal use — but if someone brings their own
  footage, say plainly that this route cannot edit it.
