"""Restaurant-Tischmix: Welche Tische passen zu den Gruppen? - interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Ein Restaurant ohne Reservierung: Gruppen kommen, werden an einen passenden Tisch gesetzt oder gehen. Die Demo zeigt, was die Tischform kostet, was ein auf die falsche Gruppenverteilung
ausgelegter Tischmix kostet, was kombinierbare Tische mit Umbauzeit bringen und wie sich Warteschlange und Reservierungen auswirken.

Lauffähig mit: streamlit run app.py
"""

import time
from dataclasses import replace

import pandas  # noqa: F401  (früh importiert, Vorsichtsmaßnahme gegen einen Importfehler beim Kaltstart der Cloud-App)
import streamlit as st

import rtm_algorithm as A
import rtm_constants as C
import rtm_reserve as R
from rtm_evaluation import (
    Settings,
    analyse,
    best_design,
    designs_of,
    exact_for,
    geduld_gain,
    geduld_regret,
    halte_table,
    load_results,
    mix_rows,
    nachbar_table,
    pool_gap_table,
    regret_matrix,
    reserve_studies,
    verdict_combine,
    verdict_form,
    verdict_mix,
    verdict_paradox,
    verdict_reserve,
)
from rtm_layout import dunkles_design, kopf_css
from rtm_presets import (
    bounds,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    sidebar_presets,
    sync_query_params,
)
from rtm_scenario import Params
from rtm_visualization import build_compare, build_floor, build_geduld, build_occupancy, build_regret, build_reserve

st.set_page_config(page_title="Restaurant-Tischmix – Sebastian Hanisch", layout="wide")

DATA = load_results()
ROWS = mix_rows(DATA)


@st.cache_data(show_spinner=False)
def _analysis(settings):
    return analyse(settings)


@st.cache_data(show_spinner=False)
def _snapshot(params, seed, minute):
    sim = A.Restaurant(params, seed * C.SUBSEED_STRIDE)
    sim.advance(C.WARMUP_MIN + minute)
    return sim.snapshot()


@st.cache_data(show_spinner=False)
def _reserve_live(cv, tol, evenings, seed):
    return [R.study(f, cv, tol, evenings, seed) for f in R.F_GRID]


def _show(verdict):
    kind, text = verdict
    {"success": st.success, "warning": st.warning, "info": st.info}[kind](text)


def _num(x, digits=2):
    return f"{x:.{digits}f}".replace(".", ",")


def _mix_name(design):
    a, b, c = design
    return f"{a} × 2er, {b} × 4er, {c} × 6er"


ASSUMPTIONS_MARKDOWN = """
| Annahme | Wer setzt an |
|---|---|
| Gruppen kommen als Poisson-Strom; Größen 2, 3, 4, 6 nach einer der vier Verteilungen (gesetzt, nicht aus Daten) | Regler, Modell |
| Verweildauer exponentiell mit dem Mittel 45 + 10 · Gruppengröße Minuten; gleicher Umsatz je Gast | Modell |
| Best-Fit setzt eine Gruppe an den kleinsten freien Tisch, der passt; passt keiner, an die kleinste freie Kombination zweier Tische (falls erlaubt) | Regler, Modell |
| Eine kombinierte Gruppe belegt beide Tische um die Umbauzeit länger (Zusammenstellen und Auseinanderrücken); die Minuten sind gesetzt, keine Quelle nennt Werte | Regler |
| Geduld konstant: eine Gruppe wartet höchstens so lange; wer nicht passt, lässt die nachfolgenden vorbei | Regler, Modell |
| Last = angebotene Gastminuten je Platzminute; bei Tischform stehen schon bei Last 1 Plätze an belegten Tischen leer | Regler |
| Grundriss: Raster mit fünf Spalten, Nachbarschaft nur oben, unten, links, rechts; keine Wege, keine Wände | Modell |
| Reservierungen: sieben Tische, 22 Anfragen je Abend zu Startzeiten im 30-Minuten-Raster, Dauer lognormal; der Preis w einer abgewiesenen Zusage und die Wartekosten c sind gesetzt | Regler |
| Keine Überbuchung, keine No-Shows, keine Gruppenverkleinerung, keine Stoßzeiten, kein leer gehaltener Tisch für eine Kombination | Nicht umgesetzt |
"""

