---
name: change-angle
description: Generate a new camera angle or framing from an existing video clip — a wide, a close-up, an over-the-shoulder or a low angle of the same moment. Use when the user runs /change-angle or asks to reframe a shot, get another perspective, produce coverage or cutaways from one take, or turn a single setup into an editable sequence.
---

# Change Angle

One take becomes coverage. Ask for a wide, a close-up or an over-the-shoulder
and Omni re-frames the same moment, so a single setup turns into a small
edit-ready sequence instead of one static angle.

Runs on `google/gemini-omni-flash/edit` via `scripts/omni.py`.

## Step 0 — Read the brand file

If `brand/brand.md` exists, read section 6 (talent) and section 7 (what must
never appear). A reframe is one of the two places identity drifts, so know what
"unchanged" means for this brand before you look at the result.

## Step 1 — Get the clip and the angle

**The source must be a file path on disk or a public URL.**

Then pick the angle. Presets:

| `--angle` | What you get |
|---|---|
| `wide` | more of the surroundings |
| `close-up` | closer on the main subject |
| `extreme-close-up` | detail framing |
| `over-the-shoulder` | from behind the subject |
| `low` | camera looks up at the subject |
| `high` | camera looks down at the subject |
| `profile` | side-on view |

Anything else goes through `--to` as free text, e.g.
`--to "a three-quarter view from the front left, chest height"`.

If the user wants a sequence rather than one shot, propose a set that actually
cuts together — typically `wide` → `close-up` → `over-the-shoulder`. Each one is
its own call.

## Step 2 — Run it

```bash
python3 scripts/omni.py change-angle --input clip.mp4 --angle close-up --out ./out
```

**For a coverage set, repeat `--angle`** — that is the point of this skill.
One command, one upload, an overview strip at the end:

```bash
python3 scripts/omni.py change-angle --input clip.mp4 \
  --angle wide --angle close-up --angle over-the-shoulder --out ./out
```

`--to` takes free-text framing and can be mixed in:
`--angle wide --to "a three-quarter view from the front left, chest height"`.

`--runs 2` for a second take of *each* angle. `--dry-run` to show the plan and
rough cost first.

## Step 3 — Look at the result before reporting success

This is the skill where the output most often looks fine and is not. Every run
writes a `…-compare.jpg` next to the video — top row source, bottom row result.
Read it, and check:

1. **It is actually a different angle**, not the same framing with a slight
   zoom. This happens, and **re-running does not fix it** — we asked for
   `close-up` twice with the old preset wording and got a near-identical frame
   both times. It is a wording problem, not variance: replacing "a closer shot
   of the main subject" with "a tight close-up framing only the subject's head
   and the product, filling the frame" produced a real close-up on the first
   try. So if a framing comes back too timid, do not just re-run — say what
   should fill the frame and what should be cropped out, via `--to`.
2. **The framing holds for the whole clip.** In the successful close-up the
   tight framing was strongest at the start and drifted back towards the
   original composition by the end. Check the last frame of the contact sheet,
   not just the first.
3. **Same action.** The recipe now locks this explicitly and it holds, but check
   anyway. The example in `examples/change-angle.mp4` was made before the fix:
   the source has a woman holding a bottle beside her shoulder, the
   over-the-shoulder take has her drinking from it. Everything else was right,
   which is what made it easy to miss. Re-running the same angle with the
   current recipe kept her holding the bottle.
4. **Same scene** — same clothing, same props, same background, same light.
5. **The subject survived the reframe** — faces and product labels are where a
   new angle breaks down, because the model has to invent what the original
   camera never saw.

In a batch, check every angle against the source, and check the angles against
*each other*: a set that does not share one continuous look will not cut into a
sequence, however good each shot is on its own. The overview strip is where
that shows up.

Be honest here. A generated angle is an interpretation, not a second camera —
if it does not match, report that rather than shipping it as coverage.

## Prompt rules

> Re-frame this shot as *&lt;shot&gt;*. Keep the same subject, action, wardrobe,
> lighting and setting. Keep everything else the same.

**The word "action" is doing real work there.** An earlier version said "the
same moment" instead, and on an over-the-shoulder reframe the model invented a
drinking motion that was not in the source. Same clip, same angle, the version
above kept her holding the bottle. Do not drop it.

Short on purpose otherwise. Two things to avoid:

- **Do not ask for two changes at once.** "A close-up, and make it night"
  reliably gets you one of the two. Chain two calls instead.
- **Do not describe the source clip back to the model.** It can see the clip.
  Extra description of what is already there mostly gives it license to
  re-render those parts.

## Notes

- Cost, measured rather than quoted: about **0.15 USD per second** of clip
  length, averaged over 28 runs. The 0.13 USD/s on fal's model page is the
  output share only; an edit also pays input tokens for the clip going in.
  Individual runs vary. A shorter source is cheaper.
- Output is 720p at 24 fps, with audio, in the length of the source — 1280×720
  for a landscape source, 720×1280 for a portrait one.
- Angles that require inventing a lot of unseen geometry (a full 180° reverse)
  are the weakest case. Small to moderate reframes hold up best.
- Google blocks editing *uploaded* videos in the EEA, UK and Switzerland, but
  allows editing model-generated ones. Calls routed through fal do not originate
  in the EEA at all, which is why runs from Germany went through. See the README.
