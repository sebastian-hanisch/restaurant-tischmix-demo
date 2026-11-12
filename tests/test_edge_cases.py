"""Randfälle: ungültige Eingaben, kleinste Restaurants, Reglergrenzen, Zustandsgrenze der exakten Kette."""

import pytest

import rtm_algorithm as A
import rtm_constants as C
import rtm_evaluation as ev
import rtm_exact as E
import rtm_presets as P
from rtm_scenario import Params


@pytest.mark.parametrize("kw", [dict(t2=-1), dict(t4=11), dict(t2=0, t4=0, t6=0), dict(t2=True), dict(t2=1.5), dict(dist="x"), dict(rho=0.0), dict(rho=2.0), dict(combine="x"),
                                dict(extra=-1.0), dict(extra=41.0), dict(patience=-1.0), dict(patience=61.0), dict(rule="x"), dict(arrangement="x")])
def test_ungueltige_eingaben_werden_abgelehnt(kw):
    with pytest.raises(ValueError):
        Params(**kw)


def test_params_nimmt_nur_schluesselwoerter():
    with pytest.raises(TypeError):
        Params(4, 4, 0)


def test_kleinstes_restaurant_ein_zweiertisch():
    for kw in (dict(), dict(combine="beliebig"), dict(combine="Nachbarn"), dict(patience=30.0)):
        r = A.run_once(Params(t2=1, t4=0, t6=0, **kw), 3, 300)
        assert 0 <= r.guest_occupancy <= 1 and r.combined_share == 0.0


def test_groesstes_restaurant_laeuft_und_hat_die_erwarteten_plaetze():
    p = Params(t2=C.TABLES_MAX, t4=C.TABLES_MAX, t6=C.TABLES_MAX)
    assert p.seats == C.SEATS_MAX == 120
    assert A.run_once(p, 3, 100).guests_per_hour > 0


def test_nur_sechsertische_nehmen_alle_gruppen_ohne_kombination():
    """Auf Sechsertischen passt jede Gruppe: ohne Kombination gibt es keine kombinierten Gruppen, und Best-Fit gleich Worst-Fit (alle Tische gleich)."""
    r1 = A.run_once(Params(t2=0, t4=0, t6=3, rule="best"), 4, 800)
    r2 = A.run_once(Params(t2=0, t4=0, t6=3, rule="worst"), 4, 800)
    assert r1.combined_share == 0.0 and r1.guests_per_hour == pytest.approx(r2.guests_per_hour)


def test_zweiertische_allein_koennen_gruppen_ab_drei_nur_kombiniert_setzen():
    ohne = A.run_once(Params(t2=6, t4=0, t6=0, combine="aus"), 4, 800)
    mit = A.run_once(Params(t2=6, t4=0, t6=0, combine="beliebig", extra=0.0), 4, 800)
    assert mit.guests_per_hour > 1.5 * ohne.guests_per_hour


def test_kombination_nachbarn_ohne_nachbarn_verhaelt_sich_wie_aus():
    """Zwei Tische in einer Zeile mit fünf Spalten sind Nachbarn, aber ein einzelner Tisch hat keinen: mit einem Tisch ist „Nachbarn“ gleich „aus“."""
    assert A.run_once(Params(t2=1, t4=0, t6=0, combine="Nachbarn"), 6, 300) == A.run_once(Params(t2=1, t4=0, t6=0, combine="aus"), 6, 300)


def test_exakte_kette_lehnt_zu_grosse_zustandsraeume_ab():
    p = Params(t2=10, t4=10, t6=10, combine="beliebig")
    with pytest.raises(ValueError):
        E.exact_chain({2: 10, 4: 10, 6: 10}, p.probs, p.rate, "alle", limit=500)


def test_exakte_kette_unbekannte_regel_wird_abgelehnt():
    with pytest.raises(ValueError):
        E.exact_chain({2: 1}, C.DISTRIBUTIONS["paare"], 0.01, "x")


def test_exact_for_erklaert_warum_sie_nicht_gilt():
    res, why = ev.exact_for(Params(patience=15.0))
    assert res is None and "Geduld 0" in why
    res, why = ev.exact_for(Params(combine="Nachbarn"))
    assert res is None and "Nachbarn" in why
    res, why = ev.exact_for(Params(t2=10, t4=10, t6=10, combine="beliebig"))
    assert res is None and "Zustände" in why
    res, why = ev.exact_for(Params())
    assert res is not None and why == "" and res.guests_per_hour == pytest.approx(11.181, abs=5e-4)


def test_last_regelt_die_zahl_der_ankuenfte():
    low = A.run_once(Params(rho=0.3), 5, 800).offered_per_hour
    high = A.run_once(Params(rho=1.8), 5, 800).offered_per_hour
    assert high == pytest.approx(6 * low, rel=0.15)


def test_alle_regler_haben_grenzen_innerhalb_der_params_gueltigkeit():
    for key, spec in P.SETTING_SPECS.items():
        if spec.choices is not None:
            for choice in spec.choices:
                Params(**{spec.param: choice})
        elif spec.param != "seed":
            Params(**{spec.param: spec.lo})
            Params(**{spec.param: spec.hi})
    Params(t2=0, t4=0, t6=1)
