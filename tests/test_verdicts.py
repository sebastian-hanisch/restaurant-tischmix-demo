"""Verdikte (reine Funktionen in rtm_evaluation.py) an handgesetzten Werten: Schwellen und jede Zahl im Text; dazu die erwartete Verdikt-Zeile je Preset (DEMO-PLAYBOOK 11a Punkt 7)."""

import pytest

import rtm_algorithm as A
import rtm_constants as C
import rtm_evaluation as ev
import rtm_reserve as R
from rtm_scenario import Params

DATA = ev.load_results()
ROWS = ev.mix_rows(DATA)


def _study(gph=10.0, se=0.05, seat=0.64, guest=0.58, comb=0.0, wait=0.0):
    return A.Study(runs=8, hours=3000, guests_per_hour=gph, guests_se=se, offered_per_hour=gph + 2, guest_occupancy=guest, seat_occupancy=seat, combined_share=comb, mean_wait=wait)


def _analysis(params=Params(), study=None, pool=12.8, aus=10.0, ideal=11.0, real=10.8, nb=10.7):
    v = {"aus": _study(aus), "beliebig0": _study(ideal), "beliebig": _study(real), "nachbarn": _study(nb)}
    return ev.Analysis(ev.Settings(params=params), study or _study(), v, pool)


def test_verdikt_form_drei_stufen_mit_zahlen():
    kind, text = ev.verdict_form(_analysis(study=_study(10.0), pool=12.8))
    assert kind == "warning" and "10,0 Gäste je Stunde" in text and "12,8" in text and "bedient das Restaurant 21,9 % weniger Gäste als der Pool" in text and "mehr als 8 %" in text
    kind, text = ev.verdict_form(_analysis(study=_study(11.9), pool=12.8))        # 7,03 %
    assert kind == "info" and "7,0 %" in text and "zwischen 2 und 8 %" in text
    kind, text = ev.verdict_form(_analysis(study=_study(12.6), pool=12.8))        # 1,56 %
    assert kind == "success" and "höchstens 2 %" in text


def test_verdikt_form_mit_warteschlange_nennt_die_schranke_nicht_als_obergrenze():
    kind, text = ev.verdict_form(_analysis(params=Params(patience=15.0), study=_study(13.5)))
    assert kind == "info" and "Geduld 15 Minuten" in text and "keine Obergrenze" in text and "gilt für Gäste, die sofort gehen" in text


def test_verdikt_belegung():
    kind, text = ev.verdict_paradox(_analysis(study=_study(seat=0.64, guest=0.58)))
    assert kind == "info" and "zu 64 %" in text and "nur zu 58 %" in text


def test_verdikt_kombination_drei_faelle():
    kind, text = ev.verdict_combine(_analysis(aus=10.0, ideal=11.0, real=10.8, nb=10.7))
    assert kind == "success" and "ohne Umbauzeit 10,0 %" in text and "mit 10 Minuten Umbau 8,0 %" in text and "nur Nachbartische mit Umbau 7,0 %" in text
    kind, text = ev.verdict_combine(_analysis(aus=10.0, ideal=10.5, real=9.8, nb=9.7))
    assert kind == "warning" and "schadet die Kombination" in text and "mit 10 Minuten Umbau -2,0 %" in text
    kind, text = ev.verdict_combine(_analysis(aus=10.0, ideal=9.9, real=9.85, nb=9.8))      # auch wenn schon ohne Umbauzeit nichts bringt: Schaden wird gemeldet
    assert kind == "warning" and "schadet die Kombination" in text
    kind, text = ev.verdict_combine(_analysis(aus=10.0, ideal=10.3, real=10.04, nb=10.02))
    assert kind == "info" and "kaum etwas" in text


def test_verdikt_kombination_nennt_die_umbauzeit_der_einstellung():
    _, text = ev.verdict_combine(_analysis(params=Params(extra=25.0)))
    assert "mit 25 Minuten Umbau" in text


def test_verdikt_mix_robuster_mix_und_schlechter_mix():
    kind, text = ev.verdict_mix(ROWS, (3, 3, 1), "none")
    assert kind == "success" and "3 × 2er, 3 × 4er, 1 × 6er" in text and "bis zu 12,5 % mehr Gäste" in text and "höchstens 12,5 % mehr" in text and "11,1 % der möglichen Gäste" in text
    kind, text = ev.verdict_mix(ROWS, (4, 4, 0), "none")
    assert kind == "warning" and "bis zu 32,0 % mehr Gäste als der Mix 4 × 2er, 4 × 4er, 0 × 6er (bei der Verteilung „viele große Gruppen“; das sind 24,2 % der möglichen Gäste" in text and "höchstens 12,5 % mehr" in text
    kind, text = ev.verdict_mix(ROWS, (0, 0, 4), "alle10")
    assert kind == "warning" and "(6 × 2er, 3 × 4er, 0 × 6er) bedient der beste Mix höchstens 3,9 % mehr" in text


def test_verdikt_reservierung_innerer_bestwert_und_rand():
    studies = ev.reserve_studies(DATA, 0.5, 15.0)
    kind, text = ev.verdict_reserve(studies, 2.0, 0.5)
    assert kind == "info" and "Planungsfaktor 1,15 den größten Nettowert" in text and "nur nach bedienten Gästen wäre es 0,50" in text and "Der zweitbeste Faktor (1,00) liegt nur" in text
    kind, text = ev.verdict_reserve(studies, 0.0, 0.0)
    assert kind == "warning" and "Rand des gerechneten Bereichs" in text and "gilt hier nicht" in text


def test_verdikt_form_je_preset():
    erwartet = {"Viele Paare, passender Mix": "warning", "Gleicher Mix, große Gruppen": "warning", "Mit Kombination": "info", "Mit Umbauzeit": "warning", "Mit Warteschlange": "info", "Robuster Mix": "warning"}
    assert set(erwartet) == set(C.PRESETS)
    for name, kind in erwartet.items():
        a = ev.analyse(ev.Settings(params=Params(**C.PRESETS[name])))
        assert ev.verdict_form(a)[0] == kind, (name, ev.verdict_form(a)[1])


def test_verdikt_kombination_je_preset_behauptet_keinen_schaden_bei_20_minuten_umbau():
    """Auch mit 20 Minuten Umbau bringt die Kombination im Preset „Mit Umbauzeit“ mehr Gäste als ohne (Messung: +35,9 %): das Verdikt meldet Erfolg."""
    a = ev.analyse(ev.Settings(params=Params(**C.PRESETS["Mit Umbauzeit"])))
    assert ev.verdict_combine(a)[0] == "success" and "mit 20 Minuten Umbau" in ev.verdict_combine(a)[1]


def test_analyse_nutzt_den_eingestellten_lauf_wenn_er_einer_variante_gleicht():
    p = Params(combine="beliebig")
    a = ev.analyse(ev.Settings(params=p))
    assert a.study == a.variants["beliebig"]
    assert a.pool == pytest.approx(ev.pool_for(p))


def test_reserve_best_f_waehlt_den_groessten_nettowert_bei_gleichstand_den_kleineren_faktor():
    mk = lambda f, served: R.ReserveStudy(f, 0.5, 15.0, 10, served, 0.1, 0.0, 0.0, served)      # noqa: E731
    assert R.best_f([mk(0.5, 5), mk(1.0, 5), mk(1.5, 4)], 0.0, 0.0) == 0.5
