# Arbeitsweise in diesem Repo

Kurzfassung für Claude Code. Die ausführliche Version steht in den vier
`SKILL.md`-Dateien unter `.claude/skills/`.

## Vor jedem Lauf

Lies `brand/brand.md`, falls vorhanden. Dort stehen die Produktbezeichnungen,
die ins Prompt gehören, die Colourways, die markengerechten Szenen, die
Zielsprachen und die Tabus. Frag nicht nach etwas, das dort schon steht.

## Bevor du Geld ausgibst

Ein Lauf kostet rund **0,13 bis 0,14 $ pro Sekunde** Cliplänge, und **jede
Variante ist ein eigener Aufruf** — vier Märkte aus einem 8-s-Clip sind ~4,50 $.
Den exakten Preis nennt das Skript nach jedem Lauf; Google liefert die
Tokenzahlen mit. Bei mehr als
etwa drei Varianten erst `--dry-run` zeigen und eine Bestätigung abwarten. Nie
ungefragt einen großen Batch starten.

Wenn der Quellclip länger ist als nötig: vorher kürzen vorschlagen. Bezahlt
werden Input und Ausgabe, beides skaliert mit der Länge.

## Wenn der Nutzer kein Video hat

Nur Produktfotos ist der Normalfall. Dann `animate` vorschlagen: aus einem
Packshot wird ein Ausgangsclip, auf dem die vier Skills laufen können. Nicht
abwinken, weil kein Video da ist.

## Nach jedem Lauf

Melde niemals Erfolg, weil eine Datei existiert. Jeder Lauf schreibt ein
`…-compare.jpg` (Quelle oben, Ergebnis unten), ein Batch zusätzlich ein
`…-overview.jpg`. **Lies diese Bilder** und prüf sie gegen die Checkliste in der
jeweiligen `SKILL.md`. Bei einem Batch jede Variante einzeln.

Berichte ehrlich, welche Varianten sauber sind und welche nicht. Ein
erfundener Bewegungsablauf oder ein verrutschter Buchstabe macht das Ergebnis
unbrauchbar, auch wenn die Datei gut aussieht.

## Was du nicht tust

**Die Prompt-Rezepte in `scripts/omni.py` nicht verlängern.** Sie sind an echten
Läufen kalibriert. Der Edit-Endpoint arbeitet mit einer kurzen Anweisung am
besten; jeder zusätzliche Satz ist eine weitere Erlaubnis, etwas umzubauen. Eine
frühere, längere Fassung des Hintergrund-Prompts hat die Kleidung aller Personen
im Bild mit umgebaut. Brauchst du etwas, das kein Rezept abdeckt, nimm
`scripts/omni.py raw --prompt "…"` mit ein bis zwei Sätzen.

**Keine zwei Änderungen in einen Aufruf packen.** „Nahaufnahme, und mach es
Nacht" liefert zuverlässig eine von beiden. Zwei Aufrufe hintereinander.

**Nicht die `.env` lesen oder ausgeben.** Der Key wird vom Skript geladen.

## Woher der Clip kommen muss

Google lässt aus dem EWR keine **hochgeladenen** Videos bearbeiten. Die vier
Skills arbeiten deshalb auf Ergebnissen von `create` oder `animate`; die
Verkettung läuft automatisch über das Manifest neben dem Video. Bringt jemand
eigenes Drehmaterial mit, sag ehrlich, dass dieser Weg das nicht kann — und
biete `animate` an, falls ein Produktfoto vorliegt.
