"""Orakel-Tests (DEMO-PLAYBOOK §12): unabhängige Rechenwege für die exakte Kette, den Sitzplatz-Pool und die Simulation.

* `exact_chain` (Zustände = Zahl der Gruppen je Größe und Tischkonfiguration) gegen eine zweite Umsetzung mit EINZELNEN Tischen: jeder Zustand ist die Belegung jedes Tisches,
  dichte Matrix, andere Datenstruktur und anderer Löser. Die zweite Umsetzung stammt vom selben Autor nach denselben Regeln (Tischwahl, Gleichstand, Dauer): sie bestätigt die Umsetzung,
  nicht die Regeln.
* Kaufman-Roberts gegen die Markov-Kette des Pools (dichte Matrix, Annahme aller passenden Gruppen); optimale Annahme nie unter Kaufman-Roberts.
* Simulation gegen die exakte Kette; Prüfwerte aus der Vormessung (`mdp.py` der Planung, andere Umsetzung).
* Reservierungsabend: Eigenschaften (ohne Streuung und mit f ≥ 1 gibt es keine Überziehung)."""

import itertools

import numpy as np
import pytest

import rtm_algorithm as A
import rtm_constants as C
import rtm_exact as E
import rtm_reserve as R
from rtm_scenario import Params, mean_dwell


def oracle_gph(caps, probs, rate, allowed, extra, rule):
    """Zweite Umsetzung: Zustand = je Tisch None oder (Gruppengröße, Partnertisch oder -1); dichte Generatormatrix. `allowed`: None (keine Kombination), "all" oder Menge erlaubter Paare (i < j)."""
    n = len(caps)
    rank = {t: r for r, t in enumerate(sorted(range(n), key=lambda i: (caps[i], i)))}

    def place(state, size):
        free = [i for i in range(n) if state[i] is None]
        singles = [i for i in free if caps[i] >= size]
        if singles:
            if rule == "best":
                return (min(singles, key=lambda i: rank[i]),)
            return (max(singles, key=lambda i: (caps[i], -i)),)
        if allowed is None:
            return None
        cands = [(caps[i] + caps[j], min(rank[i], rank[j]), max(rank[i], rank[j]), i, j) for i, j in itertools.combinations(free, 2)
                 if caps[i] + caps[j] >= size and (allowed == "all" or (i, j) in allowed)]
        if not cands:
            return None
        best = min(cands)
        return (best[3], best[4])

    start = (None,) * n
    index, order = {start: 0}, [start]
    edges = []      # (von, nach, Rate, Klasse oder -1)
    i = 0
    while i < len(order):
        state = order[i]
        for ci, size in enumerate(C.SIZES):
            tabs = place(state, size)
            if tabs is None:
                continue
            new = list(state)
            for k, t in enumerate(tabs):
                new[t] = (size, tabs[1 - k] if len(tabs) == 2 else -1)
            new = tuple(new)
            if new not in index:
                index[new] = len(order)
                order.append(new)
            edges.append((i, index[new], rate * probs[ci], ci))
        seen = set()
        for t in range(n):
            if state[t] is not None and t not in seen:
                size, partner = state[t]
                tabs = (t,) if partner < 0 else (t, partner)
                seen.update(tabs)
                new = list(state)
                for u in tabs:
                    new[u] = None
                new = tuple(new)
                if new not in index:
                    index[new] = len(order)
                    order.append(new)
                stay = mean_dwell(size) + (extra if partner >= 0 else 0.0)
                edges.append((i, index[new], 1.0 / stay, -1))
        i += 1
    m = len(order)
    Q = np.zeros((m, m))
    for a, b, r, _ in edges:
        Q[a, b] += r
        Q[a, a] -= r
    A_ = np.vstack([Q.T, np.ones(m)])
    rhs = np.zeros(m + 1)
    rhs[-1] = 1.0
    pi = np.linalg.lstsq(A_, rhs, rcond=None)[0]
    accepted_guests = sum(pi[a] * r * C.SIZES[ci] for a, _b, r, ci in edges if ci >= 0)
    return 60.0 * accepted_guests