# Fester Kopf: nur der Titel bleibt beim Scrollen oben (Stylesheet in rtm_layout.py).
st.html(kopf_css(dunkles_design()))
with st.container(key="kopf"):
    st.title("🍽️ Restaurant-Tischmix: Welche Tische passen zu den Gruppen?")
st.markdown(
    """
Ein **Restaurant ohne Reservierung** hat Tische für zwei, vier und sechs Personen, und die Gruppen kommen in unterschiedlicher Größe. Eine Gruppe wird an einen passenden Tisch gesetzt oder geht.
Die Demo fragt: Was kostet die **Tischform** gegenüber einem idealen Sitzplatz-Pool? Wie viele Gäste gehen verloren, wenn der **Tischmix** auf die falsche Gruppenverteilung ausgelegt ist? Was bringen
**kombinierbare Tische**, wenn das Zusammenstellen **Umbauzeit** kostet, und ändern **Warteschlange** und **Reservierungen** daran etwas?

Alle Annahmen (Gruppenverteilungen, Verweildauern, Umbauzeit, Geduld) sind Regler oder gesetzt, keine Messdaten. Weiter unten: der **Grundriss** eines Abends, drei **Kernfragen**, der Reiter
**Reservierung**, sechs **Experimente** mit vorgerechneten Messreihen und die Expander **🔧 Wie wir das erreichen – vollständiger Methodenvergleich**, **📐 Mathematische Formulierung** und **🚧 Wo die Annahmen enden**.
"""
)
st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    sidebar_presets()  # Schnellstart oben, das aktive Preset ist hervorgehoben
    st.header("🍽️ Restaurant")
    t2 = st.slider("Zweiertische", *bounds("t2_slider"), key="t2_slider", help="Wie viele Tische mit zwei Plätzen.")
    t4 = st.slider("Viertische", *bounds("t4_slider"), key="t4_slider", help="Wie viele Tische mit vier Plätzen.")
    t6 = st.slider("Sechsertische", *bounds("t6_slider"), key="t6_slider", help="Wie viele Tische mit sechs Plätzen.")
    seats = 2 * t2 + 4 * t4 + 6 * t6
    st.caption(f"{seats} Plätze an {t2 + t4 + t6} Tischen.")
    st.header("👥 Gäste")
    dist = st.selectbox("Gruppenverteilung", list(C.DISTRIBUTIONS), key="dist_select", format_func=lambda k: C.DIST_LABELS[k],
                        help="Anteile der Gruppengrößen 2, 3, 4 und 6 (gesetzt, nicht aus Daten).")
    rho = st.slider("Last", *bounds("rho_slider"), key="rho_slider", step=0.1, format="%.1f",
                    help="Angebotene Gastminuten je Platzminute. Bei Tischform stehen schon bei 1,0 Plätze an belegten Tischen leer (Gastbelegung unter Tischbelegung).")
    st.header("⚙️ Regeln")
    rule = st.selectbox("Tischwahl", list(C.RULES), key="rule_select", format_func=lambda k: C.RULE_LABELS[k], help="Best-Fit nimmt den kleinsten passenden freien Tisch, Worst-Fit den größten.")
    combine = st.selectbox("Kombination zweier Tische", list(C.COMBINE_MODES), key="combine_select",
                           help="aus: nur Einzeltische. nur 2er: zwei freie Zweiertische. beliebig: zwei beliebige freie Tische. Nachbarn: zwei freie Tische, die im Grundriss nebeneinander stehen.")
    extra = st.slider("Umbauzeit je kombinierter Gruppe (Minuten)", *bounds("extra_slider"), key="extra_slider", step=5.0, format="%.0f",
                      help="Beide Tische sind so viele Minuten länger belegt (Zusammenstellen und Auseinanderrücken); gilt nur, wenn Kombination erlaubt ist. Gesetzt, nicht gemessen.")
    patience = st.slider("Geduld der Gäste (Minuten)", *bounds("patience_slider"), key="patience_slider", step=5.0, format="%.0f",
                         help="0: Gäste gehen sofort, wenn kein Tisch passt. Sonst warten sie so lange auf einen passenden Tisch.")
    arrangement = st.selectbox("Anordnung im Grundriss", list(C.ARRANGEMENTS), key="arrangement_select",
                               help="sortiert: kleine Tische zuerst im Raster. verteilt: größere Tische gleichmäßig über das Raster. Wirkt nur auf die Kombination „Nachbarn“ und das Bild.")
    st.header("🎲 Zufall")
    seed = st.number_input("Zufalls-Seed", *bounds("seed_input"), key="seed_input", help="Gleicher Seed, gleicher Lauf (eigener Zufallsgenerator).")
    st.button("🎲 Neuen Zufalls-Seed würfeln", on_click=randomize_seed)

