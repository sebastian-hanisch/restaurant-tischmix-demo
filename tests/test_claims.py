"""Jede Zahl der README-Tabelle „Befunde“ wird hier gezählt (DEMO-PLAYBOOK 11a): über die ganze Messdatei `data/rtm_results.json`;
vier Zeilen rechnen die Tests außerdem neu (exakte Kette, Simulation, Reservierungsabende) und prüfen so, dass die Datei zum Code passt."""

import pytest

import rtm_algorithm as A
import rtm_constants as C
import rtm_evaluation as ev
import rtm_exact as E
import rtm_reserve as R
from rtm_scenario import Params, mean_dwell

DATA = ev.load_results()
ROWS = ev.mix_rows(DATA)
DISTS = list(C.DISTRIBUTIONS)


def test_messreihe_hat_die_erwartete_form():
    m = DATA["meta"]
    assert m["sweep_seeds"] == list(C.SWEEP_SEEDS) and len(C.SWEEP_SEEDS) == 12 and m["hours"] == 3000 and m["warmup_min"] == 300.0 and m["mix_seats"] == C.MIX_SEATS == 24
    assert len(ROWS) == 76 and len(ev.designs_of(ROWS)) == 19 and {r["dist"] for r in ROWS} == set(DISTS)
    assert all(2 * a + 4 * b + 6 * c == 24 for a, b, c in ev.designs_of(ROWS))


def test_tischform_kostet_gegen_den_pool():
    """Befund 1: Pool-Schranke und beste Mixe (exakt, 24 Plätze, Last 1,0)."""
    rows = {r["dist"]: r for r in ev.pool_gap_table(DATA)}
    assert {d: round(rows[d]["pool"], 3) for d in DISTS} == {"paare": 12.861, "klein": 14.600, "gross": 10.953, "gemischt": 11.758}
    assert {d: (rows[d]["dedicated"], round(rows[d]["dedicated_gph"], 3)) for d in DISTS} == {"paare": ((4, 4, 0), 11.181), "klein": ((6, 3, 0), 12.935), "gross": ((0, 3, 2), 9.760),
                                                                                          "gemischt": ((1, 4, 1), 10.149)}
    assert {d: round(rows[d]["gap_dedicated"], 1) for d in DISTS} == {"paare": 13.1, "klein": 11.4, "gross": 10.9, "gemischt": 13.7}
    assert {d: (rows[d]["combinable"], round(rows[d]["combinable_gph"], 3)) for d in DISTS} == {"paare": ((6, 3, 0), 12.005), "klein": ((10, 1, 0), 13.655), "gross": ((4, 4, 0), 10.275),
                                                                                             "gemischt": ((4, 4, 0), 10.948)}
    assert {d: round(rows[d]["gap_combinable"], 1) for d in DISTS} == {"paare": 6.7, "klein": 6.5, "gross": 6.2, "gemischt": 6.9}
    assert all(r["gap_dedicated"] > 10.0 for r in rows.values()) and all(r["gap_combinable"] < 7.0 for r in rows.values())


def test_pool_optimum_und_kaufman_roberts_stimmen_bis_auf_zwei_tausendstel_ueberein():
    assert all(-1e-6 <= DATA["pool"][d]["opt"] - DATA["pool"][d]["kr"] <= 0.002 for d in DISTS)
    assert round(DATA["pool"]["klein"]["opt"], 3) == 14.600 and round(DATA["pool"]["klein"]["kr"], 3) == 14.599


def test_falsch_geschaetzter_mix_ohne_kombination():
    """Befund 2: ohne Kombination verliert ein falsch ausgelegter Mix bis 54,3 %, der robusteste Mix höchstens 12,5 %."""
    m = ev.regret_matrix(ROWS, "none")
    assert m["best"] == {"paare": (4, 4, 0), "klein": (6, 3, 0), "gross": (0, 3, 2), "gemischt": (1, 4, 1)}
    assert (round(m["worst"][0], 1), m["worst"][1], m["worst"][2]) == (54.3, "klein", "gross")
    assert round(m["loss"][("paare", "gross")], 1) == 32.0 and round(m["loss"][("gross", "klein")], 1) == 42.8
    assert m["robust"] == (3, 3, 1) and round(m["robust_loss"], 1) == 12.5
    assert sum(1 for v in m["loss"].values() if v > 10.0) == 7            # 7 der 12 Fehlannahmen kosten mehr als 10 %


