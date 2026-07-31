# Omni Video Skills — ein Clip, viele Varianten

Vier Claude-Code-Skills, die ein **vorhandenes Video verändern**, statt neu zu
drehen. Hintergrund tauschen, Perspektive wechseln, Material umfärben,
On-Screen-Text übersetzen — jeweils ein Befehl, ein Modellaufruf.

```
/swap-background    gleiche Aufnahme, neue Szene
/change-angle       neue Perspektive aus demselben Take
/transform-object   neues Material, gleiches Produkt
/localize           On-Screen-Text in einer anderen Sprache
```

Läuft auf **Gemini Omni Flash** (Video-zu-Video) über fal.ai.

![Quelle oben, die vier Skills darunter](examples/overview.jpg)

## Installation (2 Minuten)

```bash
git clone https://github.com/software-gif/claude-omni-video-skills.git
cd claude-omni-video-skills
pip install fal-client
cp .env.example .env    # und den fal-Key eintragen
```

Du brauchst einen Key von [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys).
Optional, aber empfohlen: `brew install ffmpeg` — dann legt jeder Lauf
zusätzlich ein Vorher-Nachher-Kontaktblatt an (siehe unten).

Dann Claude Code im Ordner starten und loslegen:

```
/swap-background
```

Willst du die Skills in einem anderen Projekt nutzen, kopiere `.claude/skills/`
und `scripts/omni.py` dorthin.

## Die vier Skills

| Skill | Wofür | Die eine Variable |
|---|---|---|
| `/swap-background` | Ein Dreh, mehrere Märkte, Jahreszeiten oder Settings | die neue Szene |
| `/change-angle` | Aus einem Take eine schnittfähige Sequenz machen | die Perspektive |
| `/transform-object` | Colourways und Finishes testen, ohne Muster | Material oder Farbe |
| `/localize` | Ein Master-Clip, mehrere Sprachmärkte | die Zielsprache |

Alle vier laufen auf demselben Endpoint: `google/gemini-omni-flash/edit`. Du
gibst einen Clip rein, den du schon hast, plus **eine** Anweisung in
Alltagssprache. Das Modell ändert das eine Ding und lässt den Rest stehen.

Der eigentliche Inhalt der Skills sind nicht die Skripte, sondern die
Prompt-Rezepte in `scripts/omni.py` und die Prüf-Checklisten in den
`SKILL.md`-Dateien. Die stehen dort, weil beides an echten Läufen kalibriert
ist und nicht geraten.

## Ohne eigenes Material starten

Wenn du gerade keinen Clip zur Hand hast, erzeugt dir das Skript einen:

```bash
python3 scripts/omni.py create \
  --prompt "A young woman in a grey hoodie holds a matte black water bottle on a sunlit city sidewalk, slow push-in, the words STAY SHARP burned into the lower third." \
  --aspect 16:9 --duration 8 --out ./examples --name source
```

Das läuft über den Text-to-Video-Endpoint desselben Modells. So ist der
Beispielclip in `examples/` entstanden — der vollständige Prompt steht in
[`examples/README.md`](examples/README.md).

## Das Kontaktblatt

Claude kann kein Video abspielen — ein JPG aber schon. Deshalb legt jeder Lauf
neben dem MP4 ein `…-compare.jpg` an: **obere Reihe Quelle, untere Reihe
Ergebnis**, jeweils Anfang, Mitte und Ende.

Das ist kein Deko-Feature. Es ist die Grundlage dafür, dass Claude in Schritt 3
jeder Skill wirklich hinschaut, statt „fertig" zu melden, weil eine Datei
existiert. Braucht `ffmpeg`; fehlt es, läuft alles andere normal weiter.

## Beispiele

In `examples/` liegt ein kompletter Durchlauf: ein Ausgangsclip und die vier
Ergebnisse, dazu die Kontaktblätter. **Alle vier sind Erstversuche**, kein
Cherry-Picking. Details und die exakten Befehle stehen in
[`examples/README.md`](examples/README.md).

## Kosten

Abgerechnet wird nach Videolänge: laut fal-Modellseite rund **0,13 $ pro
Sekunde** 720p-Video. Ein 8-Sekunden-Clip kostet also grob **1 $ pro Lauf** —
egal welche der vier Skills.

`--dry-run` zeigt Prompt und Größenordnung, ohne etwas auszugeben.

## Grenzen — ehrlich

Gemessen an einem 8-Sekunden-Clip mit einer Person, einem Produkt und
eingebranntem Text, über sechs Läufe.