params = Params(t2=t2, t4=t4, t6=t6, dist=dist, rho=rho, combine=combine, extra=extra, patience=patience, rule=rule, arrangement=arrangement)
settings = Settings(params=params, seed=int(seed))
sync_query_params({"t2_slider": t2, "t4_slider": t4, "t6_slider": t6, "dist_select": dist, "rho_slider": rho, "rule_select": rule, "combine_select": combine,
                   "extra_slider": extra, "patience_slider": patience, "arrangement_select": arrangement, "seed_input": int(seed)})

t0 = time.perf_counter()
with st.spinner("Das Restaurant wird durchgespielt …"):
    a = _analysis(settings)
elapsed = time.perf_counter() - t0
s = a.study

# ---------------------------------------------------------------------------------------------- Ergebnis und Grundriss
st.markdown("## Ergebnis des eingestellten Restaurants")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Gäste je Stunde", _num(s.guests_per_hour), help=f"Mittel über {s.runs} Läufe zu je {s.hours:.0f} Stunden, Standardfehler {_num(s.guests_se)}.")
c2.metric("Idealer Sitzplatz-Pool", _num(a.pool), help="Jede Gruppe belegt genau ihre Gästezahl an Plätzen (Kaufman-Roberts, exakt): Vergleichsgröße ohne Tischform; eine Obergrenze nur, wenn Gäste sofort gehen (Geduld 0).")
c3.metric("Gastbelegung", f"{100 * s.guest_occupancy:.0f} %".replace(".", ","), help="Mittlere Zahl sitzender Gäste durch Plätze.")
c4.metric("Tischbelegung", f"{100 * s.seat_occupancy:.0f} %".replace(".", ","), help="Mittlere Zahl der Plätze an belegten Tischen durch Plätze.")
c5.metric("Kombinierte Gruppen", f"{100 * s.combined_share:.0f} %".replace(".", ","), help="Anteil der gesetzten Gruppen, die zwei Tische belegen.")
st.caption(f"Rechenzeit der Live-Rechnung: {elapsed:.1f} s (Läufe mit Zufalls-Seeds {int(seed)} · 1000 + k, wiederholte Einstellungen kommen aus dem Zwischenspeicher).")

st.markdown("**Ein Abend im Grundriss**")
minute = st.slider("Zeitpunkt des Abends (Minuten nach der Einschwingzeit)", 0, 600, 150, step=15, key="floor_minute",
                   help="Zeigt, welche Tische zu diesem Zeitpunkt besetzt sind (ein Lauf mit dem eingestellten Zufalls-Seed). Hellgrün: frei, grün: besetzt, blau: kombiniert.")
st.plotly_chart(build_floor(_snapshot(params, int(seed), minute), params.tables), width="stretch", config={"displayModeBar": False})

# ---------------------------------------------------------------------------------------------- Kernfrage 1
st.markdown("## Kernfrage 1: Was kostet die Tischform?")
_show(verdict_form(a))
_show(verdict_paradox(a))
col_a, col_b = st.columns(2)
with col_a:
    st.plotly_chart(build_compare([("Restaurant", s.guests_per_hour, s.guests_se, C.COLOR_GOOD), ("Idealer Pool", a.pool, 0.0, C.COLOR_GRAY)]), width="stretch", config={"displayModeBar": False})