@pytest.mark.parametrize("key,worst,robust,robust_loss", [("alle0", 15.8, (6, 3, 0), 4.8), ("alle10", 15.9, (6, 3, 0), 3.9), ("alle20", 16.2, (6, 3, 0), 3.0)])
def test_falsch_geschaetzter_mix_mit_kombination(key, worst, robust, robust_loss):
    m = ev.regret_matrix(ROWS, key)
    assert round(m["worst"][0], 1) == worst and (m["worst"][1], m["worst"][2]) == ("klein", "gross")
    assert m["robust"] == robust and round(m["robust_loss"], 1) == robust_loss


def test_vierte_verteilung_aendert_nichts_am_befund():
    """Ohne die Verteilung „gemischt“ (drei Verteilungen) bleiben der größte Verlust, der robuste Mix und sein Bedauern gleich."""
    three = [r for r in ROWS if r["dist"] != "gemischt"]
    for key, worst in (("none", 54.3), ("alle0", 15.8), ("alle10", 15.9), ("alle20", 16.2)):
        losses = []
        best = {d: ev.best_design(three, d, key) for d in ("paare", "klein", "gross")}
        for a in best:
            for w in best:
                losses.append(ev.regret_of(three, best[a], w, key))
        assert round(max(losses), 1) == worst


def test_haltekosten_zuwachs_schrumpft_versicherung_bleibt():
    """Befund 3: Umbauzeit 0 / 10 / 20 Minuten."""
    h = {x["extra"]: x for x in ev.halte_table(ROWS)}
    assert {e: {d: round(g, 1) for d, g in h[e]["gain"].items()} for e in h} == {
        0.0: {"paare": 9.8, "klein": 7.9, "gross": 8.4, "gemischt": 10.5},
        10.0: {"paare": 7.4, "klein": 5.6, "gross": 5.3, "gemischt": 7.9},
        20.0: {"paare": 5.1, "klein": 3.4, "gross": 2.3, "gemischt": 5.4}}
    assert [(h[e]["harm"], h[e]["cells"]) for e in h] == [(6, 76), (15, 76), (21, 76)]
    assert [round(h[e]["robust_loss"], 1) for e in h] == [4.8, 3.9, 3.0] and all(h[e]["robust"] == (6, 3, 0) for e in h)
    assert [round(h[e]["worst"], 1) for e in h] == [15.8, 15.9, 16.2]
    assert all(h[e]["robust_loss"] < 5.0 < 12.5 for e in h)


def test_warteschlange_mehr_gaeste_gleiche_rangfolge():
    """Befund 4: Geduld 0 / 15 / 30 Minuten, drei Bestmixe gegeneinander (Simulation, 12 Zufalls-Seeds, 3000 Stunden)."""
    g = DATA["geduld"]
    assert [round(ev.geduld_regret(g, p, "aus"), 1) for p in (0.0, 15.0, 30.0)] == [54.2, 55.6, 56.1]
    assert [round(ev.geduld_regret(g, p, "beliebig"), 1) for p in (0.0, 15.0, 30.0)] == [45.1, 42.4, 44.4]
    assert [round(ev.geduld_gain(g, p, "aus"), 3) for p in (0.0, 15.0, 30.0)] == [11.295, 12.113, 12.664]
    assert [round(ev.geduld_gain(g, p, "beliebig"), 3) for p in (0.0, 15.0, 30.0)] == [11.588, 12.495, 13.101]
    assert round(100 * (ev.geduld_gain(g, 15.0, "aus") / ev.geduld_gain(g, 0.0, "aus") - 1), 1) == 7.2
    assert round(100 * (ev.geduld_gain(g, 30.0, "aus") / ev.geduld_gain(g, 0.0, "aus") - 1), 1) == 12.1
    assert max(r["se"] for r in g) < 0.04 and len(g) == 54


def test_nachbarschaft_kostet_wenig():
    """Befund 5: nur Nachbartische gegen beliebige Paare (acht 2er, zwei 4er im Raster mit fünf Spalten, Simulation)."""
    rows = ev.nachbar_table(DATA["nachbar"])
    losses = [100 * (1 - r[f"nachbarn{e}"] / r[f"beliebig{e}"]) for r in rows for e in (0, 10)]
    assert len(losses) == 12 and round(min(losses), 1) == 0.3 and round(max(losses), 1) == 2.8
    for dist in ("paare", "klein", "gross"):
        a, b = [r for r in rows if r["dist"] == dist]
        assert max(abs(a["nachbarn0"] - b["nachbarn0"]), abs(a["nachbarn10"] - b["nachbarn10"])) < 0.1     # die Anordnung der Tische ändert höchstens 0,1 Gäste je Stunde
    assert max(r["se"] for r in DATA["nachbar"]) < 0.03


