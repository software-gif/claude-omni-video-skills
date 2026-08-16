#!/usr/bin/env python3
"""
omni.py — ein Clip rein, viele Varianten raus.

Ruft Gemini Omni Flash direkt bei Google auf (kein fal, kein SDK). Jede Skill
in .claude/skills/ ist ein Wrapper um genau ein Unterkommando hier.

    python3 scripts/omni.py create           --prompt "..." --aspect 9:16
    python3 scripts/omni.py animate          --image packshot.jpg --prompt "slow orbit"
    python3 scripts/omni.py swap-background  --input out/clip.mp4 --to "a rainy Tokyo street"
    python3 scripts/omni.py change-angle     --input out/clip.mp4 --angle wide --angle close-up
    python3 scripts/omni.py transform-object --input out/clip.mp4 --object "the jar" --to "frosted glass"
    python3 scripts/omni.py localize         --input out/clip.mp4 --lang German --lang French
    python3 scripts/omni.py raw              --input out/clip.mp4 --prompt "..."

--to, --angle und --lang sind wiederholbar; jede Angabe ist ein eigener Aufruf.

WICHTIG ZUR HERKUNFT DES CLIPS
Google erlaubt aus EWR, Schweiz und UK das Bearbeiten *hochgeladener* Videos
nicht — nachgemessen, mit korrekter Payload und harmlosem Prompt. Erlaubt ist
das Bearbeiten von Clips, die das Modell selbst erzeugt hat.

Deshalb arbeiten die vier Skills auf Ergebnissen von `create` oder `animate`:
Jeder Lauf schreibt seine interaction id in die Manifest-Datei neben dem Video,
und --input findet sie dort von selbst. Du hantierst nie mit IDs.

    python3 scripts/omni.py animate --image packshot.jpg --prompt "slow orbit" --out ./out
    python3 scripts/omni.py swap-background --input out/animate-*.mp4 --to "..."

Env: GEMINI_API_KEY (https://aistudio.google.com/apikey) — in .env neben dem Repo.
"""

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import google_omni as api  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Schätzwerte für --dry-run. Abgerechnet wird nach Tokens, und jeder fertige
# Lauf weist seinen ECHTEN Preis aus den mitgelieferten Zahlen aus — diese
# Konstanten dienen nur der Vorschau.
# Gemessen: ~5.900 Ausgabe-Tokens je Sekunde Video, ~5.800 Eingabe-Tokens je
# Sekunde bei einem Video als Eingabe.
TOKENS_OUT_PER_SECOND = 5900
TOKENS_IN_PER_SECOND = 5800


def estimate(seconds, with_video_input):
    out = seconds * TOKENS_OUT_PER_SECOND * api.USD_PER_OUTPUT_TOKEN
    inp = seconds * TOKENS_IN_PER_SECOND * api.USD_PER_INPUT_TOKEN if with_video_input else 0
    return out + inp


# --------------------------------------------------------------------------
# Prompt-Rezepte
#
# Omni-Edit nimmt EINE Anweisung in Alltagssprache. Lange, verschachtelte
# Prompts machen das Ergebnis schlechter, nicht besser. Jedes Rezept besteht
# deshalb aus genau drei Teilen:
#
#   1. die eine Änderung
#   2. ein kurzer Lock-Satz gegen die für diesen Job typische Drift
#   3. "Keep everything else the same."  (aus Googles Prompt-Hinweisen, wirkt messbar)
#
# Der Markenkontext gehört ausdrücklich NICHT hier hinein. Er steuert, welchen
# Text Claude in --to schreibt, nicht wie lang der Prompt wird. Siehe
# brand/README.md und die "Prompt rules"-Abschnitte in den SKILL.md-Dateien.
#
# Nichts hier ergänzen, ohne es zu messen: Jeder zusätzliche Satz ist eine
# weitere Erlaubnis, etwas umzubauen. Die gemessenen Grenzen stehen im README.
# --------------------------------------------------------------------------

KEEP = "Keep everything else the same."

