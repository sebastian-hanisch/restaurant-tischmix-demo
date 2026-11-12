"""Erzeugt `data/rtm_results.json`: vorgerechnete Messreihen (exakte Kette und Simulationen mit festen Zufalls-Seeds).

    python tools/make_results.py <teil> [<teil> ...]      Teile: mix pool annahme geduld nachbar reserve

Jeder Teil schreibt seinen Abschnitt in die Datei und lässt die übrigen stehen. Die Simulationen nutzen die Zufalls-Seeds `C.SWEEP_SEEDS` (je Lauf seed · 1000 + k, hier k = 0).
Reihenfolge der Teile: `mix` zuerst (24 Plätze, 19 Mixe, vier Verteilungen, exakt); die Teile sind unabhängig und einzeln wiederholbar (Erfahrung: Teile nacheinander im Vordergrund laufen lassen)."""

import itertools
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import rtm_algorithm as A  # noqa: E402
import rtm_constants as C  # noqa: E402
import rtm_exact as E  # noqa: E402
import rtm_reserve as R  # noqa: E402
from rtm_scenario import Params, mean_dwell  # noqa: E402

OUT = ROOT / "data" / "rtm_results.json"
HOURS = 3000            # Stunden je Simulationslauf nach der Einschwingzeit


def load() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}


def save(data: dict):
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(data, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))   # LF auch unter Windows


