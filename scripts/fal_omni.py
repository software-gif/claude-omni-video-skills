#!/usr/bin/env python3
"""
fal_omni.py — Gemini Omni über fal.ai.

Gleiche Schnittstelle wie google_omni.py, damit omni.py beide Wege gleich
behandeln kann.

WARUM ES DIESEN WEG GIBT
Google sperrt das Bearbeiten *hochgeladener* Videos für Nutzer in EWR, Schweiz
und UK. Über fal kommt die Anfrage nicht aus dem EWR, deshalb funktioniert
genau die Sache, um die es hier geht: einen Clip bearbeiten, den du schon hast.
Wer nur erzeugte Clips weiterbearbeitet, fährt mit google_omni.py günstiger.

Env: FAL_KEY (https://fal.ai/dashboard/keys) — in .env neben dem Repo.
"""

import json
import os
import pathlib
import shutil
import time
import urllib.request

ENDPOINT_EDIT = "google/gemini-omni-flash/edit"
ENDPOINT_CREATE = "google/gemini-omni-flash"
ENDPOINT_ANIMATE = "google/gemini-omni-flash/image-to-video"

MODEL = "gemini-omni-flash (via fal.ai)"

# Gemessen über eine ganze Session: 51,45 $ auf 29 Läufe mit 5- bis
# 8-Sekunden-Clips, also rund 0,25 $ pro Sekunde. Die 0,13 $/s auf der
# Modellseite sind nur der Ausgabe-Anteil.
#
# ACHTUNG: fals Kontostand-Endpoint hinkt der Abrechnung hinterher. Direkt nach
# einem Lauf abgelesen unterschätzt er deutlich — zwei so entstandene
# Schätzungen waren beide zu niedrig. Verlässlich ist nur Gesamtverbrauch
# geteilt durch Gesamtlaufzeit.
USD_PER_SECOND_EDIT = 0.25
USD_PER_SECOND_CREATE = 0.13

# Ein Lauf dauert normal 40 bis 90 Sekunden.
RUN_TIMEOUT = 600
POLL_EVERY = 5

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


class OmniError(RuntimeError):
    """Fehler mit einer Meldung, die für den Nutzer gedacht ist."""


class RegionBlocked(OmniError):
    """Kommt über fal praktisch nie vor — der Vollständigkeit halber."""


# Fehler, bei denen jeder weitere Aufruf im Batch genauso scheitern würde.
FATAL = ("exhausted balance", "user is locked", "invalid key", "unauthorized",
         "forbidden", "401", "403")


def is_fatal(message):
    low = message.lower()
    return any(marker in low for marker in FATAL)


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


def _client():
    if not load_key():
        raise OmniError(
            "FAL_KEY fehlt. In .env eintragen:\n"
            "  FAL_KEY=…    (https://fal.ai/dashboard/keys)"
        )
    try:
        import fal_client
    except ImportError:
        import sys
        raise OmniError(
            f"fal-client fehlt in diesem Python:\n  {sys.executable}\n\n"
            f"Installier es genau dort:\n  {sys.executable} -m pip install fal-client\n\n"
            "Ein blankes 'pip install fal-client' kann in einen anderen Python "
            "installieren — dann bleibt diese Meldung stehen, obwohl pip Erfolg meldet."
        ) from None
    return fal_client


