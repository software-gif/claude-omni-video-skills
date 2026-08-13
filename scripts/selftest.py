#!/usr/bin/env python3
"""
selftest.py — prüft die Einrichtung, ohne einen Cent auszugeben.

    python3 scripts/selftest.py

Kein einziger Modellaufruf. Geprüft wird, was erfahrungsgemäß schiefgeht,
bevor jemand zum ersten Mal Geld ausgibt: welcher Anbieter greift, ob sein Key
trägt, ffmpeg, Guthaben beziehungsweise Modellfreigabe, und ob die
Prompt-Rezepte im Code noch mit dem übereinstimmen, was die SKILL.md-Dateien
behaupten.

Geprüft wird per GET — das kostet nichts.
"""

import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OMNI = ROOT / "scripts" / "omni.py"

OK, WARN, FAIL = "  OK  ", " WARN ", " FEHLER "
problems = []


def report(status, label, detail=""):
    print(f"{status}{label}" + (f"\n        {detail}" if detail else ""))
    if status == FAIL:
        problems.append(label)


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_python():
    version = ".".join(str(n) for n in sys.version_info[:3])
    if sys.version_info < (3, 8):
        report(FAIL, f"Python {version} ist zu alt", "Mindestens 3.8 nötig.")
    else:
        report(OK, f"Python {version} — keine Zusatzpakete nötig")


def check_ffmpeg():
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        report(OK, "ffmpeg vorhanden — Kontaktblätter werden geschrieben")
    else:
        report(WARN, "ffmpeg fehlt — keine Kontaktblätter",
               "brew install ffmpeg   (ohne sie kann Claude die Ergebnisse nicht ansehen)")


def check_backend(omni, fal, google):
    """Welcher Anbieter greift, trägt sein Key, und was kann er?"""
    api = omni.pick_backend()
    if api is None:
        report(FAIL, "Kein Key gefunden",
               "FAL_KEY (fal.ai/dashboard/keys) oder GEMINI_API_KEY "
               "(aistudio.google.com/apikey) in .env eintragen.")
        return

    if api is fal:
        report(OK, "Anbieter: fal.ai — kann eigene Clips bearbeiten")
        try:
            import fal_client  # noqa: F401
        except ImportError:
            report(FAIL, "fal-client fehlt in diesem Python",
                   f"{sys.executable} -m pip install fal-client")
            return
        report(OK, "fal-client installiert")
        credit = fal.balance()
        if credit is None:
            report(WARN, "Guthaben nicht abrufbar — Key vermutlich ungültig")
        elif credit <= 0:
            report(FAIL, f"Guthaben {credit:.2f} USD — aufgebraucht",
                   "Aufladen: https://fal.ai/dashboard/billing")
        else:
            runs = int(credit / (fal.USD_PER_SECOND_EDIT * 5))
            level = OK if runs >= 4 else WARN
            report(level, f"Guthaben {credit:.2f} USD — reicht für ~{runs} Läufe à 5 s")
        return

    report(OK, "Anbieter: Google direkt — günstiger, aber im EWR nur für "
               "selbst erzeugte Clips")
    status, body, _ = google._request("/v1beta/models?pageSize=300", timeout=45)
    if status == 403:
        report(FAIL, "Key wird abgelehnt (403)",
               "Projekt ohne Zugriff. Neuen Key in AI Studio erzeugen.")
        return
    if status != 200:
        report(FAIL, f"Google antwortet mit {status}", body[:150].decode(errors="replace"))
        return
    names = [m.get("name", "") for m in json.loads(body).get("models", [])]
    if any("omni" in n for n in names):
        report(OK, f"Omni freigeschaltet ({google.MODEL})")
    else:
        report(FAIL, "Omni ist für diesen Key nicht sichtbar",
               f"{len(names)} Modelle sichtbar, keines davon Omni.")


