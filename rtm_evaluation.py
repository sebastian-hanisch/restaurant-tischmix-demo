"""Kennzahlen, Verdikte (reine Funktionen) und Zugriff auf die vorgerechneten Messreihen."""

import json
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

import rtm_algorithm as A
import rtm_constants as C
import rtm_exact as E
import rtm_reserve as R
from rtm_scenario import Params

RESULTS_PATH = Path(__file__).resolve().parent / "data" / "rtm_results.json"
MIX_KEYS = {0.0: "alle0", 10.0: "alle10", 20.0: "alle20"}


@dataclass(frozen=True, kw_only=True)
class Settings:
    params: Params = Params()
    seed: int = C.DEFAULT_SEED


@dataclass(frozen=True)
class Analysis:
    settings: Settings
    study: A.Study               # mit den eingestellten Regeln
    variants: dict               # Kombination: "aus", "beliebig0" (ohne Umbauzeit), "beliebig" (mit eingestellter Umbauzeit), "nachbarn" (Nachbartische, mit Umbauzeit)
    pool: float                  # Gäste je Stunde im idealen Sitzplatz-Pool (Kaufman-Roberts), gleiche Plätze, Verteilung und Last


def pool_for(params: Params) -> float:
    """Idealer Sitzplatz-Pool (jede Gruppe belegt genau ihre Gästezahl an Plätzen), Annahme aller passenden Gruppen."""
    return E.kaufman_roberts(params.seats, params.probs, params.rate)[0]


def analyse(settings: Settings) -> Analysis:
    p, seed = settings.params, settings.seed
    specs = {"aus": replace(p, combine="aus"), "beliebig0": replace(p, combine="beliebig", extra=0.0), "beliebig": replace(p, combine="beliebig"),
             "nachbarn": replace(p, combine="Nachbarn")}
    cache = {}

    def run(params):
        if params not in cache:
            cache[params] = A.study(params, seed)
        return cache[params]

    return Analysis(settings, run(p), {k: run(v) for k, v in specs.items()}, pool_for(p))


def exact_for(params: Params):
    """Exakte Kette für die eingestellten Regeln, oder (None, Grund), wenn sie hier nicht gilt oder zu groß ist."""
    if params.patience > 0:
        return None, "Die exakte Kette gilt für Geduld 0 (Gäste gehen sofort, wenn kein Tisch passt)."
    if params.combine == "Nachbarn":
        return None, "Die exakte Kette rechnet mit Tischarten, nicht mit dem Grundriss: Kombination „Nachbarn“ ist nur in der Simulation möglich."
    combos = {"aus": "none", "nur 2er": "nur22", "beliebig": "alle"}[params.combine]
    counts = {2: params.t2, 4: params.t4, 6: params.t6}
    try:
        return E.exact_chain(counts, params.probs, params.rate, combos, params.extra, params.rule, limit=C.LIVE_STATE_LIMIT), ""
    except ValueError:
        return None, f"Mehr als {C.LIVE_STATE_LIMIT:,} Zustände: für die exakte Kette zu groß (die Simulation rechnet weiter).".replace(",", ".")


@lru_cache(maxsize=1)
def load_results() -> dict:
    return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------------------------- Bedauern des Tischmix (exakte Messreihe)
def mix_rows(data: dict) -> list:
    return data["mix"]


def mix_value(rows: list, dist: str, design, key: str) -> float:
    """Gäste je Stunde des Mixes `design` (Zahl der 2er, 4er, 6er) bei der Verteilung `dist`; key: none, alle0, alle10, alle20."""
    for r in rows:
        if r["dist"] == dist and tuple(r["design"]) == tuple(design):
            return r[key]
    raise KeyError((dist, design, key))


def designs_of(rows: list) -> list:
    return sorted({tuple(r["design"]) for r in rows})


def best_design(rows: list, dist: str, key: str) -> tuple:
    """Bester Mix für die Verteilung (Gleichstand: der erste in der Reihenfolge der Tischzahlen)."""
    return max(designs_of(rows), key=lambda d: (mix_value(rows, dist, d, key), tuple(-x for x in d)))


