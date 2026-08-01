#!/usr/bin/env python3
"""
google_omni.py — dünne Schicht auf Gemini Omni, direkt bei Google.

Kein fal, kein SDK, nur die Gemini-API über HTTP. Wird von omni.py benutzt und
ist bewusst einzeln testbar.

Env: GEMINI_API_KEY (https://aistudio.google.com/apikey) — in .env neben dem Repo.
"""

import base64
import json
import mimetypes
import os
import pathlib
import time
import urllib.error
import urllib.request

BASE = "https://generativelanguage.googleapis.com"
MODEL = "gemini-omni-flash-preview"

# Google rechnet nach Tokens ab. Diese Sätze stehen auf der Modellseite; die
# Antwort liefert die tatsächlichen Tokenzahlen mit, deshalb kann jeder Lauf
# seinen echten Preis ausweisen statt einer Schätzung.
USD_PER_INPUT_TOKEN = 1.875 / 1_000_000
USD_PER_OUTPUT_TOKEN = 21.875 / 1_000_000

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


class OmniError(RuntimeError):
    """Fehler mit einer Meldung, die für den Nutzer gedacht ist."""


class RegionBlocked(OmniError):
    """Google verweigert das Bearbeiten hochgeladener Videos in EWR/CH/UK.

    Wird als „The prompt contains sensitive words" gemeldet, was in die Irre
    führt: Es liegt nicht am Prompt. Nachgewiesen, indem derselbe Prompt ohne
    hochgeladenes Video durchläuft und mit ihm nicht.
    """


def load_key():
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    for candidate in (REPO_ROOT / ".env", pathlib.Path.cwd() / ".env"):
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line.startswith("GEMINI_API_KEY=") and not line.startswith("#"):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if value:
                        os.environ["GEMINI_API_KEY"] = value
                        return value
    return None


