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
pip install fal-client
```

Optional, aber sehr empfohlen:

```bash
brew install ffmpeg
```

Ohne ffmpeg läuft alles, aber es entstehen keine Kontaktblätter — und dann kann
Claude das Ergebnis nicht ansehen, sondern nur melden, dass eine Datei da ist.
Das ist der halbe Nutzen.

## 3 · fal-Key eintragen

Der Key kommt von [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys).
fal ist der Anbieter, über den Gemini Omni läuft; hier entstehen auch die
Kosten. Lade dort etwas Guthaben auf, ein Lauf kostet rund 1 $.

```bash
cp .env.example .env
```

Dann `.env` öffnen und eintragen:

```
FAL_KEY=dein-key-hier
```

Die `.env` ist über `.gitignore` ausgeschlossen und landet nicht im Repo.
Alternativ geht auch `export FAL_KEY=…` in der Shell.

## 4 · Markenkontext ausfüllen

Öffne [`brand/brand.md`](brand/brand.md) und ersetz das Beispiel durch deine
Marke: Produkte, wie sie im Prompt heißen, Colourways, passende Szenen, Märkte
und Sprachen, Talent, Tabus.

Das ist der Schritt, der aus einem Video-Werkzeug ein Marken-Werkzeug macht.
Danach sagst du „mach mir die Wintervariante" statt jedes Mal Szene, Material
und Sprache auszuformulieren — Claude liest die Datei und schreibt den Aufruf.

Überspringbar, aber dann beantwortest du dieselben Fragen bei jedem Lauf.

## 5 · Erster Lauf

Claude Code im Repo-Ordner starten und einen der Befehle aufrufen:

```
/swap-background
```

Kein eigenes Material zur Hand? Dann erzeug dir eins — das kostet einen Lauf
und dauert rund 40 Sekunden:

```bash
python3 scripts/omni.py create \
  --prompt "A young woman in a grey hoodie holds a matte black water bottle on a sunlit city sidewalk, slow push-in, the words STAY SHARP burned into the lower third." \
  --aspect 16:9 --duration 8 --out ./out --name testclip
```

Vorher prüfen, ohne etwas auszugeben, geht immer mit `--dry-run`:

```bash
python3 scripts/omni.py swap-background --input ./out/testclip.mp4 \
  --to "a snowy alpine village at dusk" --dry-run
```

---

## Wenn etwas klemmt

Die vier Fehler, die in der Praxis auftreten, und was sie bedeuten.

### `FAL_KEY fehlt`

Die `.env` liegt nicht neben dem Repo, oder die Zeile heißt anders. Das Skript
sucht `FAL_KEY=` in `.env` im Repo-Wurzelverzeichnis und im aktuellen Ordner,
und danach in den Umgebungsvariablen.

### `invalid key credentials` (401)

Der Key ist falsch, abgelaufen oder gelöscht. Neu erzeugen auf
[fal.ai/dashboard/keys](https://fal.ai/dashboard/keys). Achte darauf, den
kompletten Key zu kopieren — er enthält einen Doppelpunkt und besteht aus zwei
Teilen.

### `403 Forbidden` beim Upload

Fast immer aufgebrauchtes Guthaben. Das Skript zeigt dir seit Kurzem den
Klartext von fal mit an, meist:

```
User is locked. Reason: Exhausted balance.
```

Aufladen unter [fal.ai/dashboard/billing](https://fal.ai/dashboard/billing).
Seltener: zu viele parallele Läufe. Umgehen lässt sich der Upload komplett,
indem du `--input` mit einer öffentlichen URL statt einer lokalen Datei
aufrufst.

### Etwas mit „not available in your region"

Google sperrt das Bearbeiten **hochgeladener** Videos für Nutzer in EWR,
Schweiz und UK; **modell-generierte** Videos zu bearbeiten ist dort erlaubt.
Über fal läuft die Anfrage gar nicht erst aus dem EWR heraus, deshalb liefen
unsere Tests aus Deutschland durch — mit hochgeladener Datei genauso wie mit
öffentlicher URL. Solltest du die Sperre trotzdem sehen, ist das kein Fehler im
Skript. Rufst du Omni direkt über die Google-Gemini-API auf statt über fal,
kann sie dagegen greifen.

### Es entstehen keine `-compare.jpg`

ffmpeg fehlt. `brew install ffmpeg` (macOS) beziehungsweise
`apt install ffmpeg` (Linux). Das Skript sagt beim Start Bescheid, wenn es
ffmpeg nicht findet.
