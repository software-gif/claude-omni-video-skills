#!/usr/bin/env python3
"""
omni.py — ein Video rein, ein verändertes Video raus.

Ruft Gemini Omni Flash über fal.ai auf. Jede Skill in .claude/skills/ ist ein
Wrapper um genau ein Unterkommando hier.

    python3 scripts/omni.py swap-background  --input clip.mp4 --to "a rainy Tokyo street at night"
    python3 scripts/omni.py change-angle     --input clip.mp4 --angle close-up
    python3 scripts/omni.py transform-object --input clip.mp4 --object "the bottle" --to "brushed chrome"
    python3 scripts/omni.py localize         --input clip.mp4 --lang German --keep "the brand name"
    python3 scripts/omni.py raw              --input clip.mp4 --prompt "..."
    python3 scripts/omni.py create           --prompt "..." --aspect 9:16 --duration 8

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
# Nichts hier ergänzen, ohne es zu testen: Jeder zusätzliche Satz ist eine
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


def prompt_swap_background(args):
    return (
        f"Change only the background to {args.to}. "
        f"Do not change the people or products in the shot: same faces, same clothing, "
        f"same colours, same position in the frame, same movement. {KEEP}"
    )


def prompt_change_angle(args):
    shot = args.to or ANGLES[args.angle]
    return (
        f"Re-frame this shot as {shot}. "
        f"Keep the same scene, the same subject, the same moment and the same lighting. {KEEP}"
    )


def prompt_transform_object(args):
    return (
        f"Change {args.object} to {args.to}. "
        f"Keep its shape, size and position identical, and keep the way it moves in the shot. {KEEP}"
    )


def prompt_localize(args):
    keep = f" Leave {args.keep} in the original language." if args.keep else ""
    return (
        f"Translate all on-screen text, captions, labels and signage into {args.lang}. "
        f"Keep the same fonts, colours, sizes and positions.{keep} {KEEP}"
    )


def prompt_raw(args):
    return args.prompt


RECIPES = {
    "swap-background": prompt_swap_background,
    "change-angle": prompt_change_angle,
    "transform-object": prompt_transform_object,
    "localize": prompt_localize,
    "raw": prompt_raw,
    "create": prompt_raw,
}


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
    # Änderungszeit spart Zeit, Bandbreite und genau diesen Fehler.
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
        sys.exit(
            f"Upload fehlgeschlagen: {type(exc).__name__}: {exc}\n"
            "  Häufigste Ursachen: FAL_KEY ohne Storage-Rechte, aufgebrauchtes Guthaben, "
            "oder zu viele parallele Läufe. Alternativ --input mit einer öffentlichen URL aufrufen."
        )

    cache[fingerprint] = url
    cache_file.write_text(json.dumps(cache, indent=2))
    return url, path


def download(url, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, open(target, "wb") as handle:
        shutil.copyfileobj(response, handle)
    return target


# --- Kontaktblatt ---------------------------------------------------------
#
# Claude kann kein Video abspielen, aber ein JPG lesen. Nach jedem Lauf legt
# das Skript deshalb ein Vergleichsbild an: obere Reihe Quelle, untere Reihe
# Ergebnis, jeweils drei Zeitpunkte. Das ist die Grundlage für Schritt 3 in
# jeder Skill. Braucht ffmpeg; fehlt es, wird das Blatt still übersprungen.


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
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{seconds:.2f}", "-i", str(path),
         "-frames:v", "1", "-vf", f"scale=-2:{height}", str(target)],
        check=True, timeout=60,
    )


def contact_sheet(source, result, target, work_dir):
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        return None
    length = _duration(result)
    if not length:
        return None
    stamps = [length * 0.05, length * 0.5, length * 0.93]
    rows, inputs = [], []
    try:
        for label, clip in (("s", source), ("o", result)):
            if clip is None or not pathlib.Path(clip).exists():
                continue
            frames = []
            for index, second in enumerate(stamps):
                frame = work_dir / f"sheet-{label}{index}.jpg"
                _grab(clip, min(second, (_duration(clip) or length) - 0.05), frame)
                frames.append(frame)
            rows.append(frames)
        if not rows:
            return None
        for row in rows:
            inputs.extend(row)
        args = ["ffmpeg", "-v", "error", "-y"]
        for frame in inputs:
            args += ["-i", str(frame)]
        parts, labels = [], []
        for row_index in range(len(rows)):
            base = row_index * 3
            parts.append(f"[{base}][{base + 1}][{base + 2}]hstack=3[r{row_index}]")
            labels.append(f"[r{row_index}]")
        chain = ";".join(parts)
        if len(rows) > 1:
            chain += ";" + "".join(labels) + f"vstack={len(rows)}"
        else:
            chain = chain.replace("[r0]", "")
        args += ["-filter_complex", chain, "-q:v", "3", str(target)]
        subprocess.run(args, check=True, timeout=120)
        return target
    except Exception:  # noqa: BLE001 — das Kontaktblatt ist Komfort, kein Muss
        return None


def run_once(fal_client, endpoint, arguments, index, total):
    label = f"[{index}/{total}] " if total > 1 else ""
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
        sp.add_argument("--name", help="Basisname der Ausgabedatei")
        sp.add_argument("--runs", type=int, default=1, help="Anzahl Generierungen (Default 1)")
        sp.add_argument("--dry-run", action="store_true", help="Nur den Prompt zeigen")
        sp.add_argument("--json", action="store_true", help="Ergebnis als JSON auf stdout")
        return sp

    sp = common(sub.add_parser("swap-background", help="Hintergrund tauschen"))
    sp.add_argument("--to", required=True, help='Neue Szene, z. B. "a rainy Tokyo street at night"')

    sp = common(sub.add_parser("change-angle", help="Kameraperspektive ändern"))
    sp.add_argument("--angle", choices=sorted(ANGLES), help="Vordefinierte Perspektive")
    sp.add_argument("--to", help="Freitext-Perspektive statt --angle")

    sp = common(sub.add_parser("transform-object", help="Material, Farbe oder Finish ändern"))
    sp.add_argument("--object", required=True, help='Was, z. B. "the sneaker"')
    sp.add_argument("--to", required=True, help='Wohin, z. B. "brushed chrome"')

    sp = common(sub.add_parser("localize", help="On-Screen-Text übersetzen"))
    sp.add_argument("--lang", required=True, help='Zielsprache, z. B. "German"')
    sp.add_argument("--keep", help='Was unübersetzt bleibt, z. B. "the brand name"')

    sp = common(sub.add_parser("raw", help="Eigene Anweisung, ohne Rezept"))
    sp.add_argument("--prompt", required=True)

    sp = common(sub.add_parser("create", help="Testclip aus Text erzeugen (kein Input nötig)"), needs_input=False)
    sp.add_argument("--prompt", required=True)
    sp.add_argument("--aspect", default="16:9", choices=["16:9", "9:16"])
    sp.add_argument("--duration", type=int, default=8, help="3 bis 10 Sekunden (Default 8)")

    return parser


def main():
    args = build_parser().parse_args()

    if args.command == "change-angle" and not (args.angle or args.to):
        sys.exit("change-angle braucht --angle oder --to")
    if args.command == "create" and not 3 <= args.duration <= 10:
        sys.exit("--duration muss zwischen 3 und 10 Sekunden liegen")

    prompt = RECIPES[args.command](args)

    print(f"\n  {args.command}")
    print(f"  Prompt: {prompt}\n")

    if args.dry_run:
        seconds = args.duration if args.command == "create" else 8
        print(f"  Dry run. {args.runs} Generierung(en), grob "
              f"${USD_PER_SECOND * seconds * args.runs:.2f} bei {seconds} s Video.")
        return

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
        endpoint = ENDPOINT_CREATE
        arguments = {"prompt": prompt, "aspect_ratio": args.aspect, "duration": args.duration}
        source_local = None
        source_url = None
        stem = args.name or f"clip-{slugify(prompt, 32)}"
    else:
        endpoint = ENDPOINT_EDIT
        source_url, source_local = resolve_source(fal_client, args.input, work_dir)
        arguments = {"prompt": prompt, "video_url": source_url}
        stem = args.name or f"{args.command}-{slugify(getattr(args, 'to', None) or getattr(args, 'lang', '') or 'run')}"

    written = []
    for index in range(1, args.runs + 1):
        suffix = "" if args.runs == 1 else f"-{index}"
        try:
            video, took, request_id = run_once(fal_client, endpoint, arguments, index, args.runs)
        except Exception as exc:  # noqa: BLE001 — die Meldung ist für den Nutzer, nicht fürs Log
            message = str(exc)
            print(f"  Fehlgeschlagen: {type(exc).__name__}: {message}")
            if "not available" in message.lower() or "region" in message.lower():
                print("  Hinweis: Google sperrt den Video-Edit teilweise in EU/UK/CH. "
                      "Siehe README, Abschnitt Grenzen.")
            continue

        target = download(video["url"], out_dir / f"{stem}{suffix}.mp4")
        written.append(str(target))
        print(f"  → {target}  ({video.get('file_size', 0) / 1_048_576:.1f} MB, {took:.0f}s)")

        sheet = contact_sheet(source_local, target, out_dir / f"{stem}{suffix}-compare.jpg", work_dir)
        if sheet:
            print(f"  → {sheet}  (oben Quelle, unten Ergebnis)")

        (out_dir / f"{stem}{suffix}.json").write_text(
            json.dumps(
                {
                    "command": args.command,
                    "prompt": prompt,
                    "endpoint": endpoint,
                    "request_id": request_id,
                    "source": str(source_local) if source_local else source_url,
                    "source_url": source_url,
                    "output": str(target),
                    "compare": str(sheet) if sheet else None,
                    "seconds": round(took, 1),
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    if not written:
        sys.exit(1)

    if args.json:
        print(json.dumps({"prompt": prompt, "outputs": written}, ensure_ascii=False))


if __name__ == "__main__":
    main()
