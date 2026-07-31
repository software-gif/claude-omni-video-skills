# Beispiele

Ein kompletter Durchlauf, kein Cherry-Picking: **alle vier Ergebnisse hier sind
Erstversuche.** Jedes `.jpg` ist das Kontaktblatt, das das Skript automatisch
mitschreibt — obere Reihe Quelle, untere Reihe Ergebnis, jeweils Anfang, Mitte,
Ende.

![Quelle oben, die vier Skills darunter](overview.jpg)

## Der Ausgangsclip

`source.mp4` ist selbst mit Omni erzeugt, damit die Beispiele frei
weitergegeben werden können:

```bash
python3 scripts/omni.py create \
  --prompt "A bright commercial lifestyle shot in a single continuous take: a young woman in a plain grey hoodie stands on a sunlit city sidewalk and holds a matte black stainless steel water bottle up beside her shoulder, turning it slightly toward the camera. The camera slowly pushes in. Bold white sans-serif text reading STAY SHARP is burned into the lower third of the frame. Clean modern buildings and green trees behind her, bright natural daylight. No dialogue, soft ambient city sound." \
  --aspect 16:9 --duration 8 --out ./examples --name source
```

8 Sekunden, 1280×720, 24 fps, mit Ton.

## Die vier Läufe

| Datei | Befehl | Ergebnis |
|---|---|---|
| `swap-background.mp4` | `swap-background --to "a snowy alpine village street at dusk with warm shop lights"` | sauber |
| `change-angle.mp4` | `change-angle --angle over-the-shoulder` | neue Perspektive, aber neue Handlung (siehe unten) |
| `transform-object.mp4` | `transform-object --object "the black water bottle" --to "brushed chrome"` | sauber |
| `localize.mp4` | `localize --lang German` | sauber, „STAY SHARP" → „BLEIB SMART" |

Jeweils vollständig, zum Beispiel:

```bash
python3 scripts/omni.py swap-background \
  --input examples/source.mp4 \
  --to "a snowy alpine village street at dusk with warm shop lights" \
  --out ./out
```

Diese vier Läufe entstanden einzeln. Heute würde man dieselbe Reihe als **einen**
Befehl aufrufen — `--to`, `--angle` und `--lang` sind wiederholbar, der Clip wird
dann einmal statt viermal hochgeladen und am Ende entsteht zusätzlich ein
`…-overview.jpg` über alle Varianten:

```bash
python3 scripts/omni.py swap-background --input examples/source.mp4 \
  --to "a snowy alpine village street at dusk with warm shop lights" \
  --to "a rainy Tokyo side street at night" \
  --to "a Miami boardwalk at golden hour" \
  --out ./out
```

## Was in diesen Läufen auffällt

**`change-angle` hat eine Handlung erfunden.** In der Quelle hält die Frau die
Flasche neben die Schulter. Im Over-the-Shoulder-Take trinkt sie daraus. Szene,
Kleidung, Licht und der eingebrannte Text stimmen, die Handlung nicht. Für eine
Sequenz, die gegen das Original geschnitten wird, ist das ein Ausschuss — dafür
noch einmal laufen lassen. Als eigenständiger B-Roll-Take ist es brauchbar.
Genau deshalb steht in `change-angle/SKILL.md` „gleiche Handlung" als
Prüfpunkt.

**Der eingebrannte Text hat drei von vier Edits unverändert überlebt.** Bei
`swap-background`, `change-angle` und `transform-object` steht „STAY SHARP"
danach exakt so da wie vorher. Nur `localize` hat ihn angefasst — das war der
Auftrag.

**Der Prompt für `swap-background` musste nachgeschärft werden.** Eine frühere
Fassung sagte sinngemäß „Hauptmotiv und Kamerafahrt behalten, Licht an die neue
Szene anpassen". In einem Testlauf mit einer Menschengruppe hat das Modell
daraufhin die Kleidung aller Personen an die neue Szene angepasst. Die
ausgelieferte Fassung benennt stattdessen ausdrücklich „gleiche Gesichter,
gleiche Kleidung, gleiche Farben" — damit blieb die Person im Beispiel oben
identisch.
