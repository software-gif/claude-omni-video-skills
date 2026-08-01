#!/usr/bin/env python3
"""
selftest.py — prüft die Einrichtung, ohne einen Cent auszugeben.

    python3 scripts/selftest.py

Kein einziger Modellaufruf. Geprüft wird, was erfahrungsgemäß schiefgeht,
bevor jemand zum ersten Mal Geld ausgibt: falscher Python, fehlendes ffmpeg,
Key nicht gefunden, leeres Guthaben, und ob die Prompt-Rezepte im Code noch mit
dem übereinstimmen, was die SKILL.md-Dateien behaupten.

Der Kontostand wird per GET abgefragt — das kostet nichts.
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


def load_omni():
    spec = importlib.util.spec_from_file_location("omni", OMNI)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_python(omni):
    version = ".".join(str(n) for n in sys.version_info[:3])
    if importlib.util.find_spec("fal_client"):
        report(OK, f"Python {version} mit fal-client")
    else:
        report(FAIL, f"Python {version} ohne fal-client",
               f"{sys.executable} -m pip install fal-client")


def check_ffmpeg():
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        report(OK, "ffmpeg vorhanden — Kontaktblätter werden geschrieben")
    else:
        report(WARN, "ffmpeg fehlt — keine Kontaktblätter",
               "brew install ffmpeg   (ohne sie kann Claude die Ergebnisse nicht ansehen)")


def check_key_and_balance(omni):
    key = omni.load_key()
    if not key:
        report(FAIL, "FAL_KEY nicht gefunden", "In .env eintragen: FAL_KEY=…")
        return
    report(OK, "FAL_KEY gefunden")
    request = urllib.request.Request(
        "https://rest.fal.ai/billing/user_balance",
        headers={"Authorization": f"Key {key}"},
    )
    try:
        balance = float(urllib.request.urlopen(request, timeout=30).read().decode().strip())
    except Exception as exc:  # noqa: BLE001
        report(WARN, "Guthaben nicht abrufbar", str(exc)[:120])
        return
    runs = int(balance / (omni.USD_PER_SECOND_EDIT * 5))
    if balance <= 0:
        report(FAIL, f"Guthaben {balance:.2f} USD — aufgebraucht",
               "Aufladen: https://fal.ai/dashboard/billing")
    elif runs < 4:
        report(WARN, f"Guthaben {balance:.2f} USD — reicht für ~{runs} Läufe à 5 s")
    else:
        report(OK, f"Guthaben {balance:.2f} USD — reicht für ~{runs} Läufe à 5 s")


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
    omni = load_omni()

    print("Umgebung")
    check_python(omni)
    check_ffmpeg()
    check_key_and_balance(omni)

    print("\nSkills")
    check_skills(omni)

    print("\nKommandos (Dry-Run)")
    check_commands()

    print()
    if problems:
        print(f"{len(problems)} Problem(e): " + ", ".join(problems))
        print("Oben steht bei jedem, was zu tun ist.")
        sys.exit(1)
    print("Alles in Ordnung. Ein Lauf auf einem 5-Sekunden-Clip kostet rund "
          f"{omni.USD_PER_SECOND_EDIT * 5:.2f} USD.")


if __name__ == "__main__":
    main()