def test_tischwahl_best_fit_gegen_worst_fit_und_restaurantgroesse():
    """Befund 6 (exakt): Best-Fit 7,807 gegen Worst-Fit 6,987 im kleinen Restaurant; Kombination +1,7 % gegen +0,9 % beim doppelt so großen."""
    a = DATA["annahme"]
    assert round(a["S_best"]["gph"], 3) == 7.807 and round(a["S_worst"]["gph"], 3) == 6.987
    assert round(100 * (1 - a["S_worst"]["gph"] / a["S_best"]["gph"]), 1) == 10.5
    assert (round(100 * a["S_best"]["guest_occ"], 1), round(100 * a["S_best"]["seat_occ"], 1)) == (56.1, 68.9)
    assert (round(100 * a["S_worst"]["guest_occ"], 1), round(100 * a["S_worst"]["seat_occ"], 1)) == (48.7, 70.2)
    assert a["S_worst"]["seat_occ"] > a["S_best"]["seat_occ"] and a["S_worst"]["guest_occ"] < a["S_best"]["guest_occ"]
    assert round(a["S_alle"]["gph"], 3) == 7.938 and round(a["L_none"]["gph"], 3) == 17.632 and round(a["L_alle"]["gph"], 3) == 17.796
    assert round(100 * (a["S_alle"]["gph"] / a["S_best"]["gph"] - 1), 1) == 1.7 and round(100 * (a["L_alle"]["gph"] / a["L_none"]["gph"] - 1), 1) == 0.9


def test_reservierung_bester_planungsfaktor_haengt_am_preis():
    """Befund 7: Nettowert = bedient − w · abgewiesene Zusagen − c · Gästestunden Wartezeit; 3000 Abende, F-Raster 0,5 bis 1,5."""
    table = {}
    for tol in (15.0, 30.0):
        for cv in (0.25, 0.5, 0.75):
            st = ev.reserve_studies(DATA, cv, tol)
            table[(tol, cv)] = [R.best_f(st, w, 0.0) for w in (0.0, 1.0, 2.0, 4.0)]
    assert table == {(15.0, 0.25): [0.5, 0.85, 1.0, 1.15], (15.0, 0.5): [0.5, 0.85, 1.15, 1.3], (15.0, 0.75): [0.5, 0.85, 1.15, 1.5],
                     (30.0, 0.25): [0.5, 0.85, 0.85, 1.0], (30.0, 0.5): [0.5, 0.85, 0.85, 1.15], (30.0, 0.75): [0.5, 0.85, 1.0, 1.3]}
    assert all(row[0] == 0.5 for row in table.values())                                   # ohne Preis (w = 0) liegt der beste Faktor am Rand
    assert all(0.5 < row[1] < 1.5 for row in table.values()) and all(row == sorted(row) for row in table.values())


def test_reservierung_plateau_bei_preis_zwei():
    """Bei w = 2, Streuung 0,5, Wartegrenze 15 Minuten liegen die Nettowerte der Faktoren 1,0 / 1,15 / 1,3 innerhalb von 0,25 Gästen je Abend."""
    st = {s.f: s for s in ev.reserve_studies(DATA, 0.5, 15.0)}
    nets = [st[f].net(2.0, 0.0) for f in (1.0, 1.15, 1.3)]
    assert max(nets) - min(nets) < 0.25 and round(st[0.5].net(2.0, 0.0), 1) == 28.4 and round(max(nets), 1) == 38.3


def test_reservierung_bediente_gaeste_und_zusagen():
    st = {s.f: s for s in ev.reserve_studies(DATA, 0.5, 15.0)}
    assert (round(st[0.5].served, 1), round(st[1.5].served, 1)) == (49.3, 36.7)
    assert (round(st[0.5].lost, 1), round(st[1.5].lost, 1)) == (10.4, 0.6)
    assert max(r["served_se"] for r in DATA["reserve"]) < 0.12 and len(DATA["reserve"]) == 48


def test_messdatei_passt_zum_code_exakte_zeile_neu_gerechnet():
    p = Params(t2=6, t4=3, t6=0, dist="klein")
    rate = p.rate
    row = next(r for r in ROWS if r["dist"] == "klein" and tuple(r["design"]) == (6, 3, 0))
    counts = {2: 6, 4: 3, 6: 0}
    assert E.exact_chain(counts, p.probs, rate, "none").guests_per_hour == pytest.approx(row["none"], rel=1e-12)
    assert E.exact_chain(counts, p.probs, rate, "alle", 10.0).guests_per_hour == pytest.approx(row["alle10"], rel=1e-12)


