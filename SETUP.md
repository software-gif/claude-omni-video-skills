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

**Keine Pakete zu installieren.** Die Skripte laufen mit der
Python-Standardbibliothek. Damit entfällt auch die häufigste Stolperfalle
überhaupt: dass `pip` und `python3` auf verschiedene Interpreter zeigen und
Installationen ins Leere laufen.

Optional, aber sehr empfohlen:

```bash
brew install ffmpeg
```

Ohne ffmpeg läuft alles, aber es entstehen keine Kontaktblätter — und dann kann
Claude das Ergebnis nicht ansehen, sondern nur melden, dass eine Datei da ist.
Das ist der halbe Nutzen.

## 3 · Google-Key eintragen

Der Key kommt von [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
Dort entstehen auch die Kosten: rund **0,13 $ pro Sekunde** erzeugtem Video, ein
3-Sekunden-Clip also etwa 0,40 $.

```bash
cp .env.example .env
```

Dann `.env` öffnen und eintragen:

```
GEMINI_API_KEY=dein-key-hier
```

Die `.env` ist über `.gitignore` ausgeschlossen und landet nicht im Repo.
Alternativ geht auch `export GEMINI_API_KEY=…` in der Shell.

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

**Zuerst brauchst du einen Ausgangsclip vom Modell selbst.** Warum, steht im
README: Google lässt aus EWR, Schweiz und UK keine hochgeladenen Videos
bearbeiten, wohl aber solche, die das Modell erzeugt hat.

Aus einem Produktfoto:

```bash
python3 scripts/omni.py animate \
  --image produkte/tiegel.jpg \
  --prompt "slow push-in on the jar, soft studio light, the product stays still" \
  --aspect 9:16 --duration 5 --out ./out
```

Oder ganz ohne Material:

```bash
python3 scripts/omni.py create \
  --prompt "A matte black insulated bottle on a pale wooden table, soft studio light." \
  --duration 5 --out ./out
```

Danach Claude Code im Ordner starten und eine der vier Skills auf das Ergebnis
loslassen:

```
/swap-background
```

Die Verkettung passiert von selbst — `--input` findet die Interaktions-ID im
Manifest neben dem Video.

Vorher prüfen, ohne etwas auszugeben, geht immer mit `--dry-run`.

---

## Wenn etwas klemmt

### `GEMINI_API_KEY fehlt`

Die `.env` liegt nicht neben dem Repo, oder die Zeile heißt anders. Das Skript
sucht `GEMINI_API_KEY=` in `.env` im Repo-Wurzelverzeichnis und im aktuellen
Ordner, danach in den Umgebungsvariablen.

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
