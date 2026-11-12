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
    a, b = Params(**C.PRESETS["Restaurant für Paare"]), Params(**C.PRESETS["Gleicher Mix, große Gruppen"])
    assert (a.t2, a.t4, a.t6) == (b.t2, b.t4, b.t6) and a.dist != b.dist


def test_robuster_mix_preset_ist_der_robuste_mix_der_messreihe():
    import rtm_evaluation as ev
    p = Params(**C.PRESETS["Robuster Mix"])
    assert (p.t2, p.t4, p.t6) == ev.regret_matrix(ev.mix_rows(ev.load_results()), "alle10")["robust"] and p.seats == C.MIX_SEATS