with col_b:
    st.plotly_chart(build_occupancy(s), width="stretch", config={"displayModeBar": False})

# ---------------------------------------------------------------------------------------------- Kernfrage 2
st.markdown("## Kernfrage 2: Was kostet ein falsch geschätzter Tischmix?")
st.caption("Exakt gerechnet (Markov-Kette) und vorgerechnet für 24 Plätze, Last 1,0, Best-Fit, keine Warteschlange, vier Gruppenverteilungen. Der Mix wird hier gewählt, nicht aus der Seitenleiste übernommen.")
designs = designs_of(ROWS)
default_mix = (t2, t4, t6) if (t2, t4, t6) in designs else (4, 4, 0)
mix = st.selectbox("Tischmix (24 Plätze)", designs, index=designs.index(default_mix), key="mix_choice", format_func=_mix_name)
mix_extra = st.radio("Umbauzeit der Kombination (Minuten)", (0.0, 10.0, 20.0), index=1, horizontal=True, key="mix_extra", format_func=lambda x: f"{x:.0f}")
key_c = {0.0: "alle0", 10.0: "alle10", 20.0: "alle20"}[mix_extra]
m_ded, m_comb = regret_matrix(ROWS, "none"), regret_matrix(ROWS, key_c)
d1, d2 = st.columns(2)
with d1:
    st.markdown("**Ohne Kombination**")
    st.plotly_chart(build_regret(m_ded, list(C.DISTRIBUTIONS)), width="stretch", config={"displayModeBar": False})
    _show(verdict_mix(ROWS, mix, "none"))
with d2:
    st.markdown(f"**Mit Kombination ({mix_extra:.0f} Minuten Umbau)**")
    st.plotly_chart(build_regret(m_comb, list(C.DISTRIBUTIONS)), width="stretch", config={"displayModeBar": False})
    _show(verdict_mix(ROWS, mix, key_c))

# ---------------------------------------------------------------------------------------------- Kernfrage 3
st.markdown("## Kernfrage 3: Was bringt Kombinierbarkeit, und was kosten Umbauzeit und Nachbarschaft?")
v = a.variants
st.plotly_chart(build_compare([("ohne Kombination", v["aus"].guests_per_hour, v["aus"].guests_se, C.COLOR_GRAY),
                               ("beliebige Paare, ohne Umbauzeit", v["beliebig0"].guests_per_hour, v["beliebig0"].guests_se, C.COLOR_NEUTRAL),
                               (f"beliebige Paare, {extra:.0f} min Umbau", v["beliebig"].guests_per_hour, v["beliebig"].guests_se, C.COLOR_GOOD),
                               (f"nur Nachbarn, {extra:.0f} min Umbau", v["nachbarn"].guests_per_hour, v["nachbarn"].guests_se, C.COLOR_BAD)]),
                width="stretch", config={"displayModeBar": False})
_show(verdict_combine(a))

# ---------------------------------------------------------------------------------------------- Reservierung
st.markdown("## Reservierung: Wie lang soll ein Tisch eingeplant werden?")
st.markdown(
    "Sieben Tische (3 × 2er, 3 × 4er, 1 × 6er), 22 Reservierungsanfragen je Abend zu Startzeiten im 30-Minuten-Raster. Eine Anfrage wird angenommen, wenn ein Tisch in der **geplanten** Dauer "
    "(Planungsfaktor × Mittel) frei ist; die **wirkliche** Dauer streut. Überzieht ein Gast, wartet die Folgegruppe, und nach der Wartegrenze geht sie."
)
r1, r2, r3, r4 = st.columns(4)
cv = r1.select_slider("Streuung der Dauer (Variationskoeffizient)", options=list(R.CV_CHOICES), value=0.5, key="res_cv", format_func=lambda x: _num(x))
tol = r2.radio("Wartegrenze (Minuten)", list(R.TOL_CHOICES), index=0, horizontal=True, key="res_tol", format_func=lambda x: f"{x:.0f}")
price = r3.slider("Preis einer abgewiesenen Zusage (Gäste)", 0.0, 4.0, 2.0, step=0.5, key="res_w", help="Was es kostet, wenn eine zugesagte Gruppe an der Tür abgewiesen wird (Ruf, Verärgerung), in Gästeeinheiten. Gesetzt, nicht gemessen.")
wcost = r4.slider("Wert einer Wartestunde (Gäste)", 0.0, 1.0, 0.5, step=0.25, key="res_c", help="Was eine Gast-Stunde Warten kostet, in Gästeeinheiten. Gesetzt, nicht gemessen.")
with st.spinner("Die Abende werden durchgespielt …"):
    live = _reserve_live(cv, tol, 1000, int(seed))