def check_skills(omni):
    """Frontmatter gültig, und das zitierte Rezept == das Rezept im Code."""
    recipes = {
        "swap-background": omni.prompt_swap_background("<scene>"),
        "change-angle": omni.prompt_change_angle("<shot>"),
        "transform-object": omni.prompt_transform_object("<object>", "<target>"),
        "localize": omni.prompt_localize("<language>", "<keep>"),
    }

    def norm(text):
        text = text.replace("&lt;", "<").replace("&gt;", ">")
        return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", text)).strip()

    for name, recipe in recipes.items():
        path = ROOT / ".claude" / "skills" / name / "SKILL.md"
        if not path.exists():
            report(FAIL, f"Skill {name} fehlt")
            continue
        text = path.read_text()

        head = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        declared = re.search(r"^name:\s*(.+)$", head.group(1), re.M) if head else None
        if not declared or declared.group(1).strip() != name:
            report(FAIL, f"Skill {name}: Frontmatter-Name passt nicht zum Ordner")
            continue

        quotes, current = [], []
        for line in text.splitlines():
            if line.startswith(">"):
                current.append(line.lstrip("> ").rstrip())
            elif current:
                quotes.append(" ".join(current))
                current = []
        if current:
            quotes.append(" ".join(current))

        quoted = [q for q in quotes if "Keep everything else" in q]
        if not quoted:
            report(FAIL, f"Skill {name}: kein Rezept in der Doku zitiert")
        elif norm(quoted[0]) != norm(recipe):
            report(FAIL, f"Skill {name}: Doku zitiert ein anderes Rezept als der Code",
                   "Die Doku ist damit irreführend — eines von beidem angleichen.")
        else:
            report(OK, f"Skill {name}: Rezept stimmt mit der Doku überein")


def check_commands():
    """Jedes Unterkommando einmal als Dry-Run — kostet nichts."""
    sample = ROOT / "examples" / "source.mp4"
    image = ROOT / "examples" / "overview.jpg"
    calls = [
        ("swap-background", ["--input", str(sample), "--to", "a test scene"]),
        ("change-angle", ["--input", str(sample), "--angle", "wide"]),
        ("transform-object", ["--input", str(sample), "--object", "the bottle", "--to", "chrome"]),
        ("localize", ["--input", str(sample), "--lang", "German"]),
        ("create", ["--prompt", "a test clip"]),
        ("animate", ["--image", str(image), "--prompt", "slow push-in"]),
        ("raw", ["--input", str(sample), "--prompt", "make it night"]),
    ]
    if not sample.exists():
        report(WARN, "examples/source.mp4 fehlt — Kommandos nicht prüfbar")
        return
    for name, args in calls:
        result = subprocess.run([sys.executable, str(OMNI), name, *args, "--dry-run"],
                                capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            report(OK, f"Kommando {name}")
        else:
            report(FAIL, f"Kommando {name}",
                   (result.stderr or result.stdout).strip().splitlines()[-1][:160])


def main():
    print("\nEinrichtung prüfen — es wird nichts generiert und nichts abgerechnet.\n")
    omni = load_module("omni")

    fal = load_module("fal_omni")
    google = load_module("google_omni")

    print("Umgebung")
    check_python()
    check_ffmpeg()
    check_backend(omni, fal, google)

    print("\nSkills")
    check_skills(omni)

    print("\nKommandos (Dry-Run)")
    check_commands()

    print()
    if problems:
        print(f"{len(problems)} Problem(e): " + ", ".join(problems))
        print("Oben steht bei jedem, was zu tun ist.")
        sys.exit(1)
    api = omni.pick_backend()
    per_run = (fal.cost(None, 5, True) if api is fal else omni.estimate(5, True))
    print(f"Alles in Ordnung. Ein Lauf auf einem 5-Sekunden-Clip kostet rund "
          f"{per_run:.2f} USD über {omni.backend_name(api)}.")


if __name__ == "__main__":
    main()