CASES = [
    dict(t2=2, t4=1, t6=0, dist="paare", combine="aus", extra=0.0, rule="best"),
    dict(t2=2, t4=1, t6=0, dist="paare", combine="beliebig", extra=0.0, rule="best"),
    dict(t2=2, t4=1, t6=0, dist="gross", combine="beliebig", extra=15.0, rule="best"),
    dict(t2=1, t4=1, t6=1, dist="klein", combine="aus", extra=0.0, rule="worst"),
    dict(t2=1, t4=1, t6=1, dist="gemischt", combine="beliebig", extra=10.0, rule="best"),
    dict(t2=3, t4=1, t6=0, dist="paare", combine="nur 2er", extra=20.0, rule="best"),
    dict(t2=2, t4=2, t6=0, dist="gross", combine="beliebig", extra=0.0, rule="worst"),
]


def _both(case):
    p = Params(**case)
    combos = {"aus": "none", "nur 2er": "nur22", "beliebig": "alle"}[p.combine]
    exact = E.exact_chain({2: p.t2, 4: p.t4, 6: p.t6}, p.probs, p.rate, combos, p.extra, p.rule).guests_per_hour
    caps = list(p.tables)
    allowed = {"aus": None, "beliebig": "all", "nur 2er": {(i, j) for i, j in itertools.combinations(range(len(caps)), 2) if caps[i] == 2 and caps[j] == 2}}[p.combine]
    return exact, oracle_gph(caps, p.probs, p.rate, allowed, p.extra, p.rule)


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['t2']}-{c['t4']}-{c['t6']}-{c['dist']}-{c['combine']}-{c['extra']:.0f}-{c['rule']}")
def test_exakte_kette_gegen_zweite_umsetzung_mit_einzeltischen(case):
    exact, oracle = _both(case)
    assert exact == pytest.approx(oracle, rel=1e-8, abs=1e-8)


@pytest.mark.parametrize("case", CASES[:3], ids=lambda c: f"{c['combine']}-{c['extra']:.0f}")
def test_simulation_gegen_exakte_kette(case):
    p = Params(**case)
    exact, _ = _both(case)
    s = A.study(p, 21, runs=10, hours=3000)
    assert abs(s.guests_per_hour - exact) < 4 * s.guests_se + 0.01


def test_prueffwerte_der_vormessung():
    """Werte der Planungs-Vormessung (`mdp.py`, andere Umsetzung): kleines Restaurant 2 × 2er, 2 × 4er, 1 × 6er bei „paare“, Last 1, und 24 Plätze 4 × 2er + 4 × 4er."""
    probs = C.DISTRIBUTIONS["paare"]
    small = {2: 2, 4: 2, 6: 1}
    rate = Params(t2=2, t4=2, t6=1).rate
    got = lambda combos, rule="best", extra=0.0: E.exact_chain(small, probs, rate, combos, extra, rule)    # noqa: E731
    assert round(got("none").guests_per_hour, 3) == 7.807 and round(got("alle").guests_per_hour, 3) == 7.938 and round(got("none", "worst").guests_per_hour, 3) == 6.987
    r = got("none", "worst")
    assert (round(r.guest_occupancy, 3), round(r.seat_occupancy, 3)) == (0.487, 0.702)
    p24 = Params()
    c24 = {2: 4, 4: 4, 6: 0}
    assert [round(E.exact_chain(c24, probs, p24.rate, combos, extra).guests_per_hour, 3) for combos, extra in (("none", 0), ("alle", 0), ("alle", 10))] == [11.181, 12.033, 11.834]


