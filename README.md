# Restaurant-Tischmix: Welche Tische passen zu den Gruppen? – Streamlit-Demo

**[→ Demo live ausprobieren](https://sebastianhanisch-restaurant-tischmix-demo.streamlit.app/)**

Fall-Demo für die Website „Sebastian Hanisch – Operations Research und Machine Learning“ (Themenseite „Sitzplätze optimieren“). Ein **Restaurant ohne Reservierung** hat Tische für zwei, vier und sechs Personen; Gruppen
kommen als Poisson-Strom, werden an einen passenden Tisch gesetzt oder gehen (optional warten sie). Die Demo zeigt, was die **Tischform** gegenüber einem idealen Sitzplatz-Pool kostet, was ein auf die falsche
**Gruppenverteilung** ausgelegter **Tischmix** kostet, was **kombinierbare Tische** mit **Umbauzeit** bringen und ob **Warteschlange**, **Nachbarschaft im Grundriss** oder **Reservierungen** daran etwas ändern.
Alle Annahmen (Gruppenverteilungen, Verweildauern, Umbauzeit, Geduld) sind Regler oder gesetzt, nicht aus Betriebsdaten.

## Warum dieses Problem

Wer ein Restaurant einrichtet, wählt Tische für Gruppen, die er noch nicht kennt. Nach einer Vormessung (nicht Teil dieser Demo) holt eine klügere Annahmeregel am Eingang kaum etwas; entscheidend ist der **Mix aus Zweier-, Vier- und Sechsertischen** und ob sich Tische zusammenstellen
lassen. Die Demo fragt: **Welche Tische passen zu den Gruppen von morgen, und was kostet es, wenn die Annahme über die Gruppen falsch war?**

## Modell

- **Ankünfte und Dauer:** Gruppen der Größe 2, 3, 4 und 6 kommen als Poisson-Strom; die Rate wird so gewählt, dass die angebotenen Gastminuten gleich Last mal Platzminuten sind. Die Verweildauer ist exponentiell mit dem Mittel 45 + 10 · Gruppengröße Minuten.
  Vier **Gruppenverteilungen** (gesetzt; im Code `paare`, `klein`, `gross`, `gemischt`), jeweils mit den Anteilen der Gruppen mit 2 / 3 / 4 / 6 Personen und der mittleren Gruppengröße: „gemischt, viele Paare“ (0,45 / 0,17 / 0,28 / 0,10; Ø 3,1 Personen), „fast nur Paare“ (0,70 / 0,15 / 0,10 / 0,05; Ø 2,6), „viele große Gruppen“ (0,15 / 0,20 / 0,35 / 0,30; Ø 4,1) und „gleichmäßig gemischt“ (0,30 / 0,20 / 0,30 / 0,20; Ø 3,6).
- **Tischwahl:** Best-Fit nimmt den kleinsten freien Tisch, der passt; Worst-Fit den größten. Passt kein Einzeltisch und ist Kombination erlaubt, nimmt die Gruppe die freie Kombination zweier Tische mit der kleinsten Platzsumme, die passt
  (bei gleicher Summe das Paar, dessen kleinerer Tisch am kleinsten ist). Kombination: **aus**, **nur 2er** (zwei freie Zweiertische), **beliebig** (zwei beliebige freie Tische) oder **Nachbarn** (zwei freie Tische, die im Raster nebeneinander stehen).
- **Umbauzeit:** Eine kombinierte Gruppe belegt beide Tische um die eingestellten Minuten länger (Zusammenstellen und Auseinanderrücken). Die Minuten sind **gesetzt**: keine gesichtete Quelle nannte einen Wert.
- **Geduld:** Mit Geduld 0 geht eine Gruppe sofort, wenn kein Tisch passt (Verlustsystem). Mit Geduld größer 0 wartet sie so lange (konstant) und wird gesetzt, sobald ein Tisch frei wird und sie passt (in Reihenfolge der Ankunft; wer nicht passt, lässt die folgenden vorbei).
- **Grundriss:** Tische zeilenweise in einem Raster mit fünf Spalten; Nachbarn sind oben, unten, links und rechts. Anordnung „sortiert“ (kleine Tische zuerst) oder „verteilt“ (die größeren Tische gleichmäßig über das Raster).
- **Idealer Sitzplatz-Pool:** Jede Gruppe belegt genau ihre Gästezahl an Plätzen (keine Tischform); exakt per Kaufman-Roberts-Rekursion und als optimale Annahme per Relative Value Iteration.
- **Reservierung (Reiter):** sieben Tische (drei 2er, drei 4er, ein 6er), 22 Anfragen je Abend zu neun Startzeiten im 30-Minuten-Raster (0 bis 240 Minuten), Verteilung „gemischt, viele Paare“. Angenommen wird nach der **geplanten** Dauer (Planungsfaktor f mal Mittel), die **wirkliche** Dauer
  ist lognormal mit dem Variationskoeffizienten cv (Mittel gleich dem Mittel der Größe). Überzieht ein Gast, wartet die Folgegruppe; wartet sie länger als die Wartegrenze, geht sie (zugesagt, aber abgewiesen).
  Nettowert je Abend = bediente Gäste − w · abgewiesene Zusagen − c · Gästestunden Wartezeit der Bedienten (w und c gesetzt).

## Methodik

| Verfahren | Wie es arbeitet | Grenze |
|---|---|---|
| **Ereignissimulation** | Poisson-Ankünfte, Tischwahl, Kombination, Warteschlange, Grundriss (`rtm_algorithm.py`) | Läufe mit endlicher Länge, Standardfehler wird angegeben |
| **Exakte Markov-Kette** | stationäre Verteilung über Besetzungszustände (Tischarten statt einzelner Tische; `rtm_exact.py`), nur erreichbare Zustände | gilt für Geduld 0 und Kombination aus, nur 2er oder beliebig; keine Nachbarschaft; kombinierte Gruppen haben die Dauer Exp(Mittel + Umbauzeit), die Simulation Exp(Mittel) + Umbauzeit (gleiches Mittel, andere Verteilung; gemessener Unterschied höchstens 0,24 %, siehe Test) |
| **Kaufman-Roberts** | idealer Pool ohne Tischform | Annahme: Verweildauern exponentiell; für feste Tische gilt die Rekursion nicht |
| **Reservierungsabend** | Annahme nach geplanter Dauer, lognormale wirkliche Dauer (`rtm_reserve.py`) | sieben Tische, 22 Anfragen, ein Raster von 30 Minuten |

Alle Zufallsfolgen kommen aus einem eigenen SplitMix64 mit festem Zufalls-Seed; die Live-Rechnung der App mittelt 8 Läufe zu je 3000 Stunden (nach 300 Minuten Einschwingzeit, Zufalls-Seeds Sitzungs-Seed · 1000 + k),
die Messreihen unten nutzen 12 Zufalls-Seeds (100000 bis 100011, je 3000 Stunden) oder, wo es dasteht, die exakte Kette; die Reservierungsabende: 3000 Abende mit dem Zufalls-Seed 35.

## Befunde (gemessen, keine Behauptungen)

Alle Zahlen stammen aus `data/rtm_results.json` (`tools/make_results.py`) und werden in `tests/test_claims.py` gezählt; davon rechnen die Tests je eine Zeile der exakten Mixe, der Simulationen und der Reservierungsabende neu. Wo nichts anderes steht:
24 Plätze, Last 1,0, Best-Fit, Geduld 0, 19 Tischmixe (Zahl der 2er, 4er und 6er), vier Gruppenverteilungen; „Gäste je Stunde“ ist die Zahl bedienter Gäste. **Bedauern** eines Mixes = wie viel mehr Gäste der beste Mix für die eingetretene Verteilung bedient, in Prozent der Gäste des gewählten Mixes (G_best / G − 1); als Anteil der möglichen Gäste, den der gewählte Mix verliert, ist es r / (100 + r) · 100 für das Bedauern r. Alle Verhaltensparameter sind Annahmen.

| Frage | Befund | Test |
|---|---|---|
| Was kostet die Tischform? | Der ideale Sitzplatz-Pool schafft 12,861 / 14,600 / 10,953 / 11,758 Gäste je Stunde (gemischt, viele Paare / fast nur Paare / viele große Gruppen / gleichmäßig gemischt). Der beste Mix ohne Kombination liegt **13,1 / 11,4 / 10,9 / 13,7 %** darunter (11,181 mit 4 × 2er und 4 × 4er; 12,935 mit 6 × 2er und 3 × 4er; 9,760 mit 3 × 4er und 2 × 6er; 10,149 mit 1 × 2er, 4 × 4er und 1 × 6er), mit Kombination (10 Minuten Umbau) **6,7 / 6,5 / 6,2 / 6,9 %**. Die optimale Annahme im Pool liegt höchstens 0,002 Gäste je Stunde über Kaufman-Roberts. Im Standardrestaurant der App (4 × 2er und 4 × 4er, „gemischt, viele Paare“, Zufalls-Seed 35, 8 Läufe zu je 3000 Stunden) sind die Tische im Mittel zu 64 % belegt und die Plätze zu 58 % mit Gästen | `test_tischform_kostet_gegen_den_pool`, `test_standardrestaurant_belegung`, `test_pool_optimum_und_kaufman_roberts_stimmen_bis_auf_zwei_tausendstel_ueberein` |
| Was kostet ein falsch geschätzter Mix? | Ohne Kombination bedient der beste Mix für „viele große Gruppen“ **54,3 % mehr** Gäste als der für „fast nur Paare“ gewählte (dieser verliert 35,2 % der möglichen Gäste); für „gemischt, viele Paare“ gewählt, „viele große Gruppen“ eingetreten: 32,0 % mehr (24,2 % verloren); für „viele große Gruppen“ gewählt, „fast nur Paare“ eingetreten: 42,8 % mehr (30,0 % verloren). Bei 7 der 12 Fehlannahmen bedient der passende Mix mehr als 10 % mehr Gäste (6 von 12, wenn man den Anteil verlorener Gäste nimmt). Der robusteste Mix (3 × 2er, 3 × 4er, 1 × 6er) hat ein größtes Bedauern von **12,5 %** (11,1 % verlorene Gäste). Mit Kombination (beliebige Paare) sinkt das größte Bedauern auf **15,8 / 15,9 / 16,2 %** (13,6 / 13,7 / 13,9 % verloren; Umbauzeit 0 / 10 / 20 Minuten), beim robustesten Mix (6 × 2er, 3 × 4er) auf **4,8 / 3,9 / 3,0 %** (4,6 / 3,7 / 2,9 %). Ohne die Verteilung „gleichmäßig gemischt“ bleiben diese Werte gleich | `test_falsch_geschaetzter_mix_ohne_kombination`, `test_falsch_geschaetzter_mix_mit_kombination`, `test_bedauern_als_anteil_verlorener_gaeste`, `test_vierte_verteilung_aendert_nichts_am_befund` |
| Was bringt Kombination, was kostet Umbauzeit? | Zuwachs des besten kombinierbaren Mixes gegen den besten Mix ohne Kombination (gemischt, viele Paare / fast nur Paare / viele große Gruppen / gleichmäßig gemischt): **9,8 / 7,9 / 8,4 / 10,5 %** ohne Umbauzeit, **7,4 / 5,6 / 5,3 / 7,9 %** mit 10 Minuten, **5,1 / 3,4 / 2,3 / 5,4 %** mit 20 Minuten. Kombination (derselbe Mix) ist schlechter als ohne in **6 / 15 / 21 von 76** Mix-Verteilungs-Zellen (0 / 10 / 20 Minuten) | `test_haltekosten_zuwachs_schrumpft_versicherung_bleibt` |
| Ändert eine Warteschlange das? | Gäste je Stunde der drei passenden Mixe (Mittel): Geduld 0 / 15 / 30 Minuten **11,295 / 12,113 / 12,664** ohne Kombination (+7,2 und +12,1 % gegen Geduld 0), **11,588 / 12,495 / 13,101** mit Kombination (10 Minuten Umbau). Das größte Bedauern unter den drei Bestmixen **ohne** Kombination ((4,4,0), (6,3,0), (0,3,2) für „gemischt, viele Paare“, „fast nur Paare“ und „viele große Gruppen“; auch dann, wenn alle drei mit Kombination gespielt werden) bleibt: **54,2 / 55,6 / 56,1 %** ohne, **45,1 / 42,4 / 44,4 %** mit Kombination (als verlorene Gäste 35,1 / 35,7 / 35,9 bzw. 31,1 / 29,8 / 30,7 %; Simulation, 12 Zufalls-Seeds, 3000 Stunden je Zelle, Standardfehler höchstens 0,04 Gäste je Stunde) | `test_warteschlange_mehr_gaeste_gleiche_rangfolge`, `test_bedauern_als_anteil_verlorener_gaeste` |
| Kostet Nachbarschaft viel? | Kombination nur zwischen Nachbartischen (acht 2er und zwei 4er im Raster mit fünf Spalten) kostet gegenüber beliebigen Paaren **0,3 bis 2,8 %** der Gäste (12 Zellen: drei Verteilungen, zwei Anordnungen, 0 und 10 Minuten Umbau). Die Anordnung der Tische ändert höchstens 0,1 Gäste je Stunde (Simulation, 12 Zufalls-Seeds, 3000 Stunden, Standardfehler höchstens 0,03) | `test_nachbarschaft_kostet_wenig` |
| Tischwahl und Größe? | Kleines Restaurant (2 × 2er, 2 × 4er, 1 × 6er, „gemischt, viele Paare“, exakt): Best-Fit **7,807**, Worst-Fit **6,987** Gäste je Stunde (10,5 % weniger), bei Gastbelegung 56,1 gegen 48,7 % und Tischbelegung 68,9 gegen 70,2 %. Kombination beliebiger Paare (ohne Umbauzeit) bringt dort **+1,7 %** (7,938), dem doppelt so großen Restaurant (4 × 2er, 4 × 4er, 2 × 6er) **+0,9 %** (17,796 gegen 17,632) | `test_tischwahl_best_fit_gegen_worst_fit_und_restaurantgroesse` |
| Wie lang soll ein Tisch eingeplant werden (Reservierung)? | Nur nach bedienten Gästen liegt der beste Planungsfaktor am Rand (0,5) und die Gästezahl fällt von 49,3 (f 0,5) auf 36,7 (f 1,5) je Abend (Streuung 0,5, Wartegrenze 15 Minuten, 3000 Abende, ein Zufalls-Seed, Standardfehler der Gäste je Abend höchstens 0,12); dabei werden 10,4 gegen 0,6 Gäste je Abend zugesagt und an der Tür abgewiesen. Mit einem **Preis w** je abgewiesener Zusage liegt der beste Faktor meist innen: w = 1: 0,85; w = 2: 0,85 bis 1,15; w = 4: 1,0 bis 1,5 (je Streuung und Wartegrenze, Wartewert c = 0); bei w = 4, Streuung 0,75 und Wartegrenze 15 liegt er mit 1,5 am Rand des gerechneten Bereichs. Innerhalb dieser Bereiche hängt der genaue Wert am Zufalls-Seed: eine Nachrechnung mit Zufalls-Seed 36 (nicht in den Tests) ließ ihn bei w ≥ 2 in 3 von 12 Zellen wechseln, die Bereiche blieben gleich. Bei w = 2, Streuung 0,5, Wartegrenze 15 liegen die Nettowerte der Faktoren 1,0 / 1,15 / 1,3 innerhalb von 0,25 Gästen je Abend (ein Plateau) | `test_reservierung_bester_planungsfaktor_haengt_am_preis`, `test_reservierung_plateau_bei_preis_zwei`, `test_reservierung_bediente_gaeste_und_zusagen` |

### Befunde und Korrekturen gegenüber der Vormessung

- **Der Hook hat gewechselt:** Die Vormessung (Planungsordner, nicht in diesem Repo) fand, dass eine kluge Annahmeregel nach Gruppengröße kaum etwas holt (im exakten Modell höchstens 1,7 % über Best-Fit mit Kombination). Diese Aussage ist **nicht Teil dieser Demo**
  (der Optimierer dafür ist nicht eingebaut); der Hook ist jetzt die Wette auf die Gruppenverteilung (Kernfrage 2).
- **Neu gegenüber der Vormessung:** Umbauzeit, Warteschlange und Nachbarschaft sind hier gemessen; die Vormessung nahm die Kombination ohne Haltekosten an (das ist die Spalte „0 Minuten“) und rechnete nur ein Verlustsystem.
- **Reservierung:** Die Vormessung nannte acht Startzeiten; es sind neun (0 bis 240 Minuten). Ohne Preis für abgewiesene Zusagen gibt es keinen inneren Bestwert; die frühere Fassung hatte das als offen gelassen.
- **Kette gegen Simulation:** Bei Umbauzeit rechnen die exakte Kette und die Simulation mit verschiedener Verteilung der kombinierten Dauer (Exp(Mittel + Umbauzeit) gegen Exp(Mittel) + Umbauzeit, gleiches Mittel); die 18 Zellen der Geduld-Messreihe bei Geduld 0 weichen höchstens 0,24 % (und höchstens 1,2 Standardfehler) von den exakten Werten ab, ohne Kombination höchstens 0,13 %.
- **Vierte Verteilung:** Die Vormessung nutzte drei Verteilungen; „gleichmäßig gemischt“ ist neu und ändert den Befund nicht (Test oben).

## Ehrliche Grenzen

- Gruppenverteilungen, Verweildauern, Umbauzeit, Geduld, der Preis einer abgewiesenen Zusage und der Wartewert sind **gesetzte Annahmen**. **Literatur (Websuche 2026-11-12, nur Titel und Abstract, kein Volltext):** Zur Robustheit des Tischmix gegen eine falsch geschätzte Gruppenverteilung wurde **nichts gefunden**;
  das heißt nicht, dass es nichts gibt. Bekannt ist, dass der beste Mix zum Gruppenmix passt (Kimes und Thompson 2004 und 2005, Thompson 2003 und CHR-Bericht „Dedicated or Combinable?“) und dass Kombinierbarkeit in kleinen Restaurants mit kleinen Gruppen am meisten bringt;
  für Umbauzeiten beim Zusammenstellen von Tischen nannte keine gesichtete Quelle Minuten. Ein sehr ähnliches Verlustsystem mit kombinierbaren Zweiertischen beschreibt ein Blogbeitrag von Van Hautegem und Rogiest (2017; keine Fachveröffentlichung).
- Das Modell kennt **keine Überbuchung**, keine No-Shows, keine Stoßzeiten (die Last ist konstant), keine Gruppenverkleinerung und **keinen leer gehaltenen Tisch**, der auf einen Nachbartisch wartet; die Umbauzeit ist nur eine Zusatzzeit.
- Der Grundriss kennt ein Raster mit fünf Spalten und direkte Nachbarn, keine Wege, keine Küche, keine Lage von Fenstern oder Eingang.
- Die Bedauern-Matrix gilt für 24 Plätze, Last 1,0, Best-Fit und Geduld 0; eine Nachrechnung mit 18 Plätzen (nicht in den Tests dieses Repos) zeigte ohne Kombination dasselbe Muster mit größerem Bedauern (62,4 statt 54,3 %); mit Kombination und Umbauzeit war das größte Bedauern dort kleiner (12,0 und 12,6 statt 15,9 und 16,2 %), ohne Umbauzeit größer (26,2 statt 15,8 %); für größere Restaurants ist die Matrix nicht gerechnet (die exakte Kette ist für viele Mixe zu groß, zum Beispiel für 8 × 2er, 4 × 4er und 2 × 6er mit Kombination, die Simulation nicht für alle Mixe gelaufen).
- Die Reservierungsrechnung nutzt sieben Tische und 22 Anfragen; „beste Planlänge“ hängt am gesetzten Preis einer abgewiesenen Zusage und liegt bei mittlerem Preis auf einem Plateau.
- Die Live-Rechnung nutzt wenige Läufe; die Messreihen mehr Läufe und feste Zufalls-Seeds.

## Verifikation

- **Kern:** Tischwahl von Hand an kleinen Fällen (Best-Fit, Worst-Fit, Kombination, Gleichstand, erlaubte Paare), Rate nach Handrechnung, Einzeltisch gegen die Formel des Verlustsystems (M/M/1/1; die Handrechnung der Erklärseite „ein einziger Zweiertisch“ steht als Test dabei), SplitMix64 gegen Referenzwerte, Reproduzierbarkeit, Randfälle (kleinstes und größtes Restaurant, ungültige Eingaben, Reglergrenzen, Zustandsgrenze der exakten Kette).
- **Orakel (`tests/test_oracle_restaurant_tischmix.py`):** die exakte Kette gegen eine zweite Umsetzung mit **einzelnen Tischen** (jeder Zustand ist die Belegung jedes Tisches, dichte Matrix, anderer Löser) in sieben Fällen (Best-Fit und Worst-Fit, Kombination aus, nur 2er und beliebig, Umbauzeit 0 bis 20 Minuten),
  Kaufman-Roberts gegen die Markov-Kette des Pools (vier Verteilungen), optimale Annahme im Pool nie unter Kaufman-Roberts, Simulation gegen die exakte Kette (vier Standardfehler), Prüfwerte der Vormessung (7,807 / 7,938 / 6,987 / 11,181 / 12,033 / 11,834). Die zweite Umsetzung stammt vom selben Autor nach denselben Regeln und teilt die Dauer-Annahme der Kette (kombinierte Gruppen Exp(Mittel + Umbauzeit)): sie bestätigt die Umsetzung, nicht die Regeln; den Unterschied zur Simulation misst ein eigener Test.
- **Zahlen:** `tests/test_claims.py` zählt jede Zahl der Befund-Tabelle über die ganze Messdatei und rechnet je eine Zeile der exakten Mixe, der Geduld-Simulation und der Reservierungsabende neu (die übrigen Teile der Messdatei werden gegen die Datei gezählt, nicht neu gerechnet).
- **Verdikte:** reine Funktionen in `rtm_evaluation.py`, an handgesetzten Werten und für jedes Preset geprüft (`tests/test_verdicts.py`).
- **Presets, Layout, Oberfläche:** Vollständigkeit und Werte der Presets; Schnellstart oben in der Seitenleiste, fester Kopf, aktives Preset hervorgehoben, jede Regleränderung hebt die Markierung auf; AppTest; Footer; Laufzeit-Importe.
- **Testzahl:** 155 Tests (`pytest --collect-only -q tests`).

## Dateistruktur

| Datei | Zweck |
|---|---|
| `.github/workflows/tests.yml` | CI: Push, Pull Request, wöchentlicher Canary |
| `app.py` | Streamlit-App |
| `data/rtm_results.json` | vorgerechnete Messreihen |
| `requirements-dev.txt` | Laufzeit plus pytest |
| `requirements.txt` | Laufzeit-Bibliotheken (ungepinnt) |
| `tools/make_results.py` | erzeugt `data/rtm_results.json` mit festen Zufalls-Seeds |
| `rtm_algorithm.py` | Kern: Ereignissimulation, Tischwahl, Studie über mehrere Läufe |
| `rtm_constants.py` | Regler-Grenzen, Verteilungen, Farben, Presets |
| `rtm_evaluation.py` | Verdikte (reine Funktionen), Bedauern-Matrix, Auswertung der Messreihen |
| `rtm_exact.py` | exakte Markov-Kette, Kaufman-Roberts, optimale Annahme im Pool |
| `rtm_layout.py` | Fester Kopf (Stylesheet) |
| `rtm_presets.py` | Permalink, Presets (Schnellstart in der Seitenleiste, aktives Preset hervorgehoben), Zufalls-Seed-Button |
| `rtm_reserve.py` | Reservierungsabend |
| `rtm_rng.py` | eigener Zufallsgenerator (SplitMix64) |
| `rtm_scenario.py` | Parameter des Restaurants (nur Schlüsselwörter), Grundriss, Rate |
| `rtm_visualization.py` | Plotly-Abbildungen (Achsen gesperrt) |
| `tests/` | Kern, Randfälle, Orakel, Zahlen, Verdikte, Presets, Layout, AppTest, Footer, Laufzeit-Importe |

## Bewusst nicht umgesetzt

- **Überbuchung und No-Shows:** gehört als Erweiterung in `revenue-management-demo`, nicht hierher.
- **Leer gehaltene Tische, Stoßzeiten, Gruppenverkleinerung:** eigene Modelle; die Umbauzeit ist nur eine Zusatzzeit.
- **Optimierer für die Annahmeregel** (Markov-Entscheidungsprozess): die Vormessung fand dort höchstens 1,7 % über Best-Fit; er gehört nicht in diese Demo.
- **Kalibrierung auf ein echtes Restaurant:** keine Betriebsdaten eingelesen.

## Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

## Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Gebaut mit Streamlit, Plotly, NumPy und SciPy.

---

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zum Thema: [Sitzplätze optimieren](https://sebastianhanisch.net/sitzplaetze-optimieren.html).
