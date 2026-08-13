# Arbeitsweise in diesem Repo

Kurzfassung für Claude Code. Die ausführliche Version steht in den vier
`SKILL.md`-Dateien unter `.claude/skills/`.

## Vor jedem Lauf

Lies `brand/brand.md`, falls vorhanden. Dort stehen die Produktbezeichnungen,
die ins Prompt gehören, die Colourways, die markengerechten Szenen, die
Zielsprachen und die Tabus. Frag nicht nach etwas, das dort schon steht.

## Bevor du Geld ausgibst

**Jede Variante ist ein eigener Aufruf.** Über fal rund **0,25 $ pro Sekunde**
Cliplänge — vier Märkte aus einem 8-s-Clip sind also ~8 $. Über Google etwa
0,14 $/s, und dort nennt das Skript nach dem Lauf den exakten Preis, weil Google
die Tokenzahlen mitliefert; fal tut das nicht, dort bleibt es eine Schätzung.

Bei mehr als etwa drei Varianten erst `--dry-run` zeigen und eine Bestätigung
abwarten. **Nie ungefragt einen Lauf starten, der Geld kostet** — auch keinen
einzelnen zum Ausprobieren.

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

Hängt am Anbieter, und das Skript sagt beim Start, welcher greift.

**Über fal** geht jeder Clip — hochladen und los. Das ist der Grund, warum fal
der Standardweg ist.

**Über Google** sind hochgeladene Videos aus EWR, Schweiz und UK gesperrt. Dann
arbeiten die vier Skills auf Ergebnissen von `create` oder `animate`; die
Verkettung läuft automatisch über das Manifest neben dem Video. Bringt jemand
eigenes Drehmaterial mit und hat nur einen Google-Key, sag ehrlich, dass dieser
Weg das nicht kann — und biete `animate` an, falls ein Produktfoto vorliegt.
