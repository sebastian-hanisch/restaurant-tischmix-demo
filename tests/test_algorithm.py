"""Kern an Mini-Instanzen von Hand (DEMO-PLAYBOOK §1b): Tischwahl, Nachbarn, Rate, Einzeltisch gegen Formel, Simulation gegen die eigene Handrechnung."""

import math

import pytest

import rtm_algorithm as A
import rtm_constants as C
import rtm_exact as E
from rtm_rng import SplitMix64
from rtm_scenario import Params, mean_dwell, neighbours


def test_splitmix64_referenzwerte():
    """Erste Ausgaben des Standard-SplitMix64 mit Zufalls-Seed 0 (veröffentlichte Referenzwerte)."""
    rng = SplitMix64(0)
    assert [rng.next_u64() for _ in range(3)] == [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F]


def test_rate_nach_handrechnung():
    """Ein Zweiertisch, Verteilung „paare“, Last 1: Gastminuten je Gruppe = 0,45·2·65 + 0,17·3·75 + 0,28·4·85 + 0,10·6·105 = 254,95; Rate = 2 / 254,95 Gruppen je Minute."""
    p = Params(t2=1, t4=0, t6=0)
    assert p.seats == 2 and p.rate == pytest.approx(2 / 254.95)
    assert Params(t2=1, t4=0, t6=0, rho=0.5).rate == pytest.approx(1 / 254.95)


def test_mittlere_verweildauer():
    assert [mean_dwell(s) for s in C.SIZES] == [65.0, 75.0, 85.0, 105.0]


def test_best_fit_nimmt_den_kleinsten_passenden_tisch():
    caps, free = [2, 4, 6], [True, True, True]
    assert A.choose_tables(caps, free, 2, "best", None) == (0,)
    assert A.choose_tables(caps, free, 3, "best", None) == (1,)
    assert A.choose_tables(caps, free, 5, "best", None) == (2,)
    assert A.choose_tables(caps, [True, False, True], 3, "best", None) == (2,)


def test_worst_fit_nimmt_den_groessten_freien_tisch():
    caps = [2, 4, 6]
    assert A.choose_tables(caps, [True, True, True], 2, "worst", None) == (2,)
    assert A.choose_tables(caps, [True, True, False], 2, "worst", None) == (1,)
    assert A.choose_tables(caps, [True, True, False], 5, "worst", None) is None


def test_ohne_kombination_geht_eine_zu_grosse_gruppe():
    assert A.choose_tables([2, 2], [True, True], 3, "best", None) is None


def test_kombination_nimmt_die_kleinste_passende_summe():
    caps = [2, 4, 6]
    assert A.choose_tables(caps, [True, True, True], 7, "best", "alle") == (0, 2)        # 2 + 6 = 8 (2 + 4 = 6 reicht nicht, 4 + 6 = 10 ist größer)
    assert A.choose_tables([2, 2, 4], [True, True, True], 4, "best", "alle") == (2,)     # ein Einzeltisch geht vor Kombination
    assert A.choose_tables([2, 2, 2], [True, True, True], 4, "best", "alle") == (0, 1)   # 2 + 2


def test_gleiche_summe_nimmt_das_paar_mit_dem_kleinsten_tisch():
    """2 + 6 und 4 + 4 geben beide 8: das Paar mit dem kleineren Tisch gewinnt (die exakte Kette folgt derselben Regel)."""
    caps = [2, 6, 4, 4]
    assert A.choose_tables(caps, [True] * 4, 8, "best", "alle") == (0, 1)


def test_nur_erlaubte_paare_zaehlen():
    caps = [2, 2, 2]
    assert A.choose_tables(caps, [True] * 3, 4, "best", frozenset({(1, 2)})) == (1, 2)
    assert A.choose_tables(caps, [True] * 3, 4, "best", frozenset()) is None


def test_nachbarn_im_raster():
    assert neighbours(7, cols=5) == frozenset({(0, 1), (1, 2), (2, 3), (3, 4), (5, 6), (0, 5), (1, 6)})
    assert neighbours(1) == frozenset()


def test_erlaubte_paare_je_modus():
    assert A.allowed_pairs(Params(combine="aus")) is None
    assert A.allowed_pairs(Params(combine="beliebig")) == "alle"
    assert A.allowed_pairs(Params(t2=2, t4=1, combine="nur 2er")) == frozenset({(0, 1)})
    assert A.allowed_pairs(Params(t2=2, t4=1, combine="Nachbarn")) == frozenset({(0, 1), (1, 2)})