def pool_chain_gph(seats, probs, rate):
    """Markov-Kette des Pools mit Annahme aller passenden Gruppen (dichte Matrix), unabhängig von der Rekursion."""
    states = [s for s in itertools.product(*[range(seats // z + 1) for z in C.SIZES]) if sum(c * z for c, z in zip(s, C.SIZES)) <= seats]
    idx = {s: i for i, s in enumerate(states)}
    m = len(states)
    Q = np.zeros((m, m))
    for s, i in idx.items():
        used = sum(c * z for c, z in zip(s, C.SIZES))
        for k, z in enumerate(C.SIZES):
            if used + z <= seats:
                t = idx[s[:k] + (s[k] + 1,) + s[k + 1:]]
                Q[i, t] += rate * probs[k]
                Q[i, i] -= rate * probs[k]
            if s[k]:
                t = idx[s[:k] + (s[k] - 1,) + s[k + 1:]]
                Q[i, t] += s[k] / mean_dwell(z)
                Q[i, i] -= s[k] / mean_dwell(z)
    pi = np.linalg.lstsq(np.vstack([Q.T, np.ones(m)]), np.r_[np.zeros(m), 1.0], rcond=None)[0]
    total = 0.0
    for s, i in idx.items():
        used = sum(c * z for c, z in zip(s, C.SIZES))
        total += pi[i] * sum(rate * probs[k] * z for k, z in enumerate(C.SIZES) if used + z <= seats)
    return 60.0 * total


@pytest.mark.parametrize("dist", list(C.DISTRIBUTIONS))
def test_kaufman_roberts_gegen_die_kette_des_pools(dist):
    probs = C.DISTRIBUTIONS[dist]
    p = Params(t2=3, t4=1, t6=0, dist=dist)          # 10 Plätze
    assert E.kaufman_roberts(p.seats, probs, p.rate)[0] == pytest.approx(pool_chain_gph(p.seats, probs, p.rate), rel=1e-9)


@pytest.mark.parametrize("dist", list(C.DISTRIBUTIONS))
def test_optimale_annahme_im_pool_nie_unter_kaufman_roberts(dist):
    probs = C.DISTRIBUTIONS[dist]
    p = Params(t2=12 - 4, t4=4, t6=0, dist=dist)     # 24 Plätze
    kr = E.kaufman_roberts(p.seats, probs, p.rate)[0]
    opt = E.pool_optimum(p.seats, probs, p.rate)
    assert opt >= kr - 1e-9 and opt <= kr + 0.01
    assert opt <= 60 * p.rate * sum(pr * z for pr, z in zip(probs, C.SIZES)) + 1e-9      # nie mehr als angeboten


def test_gruppen_koennen_den_pool_nicht_uebertreffen():
    """Jede Tischform ist im Pool zulässig: Gäste je Stunde der exakten Kette liegen unter der Pool-Schranke (24 Plätze, Mixe aus der Messreihe)."""
    for design in ((4, 4, 0), (6, 3, 0), (0, 3, 2), (10, 1, 0)):
        p = Params(t2=design[0], t4=design[1], t6=design[2], dist="paare")
        pool = E.pool_optimum(p.seats, p.probs, p.rate)
        assert E.exact_chain({2: design[0], 4: design[1], 6: design[2]}, p.probs, p.rate, "alle").guests_per_hour < pool


def test_reservierungsabend_ohne_streuung_und_mit_genug_planung_hat_keine_ueberziehung():
    for seed in range(50):
        r = R.evening(seed, 1.0, 0.0, 15.0)
        assert r.lost == 0.0 and r.wait_gh == 0.0 and r.served == r.accepted


def test_reservierungsabend_bilanz():
    for seed in range(100):
        r = R.evening(seed, 0.85, 0.5, 15.0)
        assert r.served + r.lost == pytest.approx(r.accepted) and r.served >= 0 and r.wait_gh >= 0


def test_laengere_planung_nimmt_im_mittel_weniger_zusagen_an():
    acc = [R.study(f, 0.5, 15.0, 300, 3).accepted for f in R.F_GRID]
    assert all(a >= b - 1e-9 for a, b in zip(acc, acc[1:]))
