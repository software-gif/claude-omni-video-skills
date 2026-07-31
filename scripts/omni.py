#!/usr/bin/env python3
"""
omni.py — ein Clip rein, viele Varianten raus.

Ruft Gemini Omni Flash über fal.ai auf. Jede Skill in .claude/skills/ ist ein
Wrapper um genau ein Unterkommando hier.

    python3 scripts/omni.py swap-background  --input clip.mp4 --to "a rainy Tokyo street" --to "an alpine village"
    python3 scripts/omni.py change-angle     --input clip.mp4 --angle wide --angle close-up
    python3 scripts/omni.py transform-object --input clip.mp4 --object "the bottle" --to "brushed chrome"
    python3 scripts/omni.py localize         --input clip.mp4 --lang German --lang French
    python3 scripts/omni.py raw              --input clip.mp4 --prompt "..."
    python3 scripts/omni.py create           --prompt "..." --aspect 9:16 --duration 8

--to, --angle und --lang sind wiederholbar. Jede Angabe ist ein eigener
Modellaufruf; das Skript rendert sie nacheinander und legt am Ende einen
Überblicksstreifen über alle Varianten an.

Env: FAL_KEY (https://fal.ai/dashboard/keys) — in .env neben dem Repo oder exportiert.
"""

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.request

ENDPOINT_EDIT = "google/gemini-omni-flash/edit"
ENDPOINT_CREATE = "google/gemini-omni-flash"

# Preis laut fal-Modellseite: ~0,13 $ pro Sekunde 720p-Video.
USD_PER_SECOND = 0.13

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# Prompt-Rezepte
#
# Omni-Edit nimmt EINE Anweisung in Alltagssprache. Lange, verschachtelte
# Prompts machen das Ergebnis schlechter, nicht besser. Jedes Rezept besteht
# deshalb aus genau drei Teilen:
#
#   1. die eine Änderung
#   2. ein kurzer Lock-Satz gegen die für diesen Job typische Drift
#   3. "Keep everything else the same."  (von fal empfohlen, wirkt messbar)
#
# Der Markenkontext gehört ausdrücklich NICHT hier hinein. Er steuert, welchen
# Text Claude in --to schreibt, nicht wie lang der Prompt wird. Siehe
# brand/README.md und die "Prompt rules"-Abschnitte in den SKILL.md-Dateien.
#
# Nichts hier ergänzen, ohne es zu messen: Jeder zusätzliche Satz ist eine
# weitere Erlaubnis, etwas umzubauen. Die gemessenen Grenzen stehen im README.
# --------------------------------------------------------------------------

KEEP = "Keep everything else the same."

ANGLES = {
    "wide": "a wider shot that reveals more of the surroundings",
    "close-up": "a closer shot of the main subject",
    "extreme-close-up": "an extreme close-up of the main subject",
    "over-the-shoulder": "an over-the-shoulder shot from behind the main subject",
    "low": "a low camera angle looking up at the main subject",
    "high": "a high camera angle looking down at the main subject",
    "profile": "a side-on profile view of the main subject",
}


def prompt_swap_background(scene):
    return (
        f"Change only the background to {scene}. "
        f"Do not change the people or products in the shot: same faces, same clothing, "
        f"same colours, same position in the frame, same movement. {KEEP}"
    )


def prompt_change_angle(shot):
    return (
        f"Re-frame this shot as {shot}. "
        f"Keep the same scene, the same subject, the same moment and the same lighting. {KEEP}"
    )


def prompt_transform_object(obj, target):
    return (
        f"Change {obj} to {target}. "
        f"Keep its shape, size and position identical, and keep the way it moves in the shot. {KEEP}"
    )


