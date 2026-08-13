# Markenkontext

Das hier ist die Datei, die aus einem Video-Werkzeug ein Marken-Werkzeug macht.
Du füllst sie **einmal** aus. Danach liest Claude sie vor jedem Lauf und
formuliert die Anweisung an Omni selbst — auf deine Produkte, deine Märkte,
deinen Look.

Ohne diese Datei funktionieren die Skills auch, du musst dann nur jedes Mal
selbst sagen, welche Szene, welches Material, welche Sprache.

**Alles auf Englisch eintragen, was später im Prompt landet.** Omni versteht
Deutsch, trifft aber auf Englisch spürbar zuverlässiger. Die Überschriften und
deine Notizen dürfen deutsch bleiben.

---

## 1 · Marke

- **Name:** STUR — [sturcookware.de](https://sturcookware.de)
- **Was wir verkaufen:** Gusseisen-Kochgeschirr, Made in Germany
- **Positionierung in einem Satz:** Gusseisen der nächsten Generation — leichter
  und glatter als klassisches Gusseisen, dafür unkaputtbar.
- **Was die Marke trägt:** 50 Jahre Garantie, frei von PFAS/PTFE, natürliche
  Antihaft-Patina statt Beschichtung, computergesteuert glatt gefräst.
- **Preislage:** Einzelpfannen 159–249 €, Bräter bis 379 €. Kein Billigsegment,
  also auch keine Rabatt-Optik.

## 2 · Produkte

Wie das Produkt im Bild **aussieht und benannt wird**. Der Text in der Spalte
„So heißt es im Prompt" geht wörtlich in `/transform-object --object`. Nimm die
schlichteste eindeutige Beschreibung, keine internen Namen und keine SKU-Codes —
das Modell hat die noch nie gesehen.

| Produkt | So heißt es im Prompt | Erkennungsmerkmal |
|---|---|---|
| Gusseisenpfanne 20/24/28/32 cm | `the black cast iron pan` | mattschwarz außen, glatt gefräste hellere Innenfläche, langer gerader Griff mit Aufhängeloch, zwei Ausgusslippen |
| Grillpfanne 28 cm | `the ridged cast iron grill pan` | wie oben, aber mit Grillrippen im Boden |
| Planchapfanne 30 cm | `the flat cast iron griddle` | flach, randlos, ohne Ausguss |
| Gusseisenbräter 28 cm | `the cast iron braiser with its lid` | rund, zwei kurze Seitengriffe, separater Deckel |
| Griffschutz | `the black silicone handle sleeve` | Zubehör, selten Hauptmotiv |

**Wichtig für alle Läufe:** Die STUR-Wortmarke ist schwarz auf schwarz in den
Griff geprägt und sehr klein. Bei 720p überlebt sie einen Edit nicht zuverlässig
— nicht darauf bauen, dass sie lesbar bleibt, und sie im Ergebnis auch nicht als
Qualitätskriterium heranziehen. Wer Markenpräsenz im Clip braucht, legt sie als
Text ins Bild statt sie vom Produkt zu erwarten.

## 3 · Colourways und Finishes

**STUR verkauft aktuell ausschließlich schwarzes Gusseisen.** Damit ist
`/transform-object` hier kein Colourway-Test, sondern etwas Interessanteres:
eine Vorschau auf Linien, die es noch nicht gibt. Genau dafür lohnt sich das
Werkzeug — man sieht, wie eine Variante wirkt, bevor eine Form gebaut wird.

Sinnvolle Ziele, wörtlich für `/transform-object --to`:

- `enamelled cream white with a black rim`
- `enamelled deep forest green`
- `enamelled burgundy red`
- `brushed stainless steel`
- `raw unseasoned grey cast iron`

## 4 · Szenen, die zur Marke passen

Geht wörtlich in `/swap-background --to`. Je konkreter, desto besser: nicht
„eine Küche", sondern die Fläche, das Licht, die Tageszeit.

- `a warm home kitchen with oak worktops and low morning light`
- `a professional kitchen pass with brushed steel surfaces`
- `a stone slab beside an open campfire at dusk`
- `a snowy cabin kitchen with a window onto the mountains`
- `a plain off-white studio surface with soft top light` (ihr Packshot-Look)

**Szenen, die nicht passen:** alles Glänzend-Luxuriöse, Nachtclub, Strandparty,
Hochglanz-Marmor. STUR verkauft Solidität, nicht Glamour. Wenn Claude einen
Vorschlag machen soll, soll er sich daran halten.

## 5 · Märkte und Sprachen

Geht in `/localize --lang` und `--keep`. **Das ist bei STUR die stärkste der
vier Skills:** Der Shop liefert in 28 europäische Länder, die Creatives sind
aber deutsch.

- **Heimatmarkt:** Deutschland, Österreich, Schweiz
- **Weitere Länder:** unter anderem Frankreich, Italien, Spanien, Niederlande,
  Belgien, Polen, Dänemark
- **Zielsprachen zuerst:** `French`, `Italian`, `Spanish`, `Dutch`
- **Bleibt immer unübersetzt** (`--keep`): `the brand name STUR`
- **Achtung:** Französisch und Italienisch laufen länger als Deutsch. Bei
  Headlines prüfen, ob die Zeile noch ins Bild passt.

## 6 · Talent

- Die Creatives sind überwiegend **produktzentriert** — Pfanne als Held, oft
  Hände beim Kochen, seltener ganze Personen.
- Wenn eine Person im Bild ist, **muss sie über alle Varianten identisch
  bleiben**. Ändert sich Gesicht oder Kleidung, ist der Lauf Ausschuss.
- Hände am Griff sind ein wiederkehrendes Motiv und bei Perspektivwechseln die
  empfindlichste Stelle — Finger prüfen.

## 7 · Tabu

- **Keine erfundenen Claims.** „PFAS-frei", „50 Jahre Garantie" und
  „Made in Germany" sind geprüfte Aussagen. Das Modell darf keine neuen
  Versprechen ins Bild schreiben, und bestehende nicht umformulieren.
- **Kein erfundenes Logo.** STUR hat eine Wortmarke, kein Signet. Taucht im
  Ergebnis ein Emblem auf, ist der Lauf Ausschuss.
- Keine anderen Kochgeschirr-Marken im Bild.
- Keine Rabattstörer, keine Preisangaben.
- Kein Teflon-artiger Glanz auf der Pfanneninnenfläche — die Marke definiert
  sich über die beschichtungsfreie Patina.

---

## Wo das Bildmaterial liegt

STUR-Packshots stehen öffentlich im Shop, 2500 × 2500 px auf hellem Creme-Grund,
zum Beispiel `sturcookware.de/cdn/shop/files/24cm.png`. Die eignen sich direkt
als Eingabe für `animate`, um daraus einen Ausgangsclip zu machen.

**Rechtlicher Hinweis:** Für internes Testen unproblematisch. Was am Ende
öffentlich gezeigt wird, sollte mit STUR abgestimmt sein — es ist deren
Bildmaterial und deren Marke.