def regret_of(rows: list, design, actual: str, key: str) -> float:
    """Bedauern des Mixes `design`: wie viel mehr Gäste der beste Mix für die wirkliche Verteilung bedient, in Prozent der Gäste des gewählten Mixes (G_best / G_gewählt − 1).
    Als Anteil der möglichen Gäste, den der gewählte Mix verliert, siehe `lost_share`."""
    return 100.0 * (mix_value(rows, actual, best_design(rows, actual, key), key) / mix_value(rows, actual, design, key) - 1.0)


def lost_share(regret_percent: float) -> float:
    """Anteil der möglichen Gäste, den ein Mix mit dem Bedauern `regret_percent` (Prozent, G_best / G − 1) verliert: 100 · r / (100 + r)."""
    return 100.0 * regret_percent / (100.0 + regret_percent)


def regret_matrix(rows: list, key: str) -> dict:
    """Wenn der Mix für die Verteilung `assumed` gewählt wurde und `actual` eintritt: Bedauern in Prozent. Dazu das größte Bedauern und der robuste Mix."""
    dists = list(C.DISTRIBUTIONS)
    best = {d: best_design(rows, d, key) for d in dists}
    loss = {(a, w): regret_of(rows, best[a], w, key) for a in dists for w in dists}
    worst = max(loss.items(), key=lambda kv: kv[1])
    robust = min(designs_of(rows), key=lambda d: (max(regret_of(rows, d, w, key) for w in dists), d))
    return {"best": best, "loss": loss, "worst": (worst[1],) + worst[0], "robust": robust, "robust_loss": max(regret_of(rows, robust, w, key) for w in dists)}


# ---------------------------------------------------------------------------------------------- Verdikte
def _pct(x: float, digits: int = 1) -> str:
    return f"{x:.{digits}f}".replace(".", ",") + " %"


def _num(x: float, digits: int = 1) -> str:
    return f"{x:.{digits}f}".replace(".", ",")


def verdict_form(a: Analysis) -> tuple:
    """Kernfrage 1: Was kostet die Tischform gegenüber dem idealen Sitzplatz-Pool?"""
    s = a.study
    if a.settings.params.patience > 0:
        return "info", (f"Mit Warteschlange (Geduld {a.settings.params.patience:.0f} Minuten) bedient das Restaurant {_num(s.guests_per_hour)} Gäste je Stunde; die Pool-Schranke "
                        f"({_num(a.pool)}) gilt für Gäste, die sofort gehen, und ist hier keine Obergrenze.")
    gap = 100.0 * (1.0 - s.guests_per_hour / a.pool)
    text = (f"Das Restaurant bedient {_num(s.guests_per_hour)} Gäste je Stunde (Mittel über {s.runs} Läufe, Standardfehler {_num(s.guests_se, 2)}); ein idealer Sitzplatz-Pool mit denselben "
            f"{a.settings.params.seats} Plätzen schafft {_num(a.pool)}. Mit diesen Tischen und Regeln bedient das Restaurant {_pct(gap)} weniger Gäste als der Pool")
    if gap <= 2.0:
        return "success", text + " (höchstens 2 %)."
    if gap <= 8.0:
        return "info", text + " (zwischen 2 und 8 %)."
    return "warning", text + " (mehr als 8 %)."


def verdict_paradox(a: Analysis) -> tuple:
    """Tischbelegung gegen Gastbelegung: Tische können voller sein als die Plätze mit Gästen."""
    s = a.study
    text = f"Die Tische sind im Mittel zu {_pct(100 * s.seat_occupancy, 0)} belegt, die Plätze aber nur zu {_pct(100 * s.guest_occupancy, 0)} mit Gästen: der Rest sind Plätze an belegten Tischen."
    return "info", text