st.plotly_chart(build_reserve(live, price, wcost), width="stretch", config={"displayModeBar": False})
_show(verdict_reserve(live, price, wcost))
st.caption("Live: 1000 Abende je Planungsfaktor (Zufalls-Seed der Sitzung); die Tabelle unten und die README nutzen 3000 Abende.")
pre_rows = []
for w_, c_ in ((1.0, 0.0), (2.0, 0.0), (4.0, 0.0), (1.0, 0.5), (2.0, 0.5), (4.0, 0.5)):
    pre_rows.append({"Preis w": _num(w_, 0), "Wartewert c": _num(c_, 1), "bestes f (Streuung 0,25)": _num(R.best_f(reserve_studies(DATA, 0.25, tol), w_, c_)),
                     "bestes f (Streuung 0,5)": _num(R.best_f(reserve_studies(DATA, 0.5, tol), w_, c_)), "bestes f (Streuung 0,75)": _num(R.best_f(reserve_studies(DATA, 0.75, tol), w_, c_))})
st.markdown(f"**Bester Planungsfaktor je Preis (vorgerechnet, 3000 Abende, Wartegrenze {tol:.0f} Minuten)**")
st.dataframe(pre_rows, hide_index=True, width="stretch")

# ---------------------------------------------------------------------------------------------- Experimente
st.markdown("## Experimente (vorgerechnet)")
st.caption("Exakte Ketten und Simulationen mit festen Zufalls-Seeds (`tools/make_results.py`); nichts davon rechnet beim Öffnen der Seite.")

st.subheader("🔬 1 · Der Tischmix ist eine Wette auf die Gruppenverteilung")
pool_rows = pool_gap_table(DATA)
st.dataframe([{"Verteilung": C.DIST_LABELS[r["dist"]], "bester Mix ohne Kombination": _mix_name(r["dedicated"]), "Gäste je Stunde": _num(r["dedicated_gph"], 3),
               "bester Mix mit Kombination (10 min)": _mix_name(r["combinable"]), "Gäste je Stunde (komb.)": _num(r["combinable_gph"], 3)} for r in pool_rows], hide_index=True, width="stretch")
st.caption("Ohne Kombination hat jede Verteilung einen anderen besten Mix (mit Kombination teilen sich „große Gruppen“ und „gemischt“ denselben); deshalb ist die Wahl ohne Kenntnis der künftigen Gruppen eine Wette (Kernfrage 2).")

st.subheader("🔬 2 · Umbauzeit: der Zuwachs schrumpft, die Versicherung bleibt")
halte = halte_table(ROWS)
st.dataframe([{"Umbauzeit (min)": f"{h['extra']:.0f}", **{f"Zuwachs {C.DIST_SHORT[d]}": _num(h["gain"][d], 1) + " %" for d in C.DISTRIBUTIONS}, "größtes Bedauern bei falscher Annahme": _num(h["worst"], 1) + " %",
               "robuster Mix": _mix_name(h["robust"]), "dessen größtes Bedauern": _num(h["robust_loss"], 1) + " %", "Fälle, in denen Kombination schadet": f"{h['harm']} von {h['cells']}"} for h in halte],
             hide_index=True, width="stretch")