# Vage Kadrierungswörter liefern vage Kadrierungen. "a closer shot of the main
# subject" kam zweimal hintereinander als praktisch unveränderte Einstellung
# zurück; erst "framing only … filling the frame" erzeugte eine echte
# Nahaufnahme. Deshalb benennt jeder Eintrag, was im Bild sein soll und was
# nicht — geraten wird hier nichts.
ANGLES = {
    "wide": "a wider shot that reveals more of the surroundings",
    "close-up": "a tight close-up framing only the subject's head and the product, "
                "filling the frame",
    "extreme-close-up": "an extreme close-up filling the frame with just the product, "
                        "cropping everything else out",
    "over-the-shoulder": "an over-the-shoulder shot from behind the main subject",
    "low": "a low camera angle looking up at the main subject",
    "high": "a high camera angle looking down at the main subject",
    "profile": "a side-on profile view of the main subject",
}


def prompt_swap_background(scene):
    # "same action" kam nachträglich dazu: Ohne das Wort hat das Modell in einer
    # von vier Marktvarianten eine Trinkbewegung erfunden, die es in der Quelle
    # nicht gab. Mit ihm blieb genau diese Variante sauber.
    return (
        f"Change only the background to {scene}. "
        f"Do not change the people or products in the shot: same faces, same clothing, "
        f"same colours, same position in the frame, same action and movement. {KEEP}"
    )


def prompt_change_angle(shot):
    # "action" ist das entscheidende Wort. Ohne es hat das Modell in einem
    # Over-the-Shoulder-Take eine Trinkbewegung erfunden, die es in der Quelle
    # nicht gab; mit ihm nicht. Gleiche Quelle, gleicher Winkel, direkter A/B.
    return (
        f"Re-frame this shot as {shot}. "
        f"Keep the same subject, action, wardrobe, lighting and setting. {KEEP}"
    )


def prompt_transform_object(obj, target):
    # "label, branding" ausdrücklich zu erhalten, hat im A/B den eingebrannten
    # Text gerettet: ohne die Wörter war die Headline ab Bildmitte weg, mit
    # ihnen stand sie durchgehend. Gleiche Quelle, gleiches Zielmaterial.
    return (
        f"Change {obj} to {target}. "
        f"Keep its shape, position, label, branding and motion the same. "
        f"Keep everything else in the scene the same."
    )


def prompt_localize(lang, keep=None):
    # "labels and signage" stand hier früher mit drin und war ein Fehler: In
    # einem Testlauf hat das Modell daraufhin einer glatten schwarzen Flasche
    # einen erfundenen Schriftzug verpasst. Die Formulierung lädt dazu ein,
    # Produktoberflächen als Ort für Etiketten zu lesen. Jetzt: nur das
    # übersetzen, was schon da ist, und leere Flächen leer lassen.
    tail = f" Leave {keep} in the original language." if keep else ""
    return (
        f"Translate the text that is already visible in the frame into {lang}. "
        f"Keep the same fonts, colours, sizes and positions. "
        f"Do not add text anywhere, and leave surfaces that have no text on them blank."
        f"{tail} {KEEP}"
    )


def plan(args):
    """Was gerendert werden soll, als Liste von (Kurzname, Prompt)."""
    if args.command == "swap-background":
        return [(slugify(scene, 32), prompt_swap_background(scene)) for scene in args.to]
    if args.command == "change-angle":
        shots = [(key, ANGLES[key]) for key in (args.angle or [])]
        shots += [(slugify(free, 32), free) for free in (args.to or [])]
        return [(slug, prompt_change_angle(shot)) for slug, shot in shots]
    if args.command == "transform-object":
        return [(slugify(t, 32), prompt_transform_object(args.object, t)) for t in args.to]
    if args.command == "localize":
        return [(lang_slug(lang), prompt_localize(lang, args.keep)) for lang in args.lang]
    if args.command == "raw":
        return [("raw", args.prompt)]
    if args.command in ("create", "animate"):
        return [(slugify(args.prompt, 32), args.prompt)]
    raise ValueError(args.command)


# --------------------------------------------------------------------------
# Infrastruktur
# --------------------------------------------------------------------------




def slugify(text, limit=48):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (slug[:limit].rstrip("-")) or "run"