def prompt_localize(lang, keep=None):
    tail = f" Leave {keep} in the original language." if keep else ""
    return (
        f"Translate all on-screen text, captions, labels and signage into {lang}. "
        f"Keep the same fonts, colours, sizes and positions.{tail} {KEEP}"
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
        return [(slugify(lang, 24), prompt_localize(lang, args.keep)) for lang in args.lang]
    if args.command == "raw":
        return [("raw", args.prompt)]
    if args.command == "create":
        return [(slugify(args.prompt, 32), args.prompt)]
    raise ValueError(args.command)


# --------------------------------------------------------------------------
# Infrastruktur
# --------------------------------------------------------------------------


def load_key():
    if os.environ.get("FAL_KEY"):
        return os.environ["FAL_KEY"]
    for candidate in (REPO_ROOT / ".env", pathlib.Path.cwd() / ".env"):
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line.startswith("FAL_KEY=") and not line.startswith("#"):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if value:
                        os.environ["FAL_KEY"] = value
                        return value
    return None


def slugify(text, limit=48):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (slug[:limit].rstrip("-")) or "run"


def resolve_source(fal_client, source, work_dir):
    """Gibt (url, lokaler Pfad) zurück. Lokale Datei wird hochgeladen,
    entfernte Datei fürs Kontaktblatt einmal heruntergeladen."""
    if source.startswith(("http://", "https://")):
        local = work_dir / "source.mp4"
        try:
            download(source, local)
        except Exception:  # noqa: BLE001 — nur fürs Kontaktblatt, nicht kritisch
            local = None
        return source, local
    if source.startswith("data:"):
        return source, None

    path = pathlib.Path(source).expanduser()
    if not path.exists():
        sys.exit(f"Input nicht gefunden: {path}")

    # Denselben Clip nicht bei jedem Lauf neu hochladen. fal antwortet auf zu
    # viele Upload-Tokens hintereinander mit 403; ein Cache pro Datei und
    # Änderungszeit spart Zeit, Bandbreite und genau diesen Fehler. Bei einem
    # Batch über fünf Märkte wird so einmal hochgeladen statt fünfmal.
    stat = path.stat()
    fingerprint = f"{path.resolve()}::{stat.st_size}::{int(stat.st_mtime)}"
    cache_dir = REPO_ROOT / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "uploads.json"
    cache = {}
    if cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text())
        except ValueError:
            cache = {}
    if fingerprint in cache:
        print(f"  {path.name} bereits hochgeladen, nutze den Cache.", flush=True)
        return cache[fingerprint], path

    print(f"  Upload {path.name} ({stat.st_size / 1_048_576:.1f} MB) …", flush=True)
    try:
        url = fal_client.upload_file(str(path))
    except Exception as exc:  # noqa: BLE001 — der Nutzer braucht den Grund, nicht den Stack
        # fal schreibt den eigentlichen Grund in den Antwort-Body ("User is locked.
        # Reason: Exhausted balance."). Der str() der Exception enthält nur URL und
        # Status, also den Body herausziehen — sonst sieht man bloß ein nacktes 403.
        detail = getattr(getattr(exc, "response", None), "text", "") or ""
        sys.exit(
            f"Upload fehlgeschlagen: {type(exc).__name__}: {exc}"
            + (f"\n  fal sagt: {detail.strip()[:300]}" if detail else "")
            + "\n  Häufigste Ursachen: aufgebrauchtes Guthaben (fal.ai/dashboard/billing), "
            "ungültiger FAL_KEY, oder zu viele parallele Läufe.\n"
            "  Alternativ --input mit einer öffentlichen URL aufrufen — das umgeht den Upload."
        )

    cache[fingerprint] = url
    cache_file.write_text(json.dumps(cache, indent=2))
    return url, path


