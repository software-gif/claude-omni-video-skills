---
name: localize
description: Translate the on-screen text, captions, labels and signage inside an existing video clip into another language, in place, keeping fonts and layout. Use when the user runs /localize or asks to translate a video's on-screen text, adapt a master clip for another market, produce language variants, or change burned-in captions.
---

# Localize

One master clip, many markets. Swaps the on-screen text, captions, labels and
signage into a new language, in place, keeping the fonts, colours and positions
of the original.

This only works because Omni keeps text inside the frame legible through an
edit. It touches **on-screen text only** — the spoken voiceover stays as it is.

Runs on `google/gemini-omni-flash/edit` via `scripts/omni.py`.

## Step 0 — Read the brand file

If `brand/brand.md` exists, section 5 gives you the target languages and the
exact `--keep` string. Use them rather than asking — that section exists so
nobody has to remember that the wordmark must not be translated.

## Step 1 — Get the clip and the target language

**The source must be a file path on disk or a public URL.**

Then two things:

- **`--lang`** — the target language, written in English: `German`, `French`,
  `Brazilian Portuguese`.
- **`--keep`** — what must *not* be translated. Almost always the brand name,
  often the product name and any legal wording. `--keep "the brand name"` is
  the default worth suggesting; a translated wordmark is an unusable asset.

Before running, read the source and tell the user which text you can see in it.
If the clip has no burned-in text, this skill has nothing to do — say so
instead of spending a call.

## Step 2 — Run it

```bash
python3 scripts/omni.py localize \
  --input clip.mp4 \
  --lang German \
  --keep "the brand name" \
  --out ./out
```

**For a market set, repeat `--lang`:**

```bash
python3 scripts/omni.py localize --input clip.mp4 \
  --lang German --lang French --lang "Brazilian Portuguese" \
  --keep "the brand name" --out ./out
```

`--runs 2` for a second take of each language — text is exactly where the model
varies most, so this is the skill where a second take pays off most often.
`--dry-run` to show the plan and rough cost.

## Step 3 — Read the text in the output. Every word.

This is not optional and it is the whole job. Every run writes a
`…-compare.jpg` next to the video — top row source, bottom row result. Read it
at full size, and check:

1. **Spelling.** Letter by letter. Diacritics are the failure point: umlauts,
   accents, cedillas. A German render that says "FETER FÜR DRAUSEN" instead of
   "FEUER FÜR DRAUSSEN" is a discard, and it is not obvious at a glance.
2. **The translation is right**, not just plausible-looking text in roughly the
   right language.
3. **The brand name is untouched** and still spelled correctly.
4. **Layout held** — same font, same colour, same position, same size
   relationship. Longer target languages (German, French) push lines wider;
   check nothing runs off the frame or overlaps.
5. **The very first frame is already translated.** In one run out of five the
   model crossfaded instead of swapping: the opening showed the original
   English, both languages ghosted over each other at around 0.3 s, and only
   from ~0.5 s on was the translation clean. An ad whose first frames are in
   the wrong language is a discard. The leftmost tile of the contact sheet is
   sampled early enough to catch this — it is the tile people skip.
   Fix: re-run, or trim the first half second off the output.
6. **Text is stable across the rest of the clip** — it should not flicker,
   morph or re-spell itself between frames.
7. **Nothing else changed.**

In a batch, do this **per language**. A clean German render says nothing about
the French one, and the language you cannot read yourself is exactly the one
that will ship with a typo. If you are not confident in a language, say so and
tell the user to have a native speaker check that variant.

If any of that fails, re-run. If it fails twice the same way, the honest answer
is to set that headline in your layout tool instead — say that rather than
shipping a broken word.

## Prompt rules

> Translate the text that is already visible in the frame into *&lt;language&gt;*.
> Keep the same fonts, colours, sizes and positions. Do not add text anywhere,
> and leave surfaces that have no text on them blank. Leave *&lt;keep&gt;* in the
> original language. Keep everything else the same.

**The wording "labels and signage" used to be in this recipe and had to go.**
It reads any surface as somewhere labels belong. On one run it printed a
garbled wordmark onto a plain black bottle; on another it turned a grey hoodie
black, stamped an invented "SHARP" logo across it and added a sentence nobody
wrote. The translation itself was correct both times, which is exactly what
makes it dangerous. Old wording: 2 of 3 runs unusable. Current wording: 2 of 2
clean. See `examples/failure-invented-branding.jpg`.

- **Do not paste the target translation into the prompt.** Asking the model to
  reproduce a given string letter-for-letter performs worse than asking it to
  translate; it renders text, it does not typeset.
- **Do not ask for a language change and a layout change in one call.**
- **Never add words like "labels", "signage" or "branding" back in.** That is
  the exact failure above.

## Notes

- Cost, measured rather than quoted: an 8-second edit costs **1.71 USD**, i.e.
  **0.213 USD per second** — the 0.13 USD/s on fal's model page is the output
  share only. A shorter or smaller source is cheaper.
- Output is 720p at 24 fps, with audio, in the length of the source — 1280×720
  for a landscape source, 720×1280 for a portrait one. 720p is the ceiling, so
  small print is out of reach; headlines, captions and signage are the
  realistic target.
- Voiceover and dialogue are not touched. Voice editing is not supported by the
  endpoint at all.
- The example run in `examples/` translated a burned-in "STAY SHARP" into
  "BLEIB SMART" on the first attempt, in the same font, weight, colour and
  position, with nothing else in the frame touched. Treat that as the good
  case, not the guaranteed one.
- Google blocks editing *uploaded* videos in the EEA, UK and Switzerland, but
  allows editing model-generated ones. Calls routed through fal do not originate
  in the EEA at all, which is why runs from Germany went through. See the README.
