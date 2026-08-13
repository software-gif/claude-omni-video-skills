# Setup — Claude an Gemini Omni anschließen

Rund fünf Minuten. Danach rufst du die Skills als Slash-Befehle in Claude Code
auf und musst nie wieder daran denken, wie der API-Call aussieht.

## 1 · Claude Code

Falls noch nicht vorhanden: [claude.com/claude-code](https://claude.com/claude-code).
Die Skills funktionieren in jeder Variante — Terminal, Desktop-App oder
IDE-Erweiterung.

## 2 · Repo holen

```bash
git clone https://github.com/software-gif/claude-omni-video-skills.git
cd claude-omni-video-skills
```

**Für den Google-Weg keine Pakete nötig** — die Skripte laufen mit der
Python-Standardbibliothek. Nur der fal-Weg braucht ein Paket:

```bash
python3 -m pip install fal-client
```

`python3 -m pip` statt nur `pip` ist hier kein Pedanterie: Auf vielen Macs
liegen zwei Pythons, und ein blankes `pip install` landet womöglich im falschen.
Dann meldet pip Erfolg und das Skript trotzdem, das Paket fehle.

Optional, aber sehr empfohlen:

```bash
brew install ffmpeg
```

Ohne ffmpeg läuft alles, aber es entstehen keine Kontaktblätter — und dann kann
Claude das Ergebnis nicht ansehen, sondern nur melden, dass eine Datei da ist.
Das ist der halbe Nutzen.

## 3 · Einen Key eintragen

Du brauchst **einen** von beiden. Welchen, hängt daran, ob du eigenes
Drehmaterial bearbeiten willst:

| | fal.ai | Google direkt |
|---|---|---|
| Eigenen Clip bearbeiten | **ja** | nein (EWR/CH/UK gesperrt) |
| Preis | ~0,25 $/s | ~0,14 $/s |
| Key von | [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| Zusätzlich nötig | `python3 -m pip install fal-client` | nichts |

```bash
cp .env.example .env
```

Dann `.env` öffnen und **eine** Zeile ausfüllen:

```
FAL_KEY=dein-key-hier
# oder
GEMINI_API_KEY=dein-key-hier
```

Sind beide da, gewinnt fal — weil nur dieser Weg eigenes Material bearbeiten
kann. `--backend google` erzwingt trotzdem den günstigeren Weg.

Die `.env` ist über `.gitignore` ausgeschlossen und landet nicht im Repo.

## 4 · Markenkontext ausfüllen

Öffne [`brand/brand.md`](brand/brand.md) und ersetz das Beispiel durch deine
Marke: Produkte, wie sie im Prompt heißen, Colourways, passende Szenen, Märkte
und Sprachen, Talent, Tabus.

Das ist der Schritt, der aus einem Video-Werkzeug ein Marken-Werkzeug macht.
Danach sagst du „mach mir die Wintervariante" statt jedes Mal Szene, Material
und Sprache auszuformulieren — Claude liest die Datei und schreibt den Aufruf.

Überspringbar, aber dann beantwortest du dieselben Fragen bei jedem Lauf.

## 5 · Einrichtung prüfen

Bevor du zum ersten Mal Geld ausgibst:

```bash
python3 scripts/selftest.py
```

Das kostet nichts — kein einziger Modellaufruf. Geprüft werden Python, ffmpeg,
ob der Key gefunden wird und trägt, ob Omni für dein Projekt freigeschaltet ist,
sowie alle sieben Kommandos im Trockenlauf. Jede Fehlermeldung sagt dazu, was zu
tun ist.

## 6 · Erster Lauf

**Mit fal-Key:** nimm einfach deinen Clip.

```bash
python3 scripts/omni.py swap-background \
  --input mein-clip.mp4 \
  --to "a warm home kitchen with oak worktops and low morning light" \
  --out ./out
```

**Mit Google-Key** brauchst du zuerst einen Ausgangsclip vom Modell selbst —
hochgeladene Videos sind aus EWR, Schweiz und UK gesperrt. Aus einem
Produktfoto:

```bash
python3 scripts/omni.py animate \
  --image produkte/pfanne.png \
  --prompt "slow push-in on the pan, soft studio light, the product stays still" \
  --aspect 9:16 --duration 5 --out ./out
```

Oder ganz ohne Material mit `create`. Danach laufen die vier Skills auf dem
Ergebnis; die Verkettung passiert von selbst, `--input` findet die
Interaktions-ID im Manifest neben dem Video.

In beiden Fällen dann Claude Code im Ordner starten:

```
/swap-background
```

Vorher prüfen, ohne etwas auszugeben, geht immer mit `--dry-run`.

---

## Wenn etwas klemmt

### `Kein Key gefunden`

Die `.env` liegt nicht neben dem Repo, oder die Zeile heißt anders. Das Skript
sucht `FAL_KEY=` und `GEMINI_API_KEY=` in `.env` im Repo-Wurzelverzeichnis und
im aktuellen Ordner, danach in den Umgebungsvariablen.

### `fal-client fehlt in diesem Python`

Nur beim fal-Weg. Zwei Pythons auf dem Rechner, und pip hat in den falschen
installiert. Die Meldung nennt den Pfad des Interpreters, der gerade läuft,
samt passendem Befehl — den einfach kopieren.

### `403 Forbidden` beim Upload (fal)

Fast immer aufgebrauchtes Guthaben. Das Skript zeigt den Klartext von fal mit
an, meist `User is locked. Reason: Exhausted balance.` Aufladen unter
[fal.ai/dashboard/billing](https://fal.ai/dashboard/billing).

### `Key wird abgelehnt (403)`

Das Google-Projekt hinter dem Key hat keinen Zugriff. Neuen Key in AI Studio
erzeugen. `python3 scripts/selftest.py` sagt dir sofort, ob der Key trägt und ob
Omni für dich freigeschaltet ist.

### Etwas mit *sensitive words*

Das ist **nicht** dein Prompt, auch wenn die Meldung das behauptet. Es ist die
Regionssperre: Aus EWR, Schweiz und UK lässt Google keine **hochgeladenen**
Videos bearbeiten. Gegengetestet mit dem harmlosesten denkbaren Satz — ebenfalls
blockiert, während derselbe Prompt ohne hochgeladenes Video durchläuft.

Lösung: Ausgangsclip mit `create` oder `animate` erzeugen, die vier Skills
darauf verketten. Das Skript sagt dir beim Start, welcher der beiden Wege
gerade greift.

### `previous_interaction_id is not allowed when video task is set`

Sollte nicht mehr auftreten — falls doch, ist das Skript älter als der Fix.
Google verträgt Verkettung und explizite Aufgabenangabe nicht gleichzeitig.

### Es entstehen keine `-compare.jpg`

ffmpeg fehlt. `brew install ffmpeg` (macOS) beziehungsweise
`apt install ffmpeg` (Linux). Das Skript sagt beim Start Bescheid, wenn es
ffmpeg nicht findet.