def test_anordnung_verteilt_setzt_die_groesseren_tische_auseinander():
    assert Params(t2=8, t4=2).tables == (2,) * 8 + (4, 4)
    assert Params(t2=8, t4=2, arrangement="verteilt").tables == (2, 2, 4, 2, 2, 2, 2, 4, 2, 2)
    for kw in (dict(t2=3, t4=3, t6=1), dict(t2=0, t4=5, t6=5), dict(t2=1, t4=1)):
        p = Params(**kw, arrangement="verteilt")
        assert sorted(p.tables) == sorted(Params(**kw).tables)


def test_einzelner_zweiertisch_gegen_die_formel_des_verlustsystems():
    """Ein Zweiertisch nimmt nur Zweiergruppen (Anteil 0,45). M/M/1/1: Auslastung u = a / (1 + a) mit a = λ · 0,45 · 65; Gäste je Stunde = 60 · λ · 0,45 · 2 · (1 − u)."""
    p = Params(t2=1, t4=0, t6=0)
    a = p.rate * 0.45 * 65.0
    expected = 60 * p.rate * 0.45 * 2 * (1 - a / (1 + a))
    exact = E.exact_chain({2: 1}, p.probs, p.rate)
    assert exact.guests_per_hour == pytest.approx(expected, rel=1e-9)
    s = A.study(p, 7, runs=8, hours=3000)
    assert abs(s.guests_per_hour - expected) < 4 * s.guests_se + 0.02


def test_gleicher_seed_gleicher_lauf_anderer_seed_anderer_lauf():
    p = Params()
    assert A.run_once(p, 11, 200) == A.run_once(p, 11, 200)
    assert A.run_once(p, 11, 200) != A.run_once(p, 12, 200)


def test_kennzahlen_liegen_in_ihren_grenzen():
    for kw in (dict(), dict(combine="beliebig"), dict(patience=30.0), dict(rho=1.8), dict(rho=0.3)):
        r = A.run_once(Params(**kw), 3, 500)
        assert 0 <= r.guest_occupancy <= r.seat_occupancy <= 1.0 + 1e-9
        assert 0 <= r.guests_per_hour <= r.offered_per_hour + 1e-9
        assert 0 <= r.combined_share <= 1


def test_ohne_kombination_gibt_es_keine_kombinierten_gruppen():
    assert A.run_once(Params(combine="aus"), 5, 500).combined_share == 0.0
    assert A.run_once(Params(combine="beliebig"), 5, 500).combined_share > 0.0


def test_geduld_null_hat_keine_wartezeit_und_geduld_laesst_gaeste_warten():
    assert A.run_once(Params(patience=0.0), 5, 500).mean_wait == 0.0
    assert A.run_once(Params(patience=30.0), 5, 500).mean_wait > 0.0


def test_geduld_bedient_mehr_gaeste_und_umbauzeit_weniger():
    """Mittel über zehn Zufalls-Seeds (24 Plätze, Paare): Geduld 15 gegen 0 und Kombination mit 20 gegen 0 Minuten Umbau."""
    def mean(**kw):
        return sum(A.run_once(Params(**kw), 100 + k, 1500).guests_per_hour for k in range(10)) / 10
    assert mean(patience=15.0) > 1.03 * mean(patience=0.0)
    assert mean(combine="beliebig", extra=20.0) < mean(combine="beliebig", extra=0.0)
    assert mean(combine="beliebig", extra=0.0) > 1.03 * mean(combine="aus")


def test_schnappschuss_zeigt_besetzte_und_freie_tische():
    sim = A.Restaurant(Params(combine="beliebig"), 9)
    sim.advance(C.WARMUP_MIN + 120)
    snap = sim.snapshot()
    assert len(snap) == 8 and all(group in (0, 2, 3, 4, 6) for group, _ in snap)
    for i, (group, partner) in enumerate(snap):
        if partner >= 0:
            assert snap[partner] == (group, i)


def test_study_mittelt_ueber_laeufe_mit_verschiedenen_seeds():
    s = A.study(Params(), 5, runs=4, hours=300)
    runs = [A.run_once(Params(), 5 * C.SUBSEED_STRIDE + k, 300).guests_per_hour for k in range(4)]
    assert s.guests_per_hour == pytest.approx(sum(runs) / 4) and s.runs == 4
    assert s.guests_se == pytest.approx(math.sqrt(sum((x - s.guests_per_hour) ** 2 for x in runs) / 3 / 4))