def test_messdatei_passt_zum_code_simulationszeile_neu_gerechnet():
    p = Params(t2=4, t4=4, t6=0, dist="paare", combine="beliebig", extra=10.0, patience=15.0)
    cell = next(r for r in DATA["geduld"] if r["assumed"] == "paare" and r["dist"] == "paare" and r["combine"] == "beliebig" and r["patience"] == 15.0)
    values = [A.run_once(p, s * C.SUBSEED_STRIDE, DATA["meta"]["hours"]).guests_per_hour for s in C.SWEEP_SEEDS]
    assert sum(values) / len(values) == pytest.approx(cell["gph"], rel=1e-12)


def test_messdatei_passt_zum_code_reservierungszeile_neu_gerechnet():
    row = next(r for r in DATA["reserve"] if (r["tol"], r["cv"], r["f"]) == (15.0, 0.5, 1.0))
    s = R.study(1.0, 0.5, 15.0, 3000, 35)
    assert s.served == pytest.approx(row["served"], rel=1e-12) and s.lost == pytest.approx(row["lost"], rel=1e-12)


def test_alle_messdaten_nutzen_dieselben_annahmen_wie_die_app():
    """Last 1,0 und die vier Verteilungen der App; mittlere Dauer 45 + 10 · Größe."""
    assert set(DISTS) == {"paare", "klein", "gross", "gemischt"} and [mean_dwell(s) for s in C.SIZES] == [65.0, 75.0, 85.0, 105.0]
    assert all(abs(sum(p) - 1.0) < 1e-12 for p in C.DISTRIBUTIONS.values())


def test_bedauern_als_anteil_verlorener_gaeste():
    """Das Bedauern r (so viel mehr Gäste bedient der beste Mix) als Anteil der möglichen Gäste, den der gewählte Mix verliert: 100 · r / (100 + r)."""
    m = ev.regret_matrix(ROWS, "none")
    assert [round(ev.lost_share(x), 1) for x in (m["worst"][0], m["loss"][("paare", "gross")], m["loss"][("gross", "klein")], m["robust_loss"])] == [35.2, 24.2, 30.0, 11.1]
    assert sum(1 for v in m["loss"].values() if ev.lost_share(v) > 10.0) == 6 and sum(1 for v in m["loss"].values() if v > 10.0) == 7
    for key, expected in (("alle0", (13.6, 4.6)), ("alle10", (13.7, 3.7)), ("alle20", (13.9, 2.9))):
        mm = ev.regret_matrix(ROWS, key)
        assert (round(ev.lost_share(mm["worst"][0]), 1), round(ev.lost_share(mm["robust_loss"]), 1)) == expected
    g = DATA["geduld"]
    assert [round(ev.lost_share(ev.geduld_regret(g, p, "aus")), 1) for p in (0.0, 15.0, 30.0)] == [35.1, 35.7, 35.9]
    assert [round(ev.lost_share(ev.geduld_regret(g, p, "beliebig")), 1) for p in (0.0, 15.0, 30.0)] == [31.1, 29.8, 30.7]
    assert ev.lost_share(100.0) == 50.0 and ev.lost_share(0.0) == 0.0


def test_geduld_bestmixe_sind_die_drei_besten_mixe_ohne_kombination():
    assert {tuple(r["design"]) for r in DATA["geduld"]} == {(4, 4, 0), (6, 3, 0), (0, 3, 2)}
    best = ev.regret_matrix(ROWS, "none")["best"]
    assert {(4, 4, 0), (6, 3, 0), (0, 3, 2)} == {best["paare"], best["klein"], best["gross"]}


def test_kette_und_simulation_weichen_bei_umbauzeit_hoechstens_0_24_prozent_ab():
    """Die Kette gibt kombinierten Gruppen Exp(Mittel + δ), die Simulation Exp(Mittel) + δ: 18 Zellen der Geduld-Messreihe bei Geduld 0 gegen die exakte Mix-Reihe."""
    devs = []
    for r in DATA["geduld"]:
        if r["patience"] != 0.0:
            continue
        exact = ev.mix_value(ROWS, r["dist"], tuple(r["design"]), "none" if r["combine"] == "aus" else "alle10")
        devs.append((combine := r["combine"], 100 * abs(r["gph"] - exact) / exact, abs(r["gph"] - exact) / r["se"]))
    assert len(devs) == 18
    assert max(d[1] for d in devs) < 0.25 and max(d[2] for d in devs) < 1.2
    assert max(d[1] for d in devs if d[0] == "aus") < 0.14


def test_reservierung_randfall_bei_preis_vier_und_grosser_streuung():
    st = ev.reserve_studies(DATA, 0.75, 15.0)
    assert R.best_f(st, 4.0, 0.0) == 1.5 == max(s.f for s in st)
