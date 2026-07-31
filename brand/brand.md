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

Unten steht die Datei **komplett ausgefüllt** für eine erfundene Marke namens
Nordwand, damit du siehst, wie konkret die Einträge sein müssen. Überschreib
die Werte mit deinen eigenen, die Struktur lässt du stehen.

---

## 1 · Marke

- **Name:** Nordwand
- **Was wir verkaufen:** Isolierflaschen und Trinkbecher aus Edelstahl
- **Positionierung in einem Satz:** Ausrüstung für Leute, die draußen arbeiten,
  nicht für Leute, die draußen posieren.

## 2 · Produkte

Wie das Produkt im Bild **aussieht und benannt wird**. Der Text in der Spalte
„So heißt es im Prompt" geht wörtlich in `/transform-object --object`. Nimm die
schlichteste eindeutige Beschreibung, keine internen Namen und keine SKU-Codes —
das Modell hat die noch nie gesehen.

| Produkt | So heißt es im Prompt | Erkennungsmerkmal |
|---|---|---|
| Nordwand Flask 500 | `the black insulated bottle` | mattschwarz, gerader Korpus, schwarzer Deckel |
| Nordwand Cup 300 | `the steel cup` | gebürsteter Stahl, kein Henkel |

## 3 · Colourways und Finishes

Was du auf dem Schirm testen willst. Geht wörtlich in `/transform-object --to`.

- `matte black`
- `brushed stainless steel`
- `deep forest green`
- `sand beige with a black lid`

## 4 · Szenen, die zur Marke passen

Geht wörtlich in `/swap-background --to`. Je konkreter, desto besser: nicht
„eine Stadt", sondern die Straße, das Licht, die Tageszeit.

- `a wet granite ridge in early morning fog`
- `a workshop with sawdust in the light`
- `a snowy alpine village street at dusk with warm shop lights`

**Szenen, die nicht passen:** Nachtclub, Strandparty, alles Glossy-Luxuriöse.
Wenn Claude einen Vorschlag machen soll, soll er sich daran halten.

## 5 · Märkte und Sprachen

Geht in `/localize --lang` und `--keep`.

- **Märkte:** Deutschland, Österreich, Schweiz, Frankreich
- **Zielsprachen:** `German`, `French`
- **Bleibt immer unübersetzt** (`--keep`): `the brand name Nordwand`
- **Achtung:** Deutsch läuft breiter als Englisch. Bei langen Headlines prüfen,
  ob die Zeile noch ins Bild passt.

## 6 · Talent

Wer in den Clips zu sehen ist. Relevant, weil `/swap-background` und
`/change-angle` genau hier driften, wenn man nicht aufpasst.

- Eine Person, Ende 20, graue Kapuzenjacke, dunkle Haare zusammengebunden.
- **Muss über alle Varianten identisch bleiben.** Ändert sich Gesicht oder
  Kleidung, ist der Lauf Ausschuss.

## 7 · Tabu

Was in keinem Ergebnis auftauchen darf.

- Kein erfundenes Logo. Wir haben eine Wortmarke, keine Bildmarke — wenn im
  Ergebnis plötzlich ein Signet klebt, ist der Lauf Ausschuss.
- Keine anderen Markennamen im Bild.
- Keine Preisangaben, keine Rabattstörer.
