"""Presets: Vollständigkeit, gültige Werte, Standard-Preset = Standardeinstellungen; Permalink-Spezifikation."""

import dataclasses

import rtm_constants as C
import rtm_presets as P
from rtm_scenario import Params


def test_jedes_preset_hat_hilfetext_und_nur_bekannte_felder():
    assert set(C.PRESETS) == set(C.PRESET_HELP)
    felder = {f.name for f in dataclasses.fields(Params)}
    for name, preset in C.PRESETS.items():
        assert set(preset) <= felder, name
        assert C.PRESET_HELP[name]
        Params(**preset)            # jedes Preset ist gültig


def test_das_erste_preset_ist_der_standard():
    assert Params(**C.PRESETS[next(iter(C.PRESETS))]) == Params()


def test_jeder_regler_hat_eine_url_und_ein_params_feld():
    urls = [spec.url_param for spec in P.SETTING_SPECS.values()]
    assert len(urls) == len(set(urls))
    felder = {f.name for f in dataclasses.fields(Params)} | {"seed"}
    assert {spec.param for spec in P.SETTING_SPECS.values()} == felder


def test_standardwerte_der_regler_sind_die_der_params():
    d = Params()
    for key, spec in P.SETTING_SPECS.items():
        if spec.param != "seed":
            assert spec.default == getattr(d, spec.param), key


def test_preset_gleicher_mix_hat_denselben_mix_wie_das_standardrestaurant():
    a, b = Params(**C.PRESETS["Viele Paare, passender Mix"]), Params(**C.PRESETS["Gleicher Mix, große Gruppen"])
    assert (a.t2, a.t4, a.t6) == (b.t2, b.t4, b.t6) and a.dist != b.dist


def test_robuster_mix_preset_ist_der_robuste_mix_der_messreihe():
    import rtm_evaluation as ev
    p = Params(**C.PRESETS["Robuster Mix"])
    assert (p.t2, p.t4, p.t6) == ev.regret_matrix(ev.mix_rows(ev.load_results()), "alle10")["robust"] and p.seats == C.MIX_SEATS


def test_verteilungsnamen_nennen_mittlere_gruppengroesse_und_anteile():
    """Die Anzeigenamen der Verteilungen nennen die mittlere Gruppengröße (kaufmännisch gerundet) und, wo sie vorkommen, die Anteile; kein Name verspricht „überwiegend Paare“ bei weniger als 50 %."""
    from decimal import ROUND_HALF_UP, Decimal
    for key, probs in C.DISTRIBUTIONS.items():
        mean = Decimal(str(round(sum(p * s for p, s in zip(probs, C.SIZES)), 10))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        assert f"Ø {mean}".replace(".", ",") in C.DIST_LABELS[key], key
    assert "45 % Paare" in C.DIST_LABELS["paare"] and "70 % Paare" in C.DIST_LABELS["klein"] and "65 % ab vier" in C.DIST_LABELS["gross"]
    assert C.DISTRIBUTIONS["paare"][0] == 0.45 and C.DISTRIBUTIONS["klein"][0] == 0.70 and round(sum(C.DISTRIBUTIONS["gross"][2:]), 10) == 0.65
    assert "überwiegend Paare" not in C.PRESET_HELP["Viele Paare, passender Mix"]