def verdict_combine(a: Analysis) -> tuple:
    """Kernfrage 3: Was bringt die Kombination, und was kosten Umbauzeit und Nachbarschaft?"""
    v = a.variants
    base = v["aus"].guests_per_hour
    ideal = v["beliebig0"].guests_per_hour
    real = v["beliebig"].guests_per_hour
    nb = v["nachbarn"].guests_per_hour
    extra = a.settings.params.extra
    se = max(x.guests_se for x in v.values())
    gain = lambda x: 100.0 * (x / base - 1.0)       # noqa: E731
    text = (f"Gegenüber ohne Kombination ({_num(base)} Gäste je Stunde): beliebige Tischpaare ohne Umbauzeit {_pct(gain(ideal))}, mit {extra:.0f} Minuten Umbau {_pct(gain(real))}, "
            f"nur Nachbartische mit Umbau {_pct(gain(nb))} (Standardfehler je Wert höchstens {_num(se, 2)} Gäste je Stunde).")
    if gain(real) < -0.5:
        return "warning", text + " Mit dieser Umbauzeit schadet die Kombination."
    if gain(real) < 0.5:
        return "info", text + " Hier bringt die Kombination kaum etwas."
    return "success", text


def verdict_mix(rows: list, design, key: str) -> tuple:
    """Kernfrage 2: Was kostet ein falsch geschätzter Mix? `design` und `key` (none, alle0, alle10, alle20) wie in mix_value."""
    dists = list(C.DISTRIBUTIONS)
    losses = {w: regret_of(rows, design, w, key) for w in dists}
    worst_dist = max(losses, key=losses.get)
    m = regret_matrix(rows, key)
    a, b, c = design
    name = f"{a} × 2er, {b} × 4er, {c} × 6er"
    text = (f"Der beste Mix für die wirkliche Verteilung bedient bis zu {_pct(losses[worst_dist])} mehr Gäste als der Mix {name} (bei der Verteilung „{C.DIST_SHORT[worst_dist]}“; "
            f"das sind {_pct(lost_share(losses[worst_dist]))} der möglichen Gäste, die dieser Mix verliert); beim robustesten Mix dieser Rechenregel "
            f"({m['robust'][0]} × 2er, {m['robust'][1]} × 4er, {m['robust'][2]} × 6er) bedient der beste Mix höchstens {_pct(m['robust_loss'])} mehr.")
    kind = "success" if losses[worst_dist] <= m["robust_loss"] + 1.0 else "warning"
    return kind, text


def verdict_reserve(studies: list, w: float, c: float) -> tuple:
    """Reservierungs-Reiter: Planungsfaktor mit dem größten Nettowert unter den gerechneten Faktoren."""
    best = R.best_f(studies, w, c)
    at_edge = best in (min(s.f for s in studies), max(s.f for s in studies))
    served_best = max(studies, key=lambda s: s.served).f
    ranked = sorted(studies, key=lambda s: (-s.net(w, c), s.f))
    gap2 = ranked[0].net(w, c) - ranked[1].net(w, c)
    text = (f"Bei einem Preis von {_num(w)} je zugesagtem, aber an der Tür abgewiesenem Gast und {_num(c)} je Gästestunde Wartezeit hat der Planungsfaktor {_num(best, 2)} den größten Nettowert; "
            f"nur nach bedienten Gästen wäre es {_num(served_best, 2)}. Der zweitbeste Faktor ({_num(ranked[1].f, 2)}) liegt nur {_num(gap2, 2)} Gäste je Abend dahinter.")
    if at_edge:
        return "warning", text + " Der beste Wert liegt am Rand des gerechneten Bereichs: die Aussage „beste Planlänge“ gilt hier nicht."
    return "info", text