# Kurze Dateinamen-Kürzel statt "brazilian-portuguese".
LANG_SLUGS = {
    "arabic": "ar", "chinese": "zh", "mandarin": "zh", "danish": "da", "dutch": "nl",
    "english": "en", "filipino": "fil", "finnish": "fi", "french": "fr", "german": "de",
    "greek": "el", "hindi": "hi", "indonesian": "id", "italian": "it", "japanese": "ja",
    "korean": "ko", "malay": "ms", "norwegian": "no", "polish": "pl", "portuguese": "pt",
    "romanian": "ro", "russian": "ru", "spanish": "es", "swedish": "sv", "thai": "th",
    "turkish": "tr", "ukrainian": "uk", "vietnamese": "vi",
}


def lang_slug(language):
    key = (language or "").strip().lower()
    if key in LANG_SLUGS:
        return LANG_SLUGS[key]

    base = key.split("(")[0].strip()          # "Spanish (Mexico)" -> "es-mexico"
    if base in LANG_SLUGS:
        region = slugify(key.split("(")[-1].rstrip(")"), 12)
        return f"{LANG_SLUGS[base]}-{region}" if region != "run" else LANG_SLUGS[base]

    words = base.split()                      # "Brazilian Portuguese" -> "pt-brazilian"
    if len(words) > 1 and words[-1] in LANG_SLUGS:
        return f"{LANG_SLUGS[words[-1]]}-{slugify(' '.join(words[:-1]), 12)}"

    return slugify(key, 16)