def download(url, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, open(target, "wb") as handle:
        shutil.copyfileobj(response, handle)
    return target


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


def run_once(fal_client, endpoint, arguments, label):
    print(f"  {label}Omni läuft …", flush=True)
    started = time.time()
    handle = fal_client.submit(endpoint, arguments=arguments)
    print(f"  {label}request {handle.request_id}", flush=True)
    result = handle.get()
    video = result.get("video") or {}
    if not video.get("url"):
        raise RuntimeError(f"Kein Video in der Antwort: {json.dumps(result)[:400]}")
    return video, time.time() - started, handle.request_id


# --------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        prog="omni.py",
        description="Gemini Omni Flash über fal.ai — Video-Edit und Text-to-Video",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(sp, needs_input=True):
        if needs_input:
            sp.add_argument("--input", required=True, help="Lokale Videodatei oder öffentliche URL")
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

    return parser


def main():
    args = build_parser().parse_args()

    if args.command == "change-angle" and not (args.angle or args.to):
        sys.exit("change-angle braucht mindestens ein --angle oder --to")
    if args.command == "create" and not 3 <= args.duration <= 10:
        sys.exit("--duration muss zwischen 3 und 10 Sekunden liegen")

    jobs = plan(args)
    total = len(jobs) * args.runs

    print(f"\n  {args.command} — {len(jobs)} Variante(n)"
          + (f", {args.runs} Generierungen je Variante" if args.runs > 1 else ""))
    for slug, prompt in jobs:
        print(f"\n  [{slug}]\n  {prompt}")

    seconds = args.duration if args.command == "create" else 8
    print(f"\n  {total} Modellaufruf(e), grob ${USD_PER_SECOND * seconds * total:.2f} "
          f"bei {seconds} s Video.")

    if args.dry_run:
        print("  Dry run, es wurde nichts ausgegeben.")
        return
    if not _has_ffmpeg():
        print("  Hinweis: ffmpeg fehlt, es werden keine Kontaktblätter geschrieben.")

    if not load_key():
        sys.exit("FAL_KEY fehlt. In .env eintragen: FAL_KEY=…  (https://fal.ai/dashboard/keys)")

    try:
        import fal_client
    except ImportError:
        sys.exit("fal-client fehlt:  pip install fal-client")

    out_dir = pathlib.Path(args.out).expanduser()
    work_dir = out_dir / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)

    if args.command == "create":
        endpoint, source_url, source_local = ENDPOINT_CREATE, None, None
    else:
        endpoint = ENDPOINT_EDIT
        source_url, source_local = resolve_source(fal_client, args.input, work_dir)

    base = args.name or args.command
    written, manifest = [], []
    step = 0

    for slug, prompt in jobs:
        for run in range(1, args.runs + 1):
            step += 1
            label = f"[{step}/{total}] " if total > 1 else ""
            stem = args.name if (args.name and len(jobs) == 1) else f"{base}-{slug}"
            if args.runs > 1:
                stem = f"{stem}-{run}"

            if args.command == "create":
                arguments = {"prompt": prompt, "aspect_ratio": args.aspect,
                             "duration": args.duration}
            else:
                arguments = {"prompt": prompt, "video_url": source_url}

            try:
                video, took, request_id = run_once(fal_client, endpoint, arguments, label)
            except Exception as exc:  # noqa: BLE001 — Meldung für den Nutzer, nicht fürs Log
                message = str(exc)
                print(f"  {label}Fehlgeschlagen ({slug}): {type(exc).__name__}: {message}")
                if "not available" in message.lower() or "region" in message.lower():
                    print("  Hinweis: Google sperrt den Video-Edit hochgeladener Clips in "
                          "EWR/UK/CH. Siehe README, Abschnitt Grenzen.")
                continue

            target = download(video["url"], out_dir / f"{stem}.mp4")
            written.append(target)
            print(f"  {label}→ {target}  ({video.get('file_size', 0) / 1_048_576:.1f} MB, {took:.0f}s)")

            sheet = contact_sheet(source_local, target, out_dir / f"{stem}-compare.jpg",
                                  work_dir, tag=f"{step}")
            if sheet:
                print(f"  {label}→ {sheet}  (oben Quelle, unten Ergebnis)")

            entry = {
                "command": args.command, "variant": slug, "prompt": prompt,
                "endpoint": endpoint, "request_id": request_id,
                "source": str(source_local) if source_local else source_url,
                "source_url": source_url, "output": str(target),
                "compare": str(sheet) if sheet else None, "seconds": round(took, 1),
            }
            manifest.append(entry)
            (out_dir / f"{stem}.json").write_text(
                json.dumps(entry, indent=2, ensure_ascii=False))

    if not written:
        sys.exit(1)

    if len(written) > 1:
        strip = overview_strip(source_local, written, out_dir / f"{base}-overview.jpg", work_dir)
        if strip:
            print(f"\n  → {strip}  (Quelle plus alle Varianten)")
        (out_dir / f"{base}-batch.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False))

    print(f"\n  {len(written)} von {total} Aufruf(en) erfolgreich.")

    if args.json:
        print(json.dumps({"outputs": [str(p) for p in written], "runs": manifest},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