# ---------------------------------------------------------------------------------------------- Auswertung der vorgerechneten Messreihen
def halte_table(rows: list) -> list:
    """Je Umbauzeit: Zuwachs des besten kombinierbaren Mixes gegen den besten dedizierten (je Verteilung), größtes Bedauern einer falschen Annahme, robuster Mix und Zahl der Fälle,
    in denen Kombination (derselbe Mix) schlechter ist als ohne."""
    dists = list(C.DISTRIBUTIONS)
    out = []
    for extra, key in MIX_KEYS.items():
        gains = {}
        for d in dists:
            ded = max(mix_value(rows, d, x, "none") for x in designs_of(rows))
            comb = max(mix_value(rows, d, x, key) for x in designs_of(rows))
            gains[d] = 100.0 * (comb / ded - 1.0)
        m = regret_matrix(rows, key)
        cells = [(d, x) for d in dists for x in designs_of(rows)]
        harm = sum(1 for d, x in cells if mix_value(rows, d, x, key) < mix_value(rows, d, x, "none") - 1e-12)
        out.append({"extra": extra, "gain": gains, "worst": m["worst"][0], "robust": m["robust"], "robust_loss": m["robust_loss"], "harm": harm, "cells": len(cells)})
    return out


def geduld_regret(rows: list, patience: float, combine: str) -> float:
    """Größtes Bedauern einer falschen Annahme (wie viel mehr der beste von drei Mixen bedient) unter den drei Bestmixen OHNE Kombination (je Verteilung einer: (4,4,0), (6,3,0), (0,3,2)), bei der Geduld `patience`; `combine` ist die Regel, mit der alle drei gespielt werden."""
    worst = 0.0
    for actual in ("paare", "klein", "gross"):
        cells = {r["assumed"]: r["gph"] for r in rows if r["dist"] == actual and r["combine"] == combine and r["patience"] == patience}
        top = max(cells.values())
        worst = max(worst, max(100.0 * (top / v - 1.0) for v in cells.values()))
    return worst


def geduld_gain(rows: list, patience: float, combine: str) -> float:
    """Gäste je Stunde der drei passenden Mixe (Mix für die eingetretene Verteilung), gemittelt, bei der Geduld `patience`."""
    vals = [r["gph"] for r in rows if r["assumed"] == r["dist"] and r["combine"] == combine and r["patience"] == patience]
    return sum(vals) / len(vals)


def nachbar_table(rows: list) -> list:
    """Je Verteilung und Anordnung: Gäste je Stunde ohne Kombination, mit beliebigen Paaren und mit Nachbarn, ohne und mit 10 Minuten Umbau."""
    out = []
    for dist in ("paare", "klein", "gross"):
        for arr in C.ARRANGEMENTS:
            cells = {(r["combine"], r["extra"]): r["gph"] for r in rows if r["dist"] == dist and r["arrangement"] == arr}
            out.append({"dist": dist, "arrangement": arr, "aus": cells[("aus", 0.0)], "beliebig0": cells[("beliebig", 0.0)], "beliebig10": cells[("beliebig", 10.0)],
                        "nachbarn0": cells[("Nachbarn", 0.0)], "nachbarn10": cells[("Nachbarn", 10.0)]})
    return out


def pool_gap_table(data: dict) -> list:
    """Je Verteilung: Pool-Schranke, bester dedizierter Mix, bester kombinierbarer Mix (10 Minuten Umbau) und der Abstand zum Pool in Prozent."""
    rows = mix_rows(data)
    out = []
    for d in C.DISTRIBUTIONS:
        pool = data["pool"][d]["opt"]
        bd = best_design(rows, d, "none")
        bc = best_design(rows, d, "alle10")
        vd, vc = mix_value(rows, d, bd, "none"), mix_value(rows, d, bc, "alle10")
        out.append({"dist": d, "pool": pool, "dedicated": bd, "dedicated_gph": vd, "gap_dedicated": 100.0 * (1.0 - vd / pool),
                    "combinable": bc, "combinable_gph": vc, "gap_combinable": 100.0 * (1.0 - vc / pool)})
    return out


def reserve_studies(data: dict, cv: float, tol: float) -> list:
    """Vorgerechnete Reservierungsabende als ReserveStudy-Liste (ein Eintrag je Planungsfaktor)."""
    return [R.ReserveStudy(r["f"], r["cv"], r["tol"], 3000, r["served"], r["served_se"], r["lost"], r["wait_gh"], r["accepted"])
            for r in data["reserve"] if r["cv"] == cv and r["tol"] == tol]