def _request(path, data=None, headers=None, method=None, timeout=900):
    key = load_key()
    if not key:
        raise OmniError(
            "GEMINI_API_KEY fehlt. In .env eintragen:\n"
            "  GEMINI_API_KEY=…    (https://aistudio.google.com/apikey)"
        )
    url = path if path.startswith("http") else BASE + path
    request = urllib.request.Request(
        url, data=data, headers={"x-goog-api-key": key, **(headers or {})}, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read()
        except Exception:  # noqa: BLE001
            body = b""
        return exc.code, body, {}


# --------------------------------------------------------------------------
# Files API — nötig, um ein eigenes Video zum Bearbeiten hochzuladen
# --------------------------------------------------------------------------


def upload_file(path, on_progress=None):
    """Datei hochladen und warten, bis Google sie verarbeitet hat."""
    path = pathlib.Path(path).expanduser()
    if not path.exists():
        raise OmniError(f"Datei nicht gefunden: {path}")
    blob = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    if on_progress:
        on_progress(f"Upload {path.name} ({len(blob) / 1_048_576:.1f} MB) …")

    status, body, headers = _request(
        "/upload/v1beta/files",
        data=json.dumps({"file": {"display_name": path.name}}).encode(),
        headers={
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(len(blob)),
            "X-Goog-Upload-Header-Content-Type": mime,
            "Content-Type": "application/json",
        },
        timeout=120,
    )
    if status != 200:
        raise OmniError(f"Upload konnte nicht gestartet werden ({status}): "
                        f"{body[:300].decode(errors='replace')}")
    target = headers.get("X-Goog-Upload-URL") or headers.get("x-goog-upload-url")
    if not target:
        raise OmniError("Google hat keine Upload-URL zurückgegeben.")

    status, body, _ = _request(
        target,
        data=blob,
        headers={
            "Content-Length": str(len(blob)),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        },
        timeout=1800,
    )
    if status != 200:
        raise OmniError(f"Upload fehlgeschlagen ({status}): "
                        f"{body[:300].decode(errors='replace')}")

    info = json.loads(body)
    info = info.get("file", info)
    name, uri = info.get("name"), info.get("uri")

    for _ in range(60):
        if info.get("state") != "PROCESSING":
            break
        time.sleep(5)
        status, body, _ = _request(f"/v1beta/{name}", timeout=60)
        info = json.loads(body) if status == 200 else info
    if info.get("state") == "FAILED":
        raise OmniError("Google konnte die Datei nicht verarbeiten.")
    return uri


# --------------------------------------------------------------------------
# Generierung
# --------------------------------------------------------------------------

# Wortlaut, mit dem Google die Regionssperre meldet. Die Meldung nennt den
# Prompt, gemeint ist aber das hochgeladene Video.
_BLOCK_MARKERS = ("sensitive words", "prohibited use policy")


def interact(prompt, task, aspect="16:9", video_uri=None, image_path=None,
             previous_interaction_id=None, on_progress=None):
    """Einen Omni-Aufruf machen und die fertige Interaktion zurückgeben."""
    payload = {"model": MODEL, "input": [], "response_format": {"type": "video"}}
    if aspect:
        payload["response_format"]["aspect_ratio"] = aspect
    if task:
        payload["generation_config"] = {"video_config": {"task": task}}
    if previous_interaction_id:
        payload["previous_interaction_id"] = previous_interaction_id

    if video_uri:
        payload["input"].append({"type": "document", "uri": video_uri})
    if image_path:
        data = pathlib.Path(image_path).expanduser().read_bytes()
        mime = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
        payload["input"].append({"type": "image", "mime_type": mime,
                                 "data": base64.b64encode(data).decode()})
    payload["input"].append({"type": "text", "text": prompt})

    if on_progress:
        on_progress("Omni läuft …")
    started = time.time()
    status, body, _ = _request("/v1beta/interactions",
                               data=json.dumps(payload).encode(),
                               headers={"Content-Type": "application/json"})
    text = body.decode(errors="replace")

    if status != 200:
        low = text.lower()
        if any(marker in low for marker in _BLOCK_MARKERS) and video_uri:
            raise RegionBlocked(
                "Google lehnt das Bearbeiten hochgeladener Videos ab.\n"
                "  Die Meldung nennt \u201esensitive words\u201c, gemeint ist aber die\n"
                "  Regionssperre für EWR, Schweiz und UK — derselbe Prompt ohne\n"
                "  hochgeladenes Video läuft durch.\n\n"
                "  Was hier funktioniert: einen Clip mit `create` oder `animate`\n"
                "  erzeugen und ihn dann mit --from-interaction weiterbearbeiten.\n"
                "  Eigenes Drehmaterial lässt sich aus dem EWR heraus nicht\n"
                "  direkt bei Google bearbeiten."
            )
        try:
            detail = json.loads(text)["error"]["message"]
        except Exception:  # noqa: BLE001
            detail = text[:400]
        raise OmniError(f"Google meldet {status}: {detail}")

    result = json.loads(text)
    result["_seconds"] = round(time.time() - started, 1)
    return result


def extract_video(interaction):
    """Video-Bytes aus einer fertigen Interaktion holen."""
    for step in interaction.get("steps", []):
        for item in step.get("content", []) or []:
            if item.get("type") != "video":
                continue
            if item.get("data"):
                return base64.b64decode(item["data"])
            uri = item.get("uri") or item.get("url")
            if uri:
                status, body, _ = _request(uri, timeout=900)
                if status == 200:
                    return body
    raise OmniError("Kein Video in der Antwort gefunden.")


def cost(interaction):
    """Exakter Preis dieses Laufs aus den mitgelieferten Tokenzahlen."""
    usage = interaction.get("usage") or {}
    return (usage.get("total_input_tokens", 0) * USD_PER_INPUT_TOKEN
            + usage.get("total_output_tokens", 0) * USD_PER_OUTPUT_TOKEN)