st.caption("Zuwachs = bester kombinierbarer Mix gegen besten Mix ohne Kombination, je Verteilung. Bedauern = so viel mehr Gäste bedient der beste Mix für die eingetretene Verteilung; es gilt für den Mix, der für die jeweilige andere Verteilung am besten ist.")

st.subheader("🔬 3 · Warteschlange: mehr Gäste, gleiche Rangfolge")
gcols = st.columns(2)
with gcols[0]:
    st.plotly_chart(build_geduld(DATA["geduld"]), width="stretch", config={"displayModeBar": False})
with gcols[1]:
    st.dataframe([{"Geduld": f"{p:.0f} min", "größtes Bedauern falsche Annahme, ohne Kombination": _num(geduld_regret(DATA["geduld"], p, "aus"), 1) + " %",
                   "mit Kombination (10 min Umbau)": _num(geduld_regret(DATA["geduld"], p, "beliebig"), 1) + " %"} for p in (0.0, 15.0, 30.0)], hide_index=True, width="stretch")
    st.caption("Drei Bestmixe (je einer für Paare, kleine und große Gruppen) gegeneinander; Simulation, 12 Zufalls-Seeds, 3000 Stunden je Zelle.")

st.subheader("🔬 4 · Nachbarschaft kostet wenig")
st.dataframe([{"Verteilung": C.DIST_SHORT[r["dist"]], "Anordnung": r["arrangement"], "ohne Kombination": _num(r["aus"], 3), "beliebige Paare, 0 min": _num(r["beliebig0"], 3),
               "Nachbarn, 0 min": _num(r["nachbarn0"], 3), "beliebige Paare, 10 min": _num(r["beliebig10"], 3), "Nachbarn, 10 min": _num(r["nachbarn10"], 3)} for r in nachbar_table(DATA["nachbar"])],
             hide_index=True, width="stretch")
st.caption("Acht Zweier- und zwei Viertische im Raster mit fünf Spalten; Gäste je Stunde, Simulation, 12 Zufalls-Seeds, 3000 Stunden je Zelle.")

st.subheader("🔬 5 · Tischwahl und Restaurantgröße")
ann = DATA["annahme"]
st.dataframe([{"Fall": "kleines Restaurant (2 × 2er, 2 × 4er, 1 × 6er), Paare, Best-Fit", "Gäste je Stunde": _num(ann["S_best"]["gph"], 3), "Gastbelegung": _num(100 * ann["S_best"]["guest_occ"], 1) + " %", "Tischbelegung": _num(100 * ann["S_best"]["seat_occ"], 1) + " %"},
              {"Fall": "dasselbe, Worst-Fit", "Gäste je Stunde": _num(ann["S_worst"]["gph"], 3), "Gastbelegung": _num(100 * ann["S_worst"]["guest_occ"], 1) + " %", "Tischbelegung": _num(100 * ann["S_worst"]["seat_occ"], 1) + " %"}],
             hide_index=True, width="stretch")
if ann["L_alle"]["gph"]:
    gain_s = 100 * (ann["S_alle"]["gph"] / ann["S_best"]["gph"] - 1)
    gain_l = 100 * (ann["L_alle"]["gph"] / ann["L_none"]["gph"] - 1)
    st.caption(f"Worst-Fit hat mehr belegte Tischplätze und weniger Gäste. Kombination beliebiger Paare (ohne Umbauzeit) bringt dem kleinen Restaurant {_num(gain_s, 1)} %, dem doppelt so großen (4 × 2er, 4 × 4er, 2 × 6er) {_num(gain_l, 1)} %.")

st.subheader("🔬 6 · Die Pool-Schranke")
st.dataframe([{"Verteilung": C.DIST_LABELS[r["dist"]], "Pool (24 Plätze)": _num(r["pool"], 3), "bester Mix ohne Kombination": _num(r["dedicated_gph"], 3), "Abstand": _num(r["gap_dedicated"], 1) + " %",
               "bester Mix mit Kombination (10 min)": _num(r["combinable_gph"], 3), "Abstand ": _num(r["gap_combinable"], 1) + " %"} for r in pool_rows], hide_index=True, width="stretch")