def balance():
    """Kontostand in USD, oder None. Kostet nichts."""
    key = load_key()
    if not key:
        return None
    request = urllib.request.Request("https://rest.fal.ai/billing/user_balance",
                                     headers={"Authorization": f"Key {key}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return float(response.read().decode().strip())
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------


def upload_file(path, on_progress=None):
    """Datei zu fal hochladen; identische Dateien nur einmal.

    fal antwortet auf zu viele Upload-Tokens hintereinander mit 403, und ein
    Batch über fünf Märkte soll den Clip nicht fünfmal schicken.
    """
    client = _client()
    path = pathlib.Path(path).expanduser()
    if not path.exists():
        raise OmniError(f"Datei nicht gefunden: {path}")

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
        if on_progress:
            on_progress(f"{path.name} bereits hochgeladen, nutze den Cache.")
        return cache[fingerprint]

    if on_progress:
        on_progress(f"Upload {path.name} ({stat.st_size / 1_048_576:.1f} MB) …")
    try:
        url = client.upload_file(str(path))
    except Exception as exc:  # noqa: BLE001
        # fal schreibt den Grund in den Antwort-Body; str(exc) hat nur den Status.
        detail = getattr(getattr(exc, "response", None), "text", "") or ""
        raise OmniError(
            f"Upload fehlgeschlagen: {type(exc).__name__}: {exc}"
            + (f"\n  fal sagt: {detail.strip()[:300]}" if detail else "")
            + "\n  Häufigste Ursachen: aufgebrauchtes Guthaben "
            "(fal.ai/dashboard/billing), ungültiger FAL_KEY, oder zu viele "
            "parallele Läufe."
        ) from None

    cache[fingerprint] = url
    cache_file.write_text(json.dumps(cache, indent=2))
    return url


def interact(prompt, task, aspect="16:9", duration=8, video_uri=None,
             image_uri=None, previous_interaction_id=None, on_progress=None):
    """Einen Omni-Aufruf machen und ein interaktionsähnliches Dict zurückgeben.

    Bewusst NICHT handle.get(): das hängt an einem Event-Stream und ist in einem
    echten Lauf hängen geblieben, obwohl fal den Request längst als COMPLETED
    geführt hatte. status() und result() sind einfache HTTP-Aufrufe.
    """
    client = _client()
    if previous_interaction_id:
        raise OmniError("Verkettung gibt es nur beim Google-Weg. "
                        "Über fal wird der Clip stattdessen hochgeladen.")

    endpoint = {"text_to_video": ENDPOINT_CREATE,
                "image_to_video": ENDPOINT_ANIMATE}.get(task, ENDPOINT_EDIT)
    if endpoint == ENDPOINT_CREATE:
        arguments = {"prompt": prompt, "aspect_ratio": aspect, "duration": duration}
    elif endpoint == ENDPOINT_ANIMATE:
        arguments = {"prompt": prompt, "image_url": image_uri,
                     "aspect_ratio": aspect, "duration": duration}
    else:
        arguments = {"prompt": prompt, "video_url": video_uri}

    if on_progress:
        on_progress("Omni läuft …")
    started = time.time()
    handle = client.submit(endpoint, arguments=arguments)
    request_id = handle.request_id
    if on_progress:
        on_progress(f"request {request_id}")

    last_note = 0.0
    while True:
        elapsed = time.time() - started
        try:
            status = client.status(endpoint, request_id)
        except Exception:  # noqa: BLE001 — einzelner Statusabruf darf scheitern
            status = None
        if isinstance(status, client.Completed):
            break
        if elapsed > RUN_TIMEOUT:
            raise OmniError(
                f"Nach {RUN_TIMEOUT}s kein Ergebnis. Request {request_id} lässt sich "
                f"später noch abholen."
            )
        if on_progress and elapsed - last_note >= 30:
            last_note = elapsed
            on_progress(f"… {int(elapsed)}s ({type(status).__name__ if status else 'unbekannt'})")
        time.sleep(POLL_EVERY)

    result = client.result(endpoint, request_id)
    video = (result or {}).get("video") or {}
    if not video.get("url"):
        raise OmniError(f"Kein Video in der Antwort: {json.dumps(result)[:300]}")
    return {"id": request_id, "_video_url": video["url"],
            "_seconds": round(time.time() - started, 1),
            "_bytes": video.get("file_size"), "usage": None}


def extract_video(interaction):
    url = interaction["_video_url"]
    with urllib.request.urlopen(url, timeout=900) as response:
        return response.read()


def cost(interaction, seconds=None, editing=True):
    """Schätzung — fal liefert keine Tokenzahlen mit.

    Deshalb steht hier ein Näherungswert, während der Google-Weg den echten
    Preis nennt. Sekunden kommen von der Quelle, nicht von der Antwort.
    """
    rate = USD_PER_SECOND_EDIT if editing else USD_PER_SECOND_CREATE
    return (seconds or 8) * rate