def claim_version(out_dir, stem, ext=".mp4"):
    """Nächste freie _v1/_v2/… beanspruchen, atomar.

    Ein erneuter Lauf darf ein gutes Ergebnis nie überschreiben — dafür hat es
    zu viel gekostet. O_EXCL macht das auch dann sicher, wenn mehrere Läufe
    parallel in denselben Ordner schreiben.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    version = 1
    while True:
        candidate = out_dir / f"{stem}_v{version}{ext}"
        try:
            os.close(os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644))
            return candidate
        except FileExistsError:
            version += 1







# --- Kontaktblätter -------------------------------------------------------
#
# Claude kann kein Video abspielen, aber ein JPG lesen. Deshalb schreibt jeder
# Lauf ein Vergleichsbild (Quelle oben, Ergebnis unten) und ein Batch am Ende
# einen Überblicksstreifen über alle Varianten. Das ist die Grundlage dafür,
# dass der Prüfschritt in jeder SKILL.md überhaupt ausführbar ist.
# Braucht ffmpeg; fehlt es, wird still übersprungen.


def _has_ffmpeg():
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _duration(path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        return float(out.stdout.strip().splitlines()[0])
    except Exception:  # noqa: BLE001
        return None




def _grab(path, seconds, target, height=360):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{max(seconds, 0):.2f}", "-i", str(path),
         "-frames:v", "1", "-vf", f"scale=-2:{height}", str(target)],
        check=True, timeout=60,
    )


def _width(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    return int(out.stdout.strip().splitlines()[0])


def _stack(frames, target, per_row, work_dir):
    """Frames zu einem Raster montieren. per_row Spalten, Reihen untereinander.

    Reihenweise in zwei Durchgängen statt in einem großen Filtergraph: Bei einer
    unvollständigen letzten Reihe (5 Kacheln auf 3 Spalten) sind die Reihen
    verschieden breit, und vstack verlangt gleiche Breite. Die kurze Reihe wird
    deshalb weiß aufgefüllt.
    """
    rows = []
    for start in range(0, len(frames), per_row):
        chunk = frames[start:start + per_row]
        row_path = work_dir / f"row-{target.stem}-{len(rows)}.jpg"
        if len(chunk) == 1:
            shutil.copyfile(chunk[0], row_path)
        else:
            args = ["ffmpeg", "-v", "error", "-y"]
            for frame in chunk:
                args += ["-i", str(frame)]
            args += ["-filter_complex",
                     "".join(f"[{i}]" for i in range(len(chunk))) + f"hstack={len(chunk)}",
                     "-q:v", "3", str(row_path)]
            subprocess.run(args, check=True, timeout=180)
        rows.append(row_path)

    if len(rows) == 1:
        shutil.copyfile(rows[0], target)
        return target

    widest = max(_width(row) for row in rows)
    args = ["ffmpeg", "-v", "error", "-y"]
    for row in rows:
        args += ["-i", str(row)]
    chain = [f"[{i}]pad={widest}:ih:(ow-iw)/2:0:white[p{i}]" for i in range(len(rows))]
    filt = ";".join(chain) + ";" + "".join(f"[p{i}]" for i in range(len(rows))) \
        + f"vstack={len(rows)}"
    args += ["-filter_complex", filt, "-q:v", "3", str(target)]
    subprocess.run(args, check=True, timeout=180)
    return target


def contact_sheet(source, result, target, work_dir, tag="s"):
    """Quelle oben, Ergebnis unten, je drei Zeitpunkte."""
    if not _has_ffmpeg():
        return None
    length = _duration(result)
    if not length:
        return None
    stamps = [length * 0.05, length * 0.5, length * 0.93]
    frames = []
    try:
        for role, clip in (("a", source), ("b", result)):
            if clip is None or not pathlib.Path(clip).exists():
                continue
            clip_len = _duration(clip) or length
            for index, second in enumerate(stamps):
                frame = work_dir / f"sheet-{tag}{role}{index}.jpg"
                _grab(clip, min(second, clip_len - 0.05), frame)
                frames.append(frame)
        if not frames:
            return None
        return _stack(frames, target, 3, work_dir)
    except Exception:  # noqa: BLE001 — Komfort, kein Muss
        return None


def overview_strip(source, outputs, target, work_dir):
    """Quelle plus alle Varianten nebeneinander, jeweils Bildmitte."""
    if not _has_ffmpeg() or len(outputs) < 2:
        return None
    clips = ([source] if source and pathlib.Path(source).exists() else []) + list(outputs)
    frames = []
    try:
        for index, clip in enumerate(clips):
            length = _duration(clip)
            if not length:
                continue
            frame = work_dir / f"overview-{index}.jpg"
            _grab(clip, length * 0.5, frame)
            frames.append(frame)
        if len(frames) < 2:
            return None
        per_row = len(frames) if len(frames) <= 3 else (len(frames) + 1) // 2
        return _stack(frames, target, per_row, work_dir)
    except Exception:  # noqa: BLE001
        return None







# --------------------------------------------------------------------------


def resolve_source(source):
    """Woher der Clip kommt und wie er bearbeitet werden darf.

    Gibt (interaction_id, lokaler Pfad) zurück. Ist die id da, wird verkettet —
    der einzige Weg, der aus dem EWR heraus erlaubt ist. Fehlt sie, versuchen
    wir den Upload und melden die Sperre verständlich, falls sie greift.
    """
    path = pathlib.Path(source).expanduser()
    if not path.exists():
        sys.exit(f"Clip nicht gefunden: {path}")
    manifest = path.with_suffix(".json")
    if manifest.exists():
        try:
            entry = json.loads(manifest.read_text())
            if entry.get("interaction_id"):
                return entry["interaction_id"], path
        except ValueError:
            pass
    return None, path


def source_seconds(source):
    """Länge der Quelle, wenn sie lokal vorliegt und ffprobe da ist."""
    if not source or not shutil.which("ffprobe"):
        return None
    path = pathlib.Path(source).expanduser()
    return _duration(path) if path.exists() else None


def run_once(command, prompt, label, *, aspect=None, duration=None,
             video_uri=None, image_path=None, interaction_id=None):
    """Ein Omni-Aufruf. Gibt (Video-Bytes, Interaktion) zurück."""
    task = {"create": "text_to_video", "animate": "image_to_video"}.get(command, "edit")
    # Google kennt kein Dauer-Feld — die Länge wird im Prompt gesagt. Nur beim
    # Erzeugen sinnvoll; ein Edit erbt die Länge der Quelle.
    if duration and task != "edit":
        prompt = f"{prompt.rstrip().rstrip('.')}. About {duration} seconds long."
    # Bei task=edit lehnt Google ein gesetztes Seitenverhältnis ab; das Ergebnis
    # erbt es ohnehin von der Quelle.
    # Bei Verkettung lehnt Google ein gesetztes video_config.task ab — der
    # Kontext der Vorgänger-Interaktion sagt schon, worum es geht.
    chained = bool(interaction_id)
    result = api.interact(
        prompt,
        task=None if chained else task,
        aspect=None if (chained or task == "edit") else aspect,
        video_uri=video_uri,
        image_path=image_path,
        previous_interaction_id=interaction_id,
        on_progress=lambda m: print(f"  {label}{m}", flush=True),
    )
    return api.extract_video(result), result


def build_parser():
    parser = argparse.ArgumentParser(
        prog="omni.py",
        description="Gemini Omni Flash, direkt bei Google — Video-Edit, Text-to-Video, Bild-to-Video",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(sp, needs_input=True):
        if needs_input:
            sp.add_argument("--input", required=True,
                            help="Clip aus einem früheren Lauf (wird verkettet) oder eigene Datei")
        sp.add_argument("--out", default="./out", help="Zielordner (Default ./out)")
        sp.add_argument("--name", help="Basisname der Ausgabedateien")
        sp.add_argument("--runs", type=int, default=1, help="Generierungen pro Variante (Default 1)")
        sp.add_argument("--dry-run", action="store_true", help="Nur den Plan zeigen")
        sp.add_argument("--json", action="store_true", help="Ergebnis als JSON auf stdout")
        return sp

    sp = common(sub.add_parser("swap-background", help="Hintergrund tauschen"))
    sp.add_argument("--to", action="append", required=True, metavar="SZENE",
                    help='Neue Szene. Mehrfach angeben für mehrere Märkte.')

    sp = common(sub.add_parser("change-angle", help="Kameraperspektive ändern"))
    sp.add_argument("--angle", action="append", choices=sorted(ANGLES),
                    help="Vordefinierte Perspektive. Mehrfach angeben für eine Sequenz.")
    sp.add_argument("--to", action="append", metavar="PERSPEKTIVE",
                    help="Freitext-Perspektive, zusätzlich oder statt --angle.")

    sp = common(sub.add_parser("transform-object", help="Material, Farbe oder Finish ändern"))
    sp.add_argument("--object", required=True, help='Was, z. B. "the sneaker"')
    sp.add_argument("--to", action="append", required=True, metavar="MATERIAL",
                    help="Zielmaterial. Mehrfach angeben für eine Colourway-Reihe.")

    sp = common(sub.add_parser("localize", help="On-Screen-Text übersetzen"))
    sp.add_argument("--lang", action="append", required=True, metavar="SPRACHE",
                    help="Zielsprache. Mehrfach angeben für mehrere Märkte.")
    sp.add_argument("--keep", help='Was unübersetzt bleibt, z. B. "the brand name"')

    sp = common(sub.add_parser("raw", help="Eigene Anweisung, ohne Rezept"))
    sp.add_argument("--prompt", required=True)

    sp = common(sub.add_parser("create", help="Testclip aus Text erzeugen (kein Input nötig)"),
                needs_input=False)
    sp.add_argument("--prompt", required=True)
    sp.add_argument("--aspect", default="16:9", choices=["16:9", "9:16"])
    sp.add_argument("--duration", type=int, default=8, help="3 bis 10 Sekunden (Default 8)")

    sp = common(sub.add_parser("animate", help="Aus einem Produktfoto einen Clip machen"),
                needs_input=False)
    sp.add_argument("--image", required=True, help="Packshot als lokale Bilddatei")
    sp.add_argument("--prompt", required=True, help="Wie sich das Bild bewegen soll")
    sp.add_argument("--aspect", default="16:9", choices=["16:9", "9:16"])
    sp.add_argument("--duration", type=int, default=8, help="3 bis 10 Sekunden (Default 8)")

    return parser


def main():
    args = build_parser().parse_args()

    if args.command == "change-angle" and not (args.angle or args.to):
        sys.exit("change-angle braucht mindestens ein --angle oder --to")
    if args.command in ("create", "animate") and not 3 <= args.duration <= 10:
        sys.exit("--duration muss zwischen 3 und 10 Sekunden liegen")
    if args.command == "animate" and not pathlib.Path(args.image).expanduser().exists():
        sys.exit(f"Bild nicht gefunden: {args.image}")

    generating = args.command in ("create", "animate")
    jobs = plan(args)
    total = len(jobs) * args.runs

    print(f"\n  {args.command} — {len(jobs)} Variante(n)"
          + (f", {args.runs} Generierungen je Variante" if args.runs > 1 else ""))
    for slug, prompt in jobs:
        print(f"\n  [{slug}]\n  {prompt}")

    seconds = args.duration if generating else (source_seconds(args.input) or 8)
    basis = {"create": "Text-to-Video", "animate": "Bild-to-Video"}.get(args.command, "Video-Edit")
    print(f"\n  {total} Aufruf(e) × {seconds:.0f} s ({basis}) "
          f"≈ {estimate(seconds, not generating) * total:.2f} USD geschätzt")
    print("  Der tatsächliche Preis steht nach jedem Lauf — Google liefert die "
          "Tokenzahlen mit.")

    if args.dry_run:
        print("  Dry run, es wurde nichts ausgegeben.")
        return
    if not _has_ffmpeg():
        print("  Hinweis: ffmpeg fehlt, es werden keine Kontaktblätter geschrieben.")
    if not api.load_key():
        sys.exit("GEMINI_API_KEY fehlt. In .env eintragen:\n"
                 "  GEMINI_API_KEY=…    (https://aistudio.google.com/apikey)")

    out_dir = pathlib.Path(args.out).expanduser()
    work_dir = out_dir / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)

    interaction_id = video_uri = source_local = None
    if not generating:
        interaction_id, source_local = resolve_source(args.input)
        if interaction_id:
            print(f"\n  Quelle stammt aus einem früheren Lauf — wird verkettet "
                  f"(erlaubt im EWR).")
        else:
            print(f"\n  Kein Manifest neben {pathlib.Path(args.input).name}: "
                  f"Clip wird hochgeladen.")
            try:
                video_uri = api.upload_file(args.input, on_progress=lambda m: print("  " + m))
            except api.OmniError as exc:
                sys.exit(f"  {exc}")

    base = args.name or args.command
    written, manifest, spent = [], [], 0.0
    step = 0
    aborted = None

    for slug, prompt in jobs:
        if aborted:
            break
        for _ in range(args.runs):
            if aborted:
                break
            step += 1
            label = f"[{step}/{total}] " if total > 1 else ""
            stem = args.name if (args.name and len(jobs) == 1) else f"{base}-{slug}"

            try:
                blob, result = run_once(
                    args.command, prompt, label,
                    aspect=getattr(args, "aspect", None),
                    duration=getattr(args, "duration", None),
                    video_uri=video_uri,
                    image_path=args.image if args.command == "animate" else None,
                    interaction_id=interaction_id,
                )
            except api.RegionBlocked as exc:
                print(f"\n  {exc}")
                aborted = "region"
                break
            except api.OmniError as exc:
                print(f"  {label}Fehlgeschlagen ({slug}): {exc}")
                continue

            target = claim_version(out_dir, stem)
            target.write_bytes(blob)
            written.append(target)
            price = api.cost(result)
            spent += price
            print(f"  {label}→ {target}  ({len(blob) / 1_048_576:.1f} MB, "
                  f"{result.get('_seconds', 0):.0f}s, {price:.3f} USD)")

            sheet = contact_sheet(source_local, target,
                                  out_dir / f"{target.stem}-compare.jpg",
                                  work_dir, tag=f"{step}")
            if sheet:
                print(f"  {label}→ {sheet}  (oben Quelle, unten Ergebnis)")

            usage = result.get("usage") or {}
            entry = {
                "command": args.command, "variant": slug, "prompt": prompt,
                "model": api.MODEL,
                "interaction_id": result.get("id"),
                "chained_from": interaction_id,
                "source": str(source_local) if source_local else None,
                "output": str(target),
                "compare": str(sheet) if sheet else None,
                "seconds": result.get("_seconds"),
                "usd": round(price, 4),
                "tokens_in": usage.get("total_input_tokens"),
                "tokens_out": usage.get("total_output_tokens"),
            }
            manifest.append(entry)
            (out_dir / f"{target.stem}.json").write_text(
                json.dumps(entry, indent=2, ensure_ascii=False))

    if not written:
        sys.exit(1)

    if len(written) > 1:
        strip = overview_strip(source_local, written, out_dir / f"{base}-overview.jpg", work_dir)
        if strip:
            print(f"\n  → {strip}  (Quelle plus alle Varianten)")
        (out_dir / f"{base}-batch.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False))

    print(f"\n  {len(written)} von {total} Aufruf(en) erfolgreich, "
          f"{spent:.2f} USD tatsächlich abgerechnet.")
    if written:
        print(f"  Weiterbearbeiten: --input {written[0]}")

    if args.json:
        print(json.dumps({"outputs": [str(x) for x in written], "usd": round(spent, 4),
                          "runs": manifest}, ensure_ascii=False))


if __name__ == "__main__":
    main()