st.caption("Pool = ideale Platzvergabe ohne Tischform (exakt). Der Abstand ist der Preis der Tischform bei bestem Mix.")

# ---------------------------------------------------------------------------------------------- Expander
with st.expander("🔧 Wie wir das erreichen – vollständiger Methodenvergleich"):
    tab_methods, tab_exact = st.tabs(["📊 Verfahren", "🧮 Exakt (Markov-Kette)"])
    with tab_methods:
        st.markdown(
            """
| Verfahren | Was es rechnet | Wofür in der Demo |
|---|---|---|
| **Ereignissimulation** | Poisson-Ankünfte, Tischwahl, Kombination, Warteschlange, Grundriss | Live-Rechnung, Grundriss, Nachbarschaft, Geduld |
| **Exakte Markov-Kette** | stationäre Verteilung über Besetzungszustände (Tischarten, keine Nachbarschaft, Geduld 0) | Messreihe der Mixe, Gegenprobe der Simulation |
| **Kaufman-Roberts** | idealer Sitzplatz-Pool (jede Gruppe belegt ihre Gästezahl an Plätzen) | Pool-Schranke |
| **Reservierungsabend** | Annahme nach geplanter Dauer, wirkliche Dauer lognormal | Reiter Reservierung |

Alle Zufallsfolgen kommen aus einem eigenen SplitMix64; die Live-Rechnung mittelt """ + f"{C.LIVE_RUNS} Läufe zu je {C.LIVE_HOURS} Stunden" + """ (nach 5 Stunden Einschwingzeit), die Messreihen 12 Zufalls-Seeds (die Reservierungsabende: 3000 Abende mit dem Zufalls-Seed 35). Die exakte Kette gibt einer kombinierten Gruppe die Dauer Exp(Mittel + Umbauzeit), die Simulation Exp(Mittel) + Umbauzeit: gleiches Mittel, andere Verteilung (gemessener Unterschied höchstens 0,24 %).
"""
        )
    with tab_exact:
        st.markdown("Rechnet die Kette für die **eingestellten** Tische, Verteilung, Last und Regeln exakt und stellt sie der Simulation gegenüber (gilt für Geduld 0 und Kombination aus, nur 2er oder beliebig).")
        if st.button("Exakt rechnen", key="exact_run"):
            t1 = time.perf_counter()
            res, why = exact_for(params)
            st.session_state["exact_result"] = (params, res, why, time.perf_counter() - t1)
        stored = st.session_state.get("exact_result")
        if stored and stored[0] == params:
            _p, res, why, secs = stored
            if res is None:
                st.info(why)
            else:
                diff = s.guests_per_hour - res.guests_per_hour
                st.metric("Exakte Gäste je Stunde", _num(res.guests_per_hour, 3), delta=f"{_num(diff, 3)} Simulation minus exakt", delta_color="off")
                st.caption(f"{res.states} Zustände, {secs:.1f} s. Die Simulation streut um den exakten Wert (Standardfehler {_num(s.guests_se, 3)}).")
        elif stored:
            st.caption("Die Einstellungen haben sich geändert: erneut „Exakt rechnen“.")

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Gegeben:** Tische mit $c_i \in \{2, 4, 6\}$ Plätzen, Gruppengrößen $s \in \{2, 3, 4, 6\}$ mit Anteilen $p_s$, Last $\rho$, mittlere Verweildauer $m_s = 45 + 10 s$ Minuten, Umbauzeit $\delta$.
**Ankünfte:** Gruppen kommen als Poisson-Strom mit der Rate $\lambda$, gewählt so, dass die angebotenen Gastminuten gleich $\rho$ mal Platzminuten sind:

$$\lambda = \frac{\rho \cdot \sum_i c_i}{\sum_s p_s \, s \, m_s}.$$

**Tischwahl:** Best-Fit setzt eine Gruppe an den kleinsten freien Tisch mit $c_i \ge s$; sonst (falls erlaubt) an das freie Paar mit der kleinsten Platzsumme $c_i + c_j \ge s$; die Gruppe belegt beide Tische $m_s + \delta$ Minuten.
Ohne Warteschlange geht eine Gruppe, die nirgends passt. Gesucht ist die Zahl der Gäste je Stunde im Gleichgewicht:

$$G = 60 \, \lambda \sum_s p_s \, s \, (1 - B_s).$$

Dabei ist $B_s$ die Wahrscheinlichkeit, dass eine Gruppe der Größe $s$ nicht gesetzt wird. Die exakte Kette bestimmt $B_s$ aus der stationären Verteilung der Besetzungszustände; die Simulation schätzt $G$ aus Läufen.
**Idealer Sitzplatz-Pool:** Ohne Tischform belegt eine Gruppe genau $s$ Plätze von $C$. Mit den Lasten $a_s = \lambda p_s m_s$ gilt die Kaufman-Roberts-Rekursion für die Wahrscheinlichkeit $q(j)$, dass $j$ Plätze belegt sind:

$$j \, q(j) = \sum_s a_s \, s \, q(j - s).$$

| Symbol | Bedeutung |
|---|---|
| $c_i, C$ | Plätze von Tisch $i$, Plätze insgesamt |
| $s, p_s, m_s$ | Gruppengröße, ihr Anteil, mittlere Verweildauer |
| $\rho, \lambda$ | Last, Ankunftsrate der Gruppen je Minute |
| $\delta$ | Umbauzeit einer kombinierten Gruppe |
| $B_s, G$ | Sperrwahrscheinlichkeit der Größe $s$, Gäste je Stunde |
| $q(j), a_s$ | Wahrscheinlichkeit von $j$ belegten Plätzen im Pool, angebotene Last der Größe $s$ |

**Bedauern:** Wird der Mix für die Verteilung $d$ gewählt und tritt $d'$ ein, ist das Bedauern in Prozent
$100 \, (G^{*}_{d'} / G_{d'}(\text{Mix}) - 1)$ mit $G^{*}_{d'}$ als Gästen je Stunde des besten Mixes für $d'$ (so viel mehr Gäste bedient der beste Mix); der Anteil der möglichen Gäste, den der gewählte Mix verliert, ist $100 \, r / (100 + r)$ für das Bedauern $r$.
**Reservierung:** Nettowert je Abend = bediente Gäste $- w \cdot$ abgewiesene Zusagen $- c \cdot$ Gästestunden Wartezeit.
"""
    )

with st.expander("🚧 Wo die Annahmen enden"):
    st.markdown(
        """
- Gruppenverteilungen, Verweildauern, Umbauzeit, Geduld, Preis einer abgewiesenen Zusage und Wartewert sind **gesetzte Annahmen**, nicht aus Betriebsdaten geschätzt. Für Umbauzeiten beim Zusammenstellen von Tischen nannte keine gesichtete Quelle Minuten.
- Das Modell kennt **keine Überbuchung**, keine No-Shows, keine Stoßzeiten (die Last ist konstant), keine Gruppenverkleinerung und **keinen leer gehaltenen Tisch**, der auf einen Nachbartisch wartet; die Umbauzeit ist nur eine Zusatzzeit.
- Der Grundriss kennt nur ein Raster mit fünf Spalten und direkte Nachbarn, keine Wege und keine Küche.
- Die Reservierungsrechnung nutzt sieben Tische und 22 Anfragen und ein 30-Minuten-Raster; „beste Planlänge“ hängt am gesetzten Preis einer abgewiesenen Zusage.
- Die Live-Rechnung nutzt wenige Läufe; die Messreihen nutzen mehr Läufe und feste Zufalls-Seeds. Dass der beste Mix zum Gruppenmix passt, ist aus der Restaurantliteratur bekannt; zur Robustheit gegen eine falsch geschätzte Verteilung wurde nichts gefunden.
"""
    )
    st.markdown("**Annahmen im Überblick**")
    st.markdown(ASSUMPTIONS_MARKDOWN)

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zum Thema: [Sitzplätze optimieren](https://sebastianhanisch.net/sitzplaetze-optimieren.html)."
)