def designs(seats: int):
    """Alle Tischmixe (Zahl der 2er, 4er, 6er) mit genau `seats` Plätzen."""
    out = []
    for c in range(0, seats // 6 + 1):
        for b in range(0, (seats - 6 * c) // 4 + 1):
            rest = seats - 6 * c - 4 * b
            if rest % 2 == 0:
                out.append((rest // 2, b, c))
    return out


def rate_for(counts: dict, dist: str, rho: float = 1.0) -> float:
    probs = C.DISTRIBUTIONS[dist]
    seats = sum(t * n for t, n in counts.items())
    return rho * seats / sum(p * s * mean_dwell(s) for p, s in zip(probs, C.SIZES)) * sum(probs)


def part_mix(data):
    rows = []
    for dist in C.DISTRIBUTIONS:
        probs = C.DISTRIBUTIONS[dist]
        for a, b, c in designs(C.MIX_SEATS):
            counts = {2: a, 4: b, 6: c}
            rate = rate_for(counts, dist)
            rec = {"dist": dist, "design": [a, b, c]}
            rec["none"] = E.exact_chain(counts, probs, rate, "none").guests_per_hour
            for extra in C.EXTRAS:
                r = E.exact_chain(counts, probs, rate, "alle", extra)
                rec[f"alle{int(extra)}"] = r.guests_per_hour
            rows.append(rec)
            print("mix", dist, (a, b, c), round(rec["none"], 3), round(rec["alle0"], 3), flush=True)
    data["mix"] = rows


def part_pool(data):
    pool = {}
    for dist in C.DISTRIBUTIONS:
        probs = C.DISTRIBUTIONS[dist]
        counts = {2: 12}
        rate = rate_for(counts, dist)
        kr, _ = E.kaufman_roberts(C.MIX_SEATS, probs, rate)
        pool[dist] = {"kr": kr, "opt": E.pool_optimum(C.MIX_SEATS, probs, rate)}
        print("pool", dist, pool[dist], flush=True)
    data["pool"] = pool


def part_annahme(data):
    """Tischwahl und Größe: Best-Fit gegen Worst-Fit (Auslastungsparadox, kleines Restaurant S), Restaurant S gegen L mit und ohne Kombination."""
    out = {}
    probs = C.DISTRIBUTIONS["paare"]
    small = {2: 2, 4: 2, 6: 1}
    large = {2: 4, 4: 4, 6: 2}
    rate_s = rate_for(small, "paare")
    rate_l = rate_for(large, "paare")
    for rule in ("best", "worst"):
        r = E.exact_chain(small, probs, rate_s, "none", rule=rule)
        out[f"S_{rule}"] = {"gph": r.guests_per_hour, "guest_occ": r.guest_occupancy, "seat_occ": r.seat_occupancy}
    out["S_alle"] = {"gph": E.exact_chain(small, probs, rate_s, "alle").guests_per_hour}
    out["L_none"] = {"gph": E.exact_chain(large, probs, rate_l, "none").guests_per_hour}
    print("annahme L ohne Kombination", out["L_none"], flush=True)
    try:
        out["L_alle"] = {"gph": E.exact_chain(large, probs, rate_l, "alle").guests_per_hour}
    except ValueError as err:
        out["L_alle"] = {"gph": None, "grund": str(err)}
    print("annahme", out, flush=True)
    data["annahme"] = out


def sim_cell(params: Params, hours=HOURS, seeds=C.SWEEP_SEEDS):
    values = [A.run_once(params, s * C.SUBSEED_STRIDE, hours).guests_per_hour for s in seeds]
    n = len(values)
    mean = sum(values) / n
    se = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1) / n)
    return mean, se


def part_geduld(data):
    """Drei bestmögliche dedizierte Mixe (je eine Verteilung) gegen jede wirkliche Verteilung, Geduld 0 / 15 / 30, ohne Kombination und mit Kombination (10 Minuten Umbau)."""
    best_mix = {"paare": (4, 4, 0), "klein": (6, 3, 0), "gross": (0, 3, 2)}
    rows = []
    for assumed, (a, b, c) in best_mix.items():
        for actual in ("paare", "klein", "gross"):
            for combine, extra in (("aus", 0.0), ("beliebig", 10.0)):
                for patience in (0.0, 15.0, 30.0):
                    p = Params(t2=a, t4=b, t6=c, dist=actual, combine=combine, extra=extra, patience=patience)
                    mean, se = sim_cell(p)
                    rows.append({"assumed": assumed, "design": [a, b, c], "dist": actual, "combine": combine, "extra": extra, "patience": patience, "gph": mean, "se": se})
                    print("geduld", assumed, actual, combine, patience, round(mean, 3), round(se, 3), flush=True)
    data["geduld"] = rows


def part_nachbar(data):
    rows = []
    for dist in ("paare", "klein", "gross"):
        for arrangement in C.ARRANGEMENTS:
            for combine, extra in (("aus", 0.0), ("beliebig", 0.0), ("beliebig", 10.0), ("Nachbarn", 0.0), ("Nachbarn", 10.0)):
                p = Params(t2=8, t4=2, t6=0, dist=dist, combine=combine, extra=extra, arrangement=arrangement)
                mean, se = sim_cell(p)
                rows.append({"dist": dist, "arrangement": arrangement, "combine": combine, "extra": extra, "gph": mean, "se": se, "tables": list(p.tables)})
                print("nachbar", dist, arrangement, combine, extra, round(mean, 3), round(se, 3), flush=True)
    data["nachbar"] = rows


def part_reserve(data):
    rows = []
    for tol in R.TOL_CHOICES:
        for cv in R.CV_CHOICES:
            for f in R.F_GRID:
                s = R.study(f, cv, tol, 3000, 35)
                rows.append({"tol": tol, "cv": cv, "f": f, "served": s.served, "served_se": s.served_se, "lost": s.lost, "wait_gh": s.wait_gh, "accepted": s.accepted})
                print("reserve", tol, cv, f, round(s.served, 2), round(s.lost, 2), flush=True)
    data["reserve"] = rows


PARTS = {"mix": part_mix, "pool": part_pool, "annahme": part_annahme, "geduld": part_geduld, "nachbar": part_nachbar, "reserve": part_reserve}


def main(argv):
    if not argv or any(a not in PARTS for a in argv):
        raise SystemExit(__doc__)
    data = load()
    data.setdefault("meta", {})
    data["meta"].update({"sweep_seeds": list(C.SWEEP_SEEDS), "hours": HOURS, "warmup_min": C.WARMUP_MIN, "mix_seats": C.MIX_SEATS})
    for part in argv:
        PARTS[part](data)
        save(data)
        print("fertig:", part, flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
