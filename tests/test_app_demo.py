"""AppTest der Demo selbst: Standardrestaurant, Presets, Permalink, Kernfragen, Exakt-Tab, Reservierungs-Reiter, Grenzfälle."""

import os

import pytest
from streamlit.testing.v1 import AppTest

import rtm_constants as C

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
TIMEOUT = int(os.environ.get("APPTEST_TIMEOUT", "300"))


def _app() -> AppTest:
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    return at


def _texts(at):
    return " ".join(x.value for x in list(at.success) + list(at.info) + list(at.warning) + list(at.error))


def _headings(at):
    return " ".join(m.value for m in at.markdown if m.value.startswith("## "))


def _metric(at, label):
    return next(m.value for m in at.metric if m.label == label)


def _num(text):
    return float(text.replace(" %", "").replace(",", "."))


def test_standardrestaurant_zeigt_fuenf_kennzahlen_und_alle_abschnitte():
    at = _app()
    assert [m.label for m in at.metric[:5]] == ["Gäste je Stunde", "Idealer Sitzplatz-Pool", "Gastbelegung", "Tischbelegung", "Kombinierte Gruppen"]
    h = _headings(at)
    for wort in ("Ergebnis", "Kernfrage 1", "Kernfrage 2", "Kernfrage 3", "Reservierung", "Experimente"):
        assert wort in h
    assert _num(_metric(at, "Gäste je Stunde")) == pytest.approx(11.18, abs=0.2) and _num(_metric(at, "Idealer Sitzplatz-Pool")) == pytest.approx(12.86, abs=0.01)
    assert "weniger Gäste als der Pool" in _texts(at)


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_jedes_preset_laeuft_und_zeigt_die_verdikte(name):
    at = _app()
    at.sidebar.button(key=f"preset_{name}").click().run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    text = _texts(at)
    assert ("weniger Gäste als der Pool" in text) or ("Pool-Schranke" in text)
    assert "Gegenüber ohne Kombination" in text


def test_preset_gleicher_mix_grosse_gruppen_senkt_die_gaeste_gegen_das_standardrestaurant():
    at = _app()
    standard = _num(_metric(at, "Gäste je Stunde"))
    at.sidebar.button(key="preset_Gleicher Mix, große Gruppen").click().run(timeout=TIMEOUT)
    assert _num(_metric(at, "Gäste je Stunde")) < 0.75 * standard


def test_preset_mit_kombination_bringt_wieder_mehr_gaeste_und_zeigt_kombinierte_gruppen():
    at = _app()
    at.sidebar.button(key="preset_Gleicher Mix, große Gruppen").click().run(timeout=TIMEOUT)
    before = _num(_metric(at, "Gäste je Stunde"))
    at.sidebar.button(key="preset_Mit Kombination").click().run(timeout=TIMEOUT)
    assert _num(_metric(at, "Gäste je Stunde")) > 1.3 * before and _num(_metric(at, "Kombinierte Gruppen")) > 0


def test_kernfrage_2_wechselt_mit_dem_gewaehlten_mix():
    at = _app()
    assert "3 × 2er, 3 × 4er, 1 × 6er" in _texts(at)           # der robuste Mix steht in jedem Verdikt
    at.selectbox(key="mix_choice").set_value((3, 3, 1)).run(timeout=TIMEOUT)
    assert not at.exception and "bis zu 12,5 % mehr Gäste" in _texts(at)
    at.radio(key="mix_extra").set_value(20.0).run(timeout=TIMEOUT)
    assert not at.exception and "höchstens 3,0 % mehr" in _texts(at)


def test_exakt_tab_rechnet_und_vergleicht_mit_der_simulation():
    at = _app()
    at.button(key="exact_run").click().run(timeout=TIMEOUT)
    assert not at.exception
    assert _num(next(m.value for m in at.metric if m.label == "Exakte Gäste je Stunde")) == pytest.approx(11.181, abs=5e-4)


def test_exakt_tab_erklaert_warum_er_bei_geduld_nicht_gilt():
    at = _app()
    at.sidebar.slider(key="patience_slider").set_value(15.0).run(timeout=TIMEOUT)
    at.button(key="exact_run").click().run(timeout=TIMEOUT)
    assert not at.exception and any("Geduld 0" in i.value for i in at.info)


def test_reservierungs_reiter_aendert_den_besten_faktor_mit_dem_preis():
    at = _app()
    assert "den größten Nettowert" in _texts(at) and "Rand des gerechneten Bereichs" not in _texts(at)
    at.slider(key="res_w").set_value(0.0).run(timeout=TIMEOUT)
    assert not at.exception and "Rand des gerechneten Bereichs" in _texts(at)


def test_permalink_uebernimmt_werte_und_begrenzt_sie():
    at = AppTest.from_file(APP_PATH)
    at.query_params["t2"] = "6"
    at.query_params["t4"] = "99"
    at.query_params["dist"] = "gross"
    at.query_params["comb"] = "unsinn"
    at.query_params["pat"] = "15"
    at.run(timeout=TIMEOUT)
    assert not at.exception
    assert at.sidebar.slider(key="t2_slider").value == 6 and at.sidebar.slider(key="t4_slider").value == C.TABLES_MAX
    assert at.sidebar.selectbox(key="dist_select").value == "gross" and at.sidebar.selectbox(key="combine_select").value == "aus"
    assert at.sidebar.slider(key="patience_slider").value == 15.0


def test_nur_sechsertische_und_ein_tisch_laufen():
    at = _app()
    for key, value in (("t2_slider", 0), ("t4_slider", 0), ("t6_slider", 1)):
        at.sidebar.slider(key=key).set_value(value)
    at.run(timeout=TIMEOUT)
    assert not at.exception and "6 Plätze an 1 Tischen" in " ".join(c.value for c in at.sidebar.caption)


def test_die_sechs_experimente_und_die_reservierungstabelle_stehen_als_tabellen_da():
    at = _app()
    assert len(at.dataframe) == 7      # Reservierungstabelle und die Tabellen der Experimente 1 bis 6 (Experiment 3 hat zusätzlich ein Diagramm)
    assert [s.value for s in at.subheader if s.value.startswith("🔬")] and len([s for s in at.subheader if s.value.startswith("🔬")]) == 6
