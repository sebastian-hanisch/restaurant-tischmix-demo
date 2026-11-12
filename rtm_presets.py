"""Permalink (Begrenzen), Presets und Zufalls-Seed-Button (Standardmuster aus dem Demo-Portfolio)."""

import random
from dataclasses import dataclass, fields

import streamlit as st

import rtm_constants as C
from rtm_scenario import Params

DEFAULTS = Params()


@dataclass(frozen=True)
class SettingSpec:
    param: str       # Feld von Params (oder "seed")
    url_param: str
    caster: type
    default: object
    lo: float | None = None
    hi: float | None = None
    choices: tuple | None = None


SETTING_SPECS = {
    "t2_slider": SettingSpec("t2", "t2", int, DEFAULTS.t2, 0, C.TABLES_MAX),
    "t4_slider": SettingSpec("t4", "t4", int, DEFAULTS.t4, 0, C.TABLES_MAX),
    "t6_slider": SettingSpec("t6", "t6", int, DEFAULTS.t6, 0, C.TABLES_MAX),
    "dist_select": SettingSpec("dist", "dist", str, DEFAULTS.dist, choices=tuple(C.DISTRIBUTIONS)),
    "rho_slider": SettingSpec("rho", "rho", float, DEFAULTS.rho, C.RHO_MIN, C.RHO_MAX),
    "rule_select": SettingSpec("rule", "rule", str, DEFAULTS.rule, choices=C.RULES),
    "combine_select": SettingSpec("combine", "comb", str, DEFAULTS.combine, choices=C.COMBINE_MODES),
    "extra_slider": SettingSpec("extra", "extra", float, DEFAULTS.extra, 0.0, C.EXTRA_MAX),
    "patience_slider": SettingSpec("patience", "pat", float, DEFAULTS.patience, 0.0, C.PATIENCE_MAX),
    "arrangement_select": SettingSpec("arrangement", "arr", str, DEFAULTS.arrangement, choices=C.ARRANGEMENTS),
    "seed_input": SettingSpec("seed", "seed", int, C.DEFAULT_SEED, 0, C.SEED_MAX),
}
PARAM_TO_STATE = {spec.param: key for key, spec in SETTING_SPECS.items()}
assert {f.name for f in fields(Params)} | {"seed"} == set(PARAM_TO_STATE), "jedes Feld von Params braucht einen Regler"


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def load_permalink_settings():
    """Einmal je Sitzung: Werte aus der Adresszeile übernehmen, auf die Reglergrenzen begrenzt (Auswahlfelder: nur gültige Werte)."""
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                value = spec.caster(qp[spec.url_param])
            except (ValueError, TypeError):
                continue
            if spec.choices is not None:
                if value not in spec.choices:
                    continue
            else:
                if spec.lo is not None:
                    value = max(spec.lo, value)
                if spec.hi is not None:
                    value = min(spec.hi, value)
            st.session_state[state_key] = value
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """`values`: {state_key: aktueller Wert}; die Adresszeile spiegelt die Konfiguration."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = str(value)
    except Exception:
        pass


def apply_preset(name):
    """Setzt jeden Regler: genannte Felder aus dem Preset, alle übrigen auf den Standard."""
    for state_key, spec in SETTING_SPECS.items():
        if state_key == "seed_input":
            continue
        st.session_state[state_key] = C.PRESETS[name].get(spec.param, spec.default)


def aktives_preset():
    """Name des Presets, dessen Werte GENAU den aktuellen Einstellungen entsprechen (Zufalls-Seed ausgenommen), sonst None."""
    for name, preset in C.PRESETS.items():
        if all(st.session_state.get(key, spec.default) == preset.get(spec.param, spec.default)
               for key, spec in SETTING_SPECS.items() if key != "seed_input"):
            return name
    return None


def sidebar_presets():
    """Schnellstart oben in der Seitenleiste; das aktive Preset ist hervorgehoben (`type="primary"`)."""
    st.header("🎯 Schnellstart")
    st.caption("Ein Beispielrestaurant laden:")
    aktiv = aktives_preset()
    for name in C.PRESETS:
        st.button(name, width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP.get(name, ""), key=f"preset_{name}",
                  type="primary" if aktiv == name else "secondary")


def randomize_seed():
    st.session_state["seed_input"] = random.randint(0, C.SEED_MAX)