- **Alle vier Skills liefen beim ersten Versuch durch.** Hintergrund, Material
  und Textübersetzung kamen sauber zurück, das Produkt blieb in Form und
  Position, der eingebrannte Text blieb in drei von vier Läufen unangetastet.
- **`change-angle` erfindet gelegentlich eine Handlung.** Im Beispiel hält die
  Person die Flasche neben die Schulter — im Over-the-Shoulder-Take trinkt sie
  daraus. Als B-Roll brauchbar, als Schnittgegenstück zum Original nicht. Immer
  gegen das Original prüfen.
- **Formulierung entscheidet über Identität.** Eine frühe Fassung des
  Hintergrund-Prompts bat darum, „das Licht an die neue Szene anzupassen" —
  daraufhin hat das Modell in einem Testlauf die Kleidung aller Personen mit
  umgebaut. Die ausgelieferte Fassung benennt Gesichter, Kleidung und Farben
  ausdrücklich als unveränderlich. Deshalb: an den Rezepten in `scripts/omni.py`
  nichts anhängen, ohne es zu messen.
- **720p ist die Decke.** Das Modell liefert 1280×720 bei 24 fps, mit Ton, in
  der Länge der Quelle. Es rechnet nicht hoch. Kleingedrucktes auf einem Etikett
  überlebt das nicht — Headlines und Beschriftungen schon.
- **Der Edit nimmt nur Text, keine Referenzbilder.** Du kannst kein exaktes
  Produkt und kein bestimmtes Gesicht in einen Clip setzen. Dafür brauchst du
  einen Reference-Endpoint plus Motion Control, nicht diesen hier.
- **Eine Änderung pro Aufruf.** Zwei Wünsche in einem Prompt („Nahaufnahme, und
  mach es Nacht") liefern zuverlässig einen davon. Zwei Aufrufe hintereinander
  sind der Weg.
- **Regionssperre — und warum sie hier nicht greift.** Google sperrt das
  Bearbeiten *hochgeladener* Videos für Nutzer in EWR, Schweiz und UK;
  *modell-generierte* Videos zu bearbeiten ist dort laut Google erlaubt. Über
  fal läuft die Anfrage ohnehin nicht aus dem EWR heraus, sondern über fals
  Infrastruktur — deshalb liefen unsere Läufe aus Deutschland durch, mit
  hochgeladener Datei wie mit öffentlicher URL. Rufst du das Modell dagegen
  direkt über die Google-Gemini-API auf, kann die Sperre greifen. Das ist dann
  kein Fehler im Skript.
- **Kein Voiceover.** Der Endpoint bearbeitet keine Stimmen. `/localize` ändert
  ausschließlich Text im Bild.

### Was du selbst prüfen musst

Das Skript kann sagen, dass eine Datei entstanden ist. Ob sie brauchbar ist,
entscheidet der Blick auf das Kontaktblatt. Jede `SKILL.md` hat dafür in
Schritt 3 eine eigene Checkliste; die kurze Fassung:

| | |
|---|---|
| Motiv | gleiche Person, gleiches Produkt, gleiche Position |
| Bewegung | gleiche Kamerafahrt, gleiche Handlung |
| Text | Buchstabe für Buchstabe, besonders Umlaute |
| Rest | nichts Neues im Bild, kein erfundenes Logo |

## Manuell aufrufen

Die Skills sind Wrapper, das Skript läuft auch allein:

```bash
python3 scripts/omni.py swap-background  --input clip.mp4 --to "a rainy Tokyo street at night"
python3 scripts/omni.py change-angle     --input clip.mp4 --angle close-up
python3 scripts/omni.py transform-object --input clip.mp4 --object "the bottle" --to "brushed chrome"
python3 scripts/omni.py localize         --input clip.mp4 --lang German --keep "the brand name"
python3 scripts/omni.py raw              --input clip.mp4 --prompt "..."
python3 scripts/omni.py create           --prompt "..." --aspect 9:16 --duration 8
```

| Flag | |
|------|--|
| `--input` | lokale Datei (wird hochgeladen) oder öffentliche URL |
| `--out` | Zielordner (Default `./out`) |
| `--name` | Basisname der Ausgabedatei |
| `--runs` | mehrere Generierungen derselben Anweisung |
| `--dry-run` | nur den Prompt und die Kosten zeigen |
| `--json` | Ergebnis maschinenlesbar auf stdout |

## Lizenz

MIT.
