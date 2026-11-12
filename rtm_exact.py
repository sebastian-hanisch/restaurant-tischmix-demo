"""Exakte Rechnung für das Verlustsystem (Geduld 0, Kombination zweier beliebiger Tische oder aus): stationäre Verteilung einer Markov-Kette.

Zustand = Zahl der laufenden Gruppen je (Gruppengröße, Tischkonfiguration); eine Konfiguration ist ein Einzeltisch einer Art oder ein Tischpaar zweier Arten.
Die Kette enthält nur Zustände, die von einem leeren Restaurant aus unter der Tischwahl-Regel erreichbar sind (Ankünfte und Abgänge). Ankünfte sind Poisson, Verweildauern exponentiell; kombinierte Gruppen haben die Dauer Exp(Mittel + `extra`) (die Simulation: Exp(Mittel) + `extra`; gleiches Mittel, andere Verteilung, gemessener Unterschied höchstens 0,24 %).
Diese Datei ist der exakte Weg der Demo; die Simulation (`rtm_algorithm.py`) und eine zweite, unabhängige Umsetzung mit einzelnen Tischen (`tests/test_oracle_restaurant_tischmix.py`) prüfen ihn.

Dazu der ideale Sitzplatz-Pool (jede Gruppe belegt genau ihre Gästezahl an Plätzen): Kaufman-Roberts-Rekursion für die Annahme aller passenden Gruppen und der optimale Gewinn
bei freier Annahme (Relative Value Iteration)."""

import itertools
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl

import rtm_constants as C
from rtm_scenario import mean_dwell

COMBOS = ("none", "nur22", "alle")
STATE_LIMIT = 40000     # Standardgrenze: darüber lehnt `exact_chain` ab (Speicher und Zeit); die App setzt eine kleinere (C.LIVE_STATE_LIMIT)


@dataclass(frozen=True)
class ExactResult:
    guests_per_hour: float
    accept_prob: tuple       # Annahmewahrscheinlichkeit je Gruppengröße (Reihenfolge C.SIZES)
    guest_occupancy: float
    seat_occupancy: float
    states: int


def _configs(types, counts, combos):
    cfgs = [(t,) for t in types]
    if combos == "none":
        return cfgs
    for t1, t2 in itertools.combinations_with_replacement(types, 2):
        if t1 == t2 and counts[t1] < 2:
            continue
        if combos == "alle" or (t1, t2) == (2, 2):
            cfgs.append((t1, t2))
    return cfgs


def exact_chain(counts: dict, probs, rate: float, combos: str = "none", extra: float = 0.0, rule: str = "best", limit: int = STATE_LIMIT) -> ExactResult:
    """Stationäre Rechnung. `counts`: {Platzzahl: Zahl der Tische}, `probs`: Verteilung über C.SIZES, `rate`: Gruppen je Minute."""
    if combos not in COMBOS:
        raise ValueError(f"combos muss eines von {COMBOS} sein")
    types = sorted(t for t, n in counts.items() if n > 0)
    n_of = {t: counts[t] for t in types}
    cfgs = _configs(types, n_of, combos)
    cap = [sum(c) for c in cfgs]
    seats = sum(t * n for t, n in n_of.items())
    keys = [(si, k) for si in range(len(C.SIZES)) for k in range(len(cfgs)) if cap[k] >= C.SIZES[si]]
    kidx = {key: i for i, key in enumerate(keys)}
    stay = [mean_dwell(C.SIZES[si]) + (extra if len(cfgs[k]) == 2 else 0.0) for si, k in keys]

    def free_of(state):
        free = dict(n_of)
        for i, c in enumerate(state):
            if c:
                for t in cfgs[keys[i][1]]:
                    free[t] -= c
        return free

    def pick(free, si):
        size = C.SIZES[si]
        singles = [k for k, c in enumerate(cfgs) if len(c) == 1 and cap[k] >= size and free[c[0]] > 0]
        if singles:
            return min(singles, key=lambda k: (cap[k], k)) if rule == "best" else max(singles, key=lambda k: (cap[k], k))
        pairs = []
        for k, c in enumerate(cfgs):
            if len(c) == 2 and cap[k] >= size:
                need = {}
                for t in c:
                    need[t] = need.get(t, 0) + 1
                if all(free[t] >= v for t, v in need.items()):
                    pairs.append(k)
        return min(pairs, key=lambda k: (cap[k], k)) if pairs else None

    start = tuple([0] * len(keys))
    index = {start: 0}
    order = [start]
    arrivals = []   # je Zustand: Liste (Gruppengrößen-Index, Folgezustandsnummer)
    i = 0
    while i < len(order):
        state = order[i]
        free = free_of(state)
        row = []
        for si in range(len(C.SIZES)):
            k = pick(free, si)
            if k is None:
                row.append((si, None))
                continue
            j = kidx[(si, k)]
            nxt = state[:j] + (state[j] + 1,) + state[j + 1:]
            if nxt not in index:
                index[nxt] = len(order)
                order.append(nxt)
                if len(order) > limit:
                    raise ValueError(f"mehr als {limit} Zustände")
            row.append((si, index[nxt]))
        arrivals.append(row)
        for j, c in enumerate(state):       # auch Zustände nach einem Abgang gehören zur Kette
            if c:
                nxt = state[:j] + (c - 1,) + state[j + 1:]
                if nxt not in index:
                    index[nxt] = len(order)
                    order.append(nxt)
        i += 1
    n = len(order)
    rows, cols, vals = [], [], []
    accept = np.zeros((n, len(C.SIZES)))
    guests = np.zeros(n)
    seats_busy = np.zeros(n)
    for a, state in enumerate(order):
        for si, b in arrivals[a]:
            if b is not None:
                rows.append(a); cols.append(b); vals.append(rate * probs[si])
                accept[a, si] = 1.0
        for j, c in enumerate(state):
            if c:
                nxt = state[:j] + (c - 1,) + state[j + 1:]
                rows.append(a); cols.append(index[nxt]); vals.append(c / stay[j])
                guests[a] += c * C.SIZES[keys[j][0]]
                seats_busy[a] += c * cap[keys[j][1]]
    A = sp.csr_matrix((vals, (rows, cols)), shape=(n, n))
    Q = A - sp.diags(np.asarray(A.sum(axis=1)).ravel())
    QT = Q.T.tolil()
    QT[0, :] = 1.0
    b = np.zeros(n)
    b[0] = 1.0
    pi = spl.spsolve(QT.tocsc(), b)
    pi = np.maximum(pi, 0.0)
    pi /= pi.sum()
    acc = tuple(float(pi @ accept[:, si]) for si in range(len(C.SIZES)))
    gph = 60.0 * rate * sum(probs[si] * C.SIZES[si] * acc[si] for si in range(len(C.SIZES)))
    return ExactResult(gph, acc, float(pi @ guests) / seats, float(pi @ seats_busy) / seats, n)


# ---------------------------------------------------------------------------------------------- idealer Sitzplatz-Pool
def kaufman_roberts(seats: int, probs, rate: float) -> tuple:
    """Kaufman-Roberts-Rekursion: Annahme jeder Gruppe, die in die freien Plätze passt. Rückgabe: (Gäste je Stunde, Sperrwahrscheinlichkeit je Gruppengröße)."""
    load = [rate * probs[si] * mean_dwell(C.SIZES[si]) for si in range(len(C.SIZES))]    # Erlang je Klasse
    q = [0.0] * (seats + 1)
    q[0] = 1.0
    for j in range(1, seats + 1):
        q[j] = sum(load[si] * C.SIZES[si] * q[j - C.SIZES[si]] for si in range(len(C.SIZES)) if j - C.SIZES[si] >= 0) / j
    total = sum(q)
    q = [x / total for x in q]
    block = tuple(sum(q[j] for j in range(seats - C.SIZES[si] + 1, seats + 1)) for si in range(len(C.SIZES)))
    gph = 60.0 * rate * sum(probs[si] * C.SIZES[si] * (1.0 - block[si]) for si in range(len(C.SIZES)))
    return gph, block


def _pool_states(seats: int):
    """Alle Zustände des Pools: Zahl der Gruppen je Größe mit höchstens `seats` belegten Plätzen."""
    out = []

    def rec(si, used, cur):
        if si == len(C.SIZES):
            out.append(tuple(cur))
            return
        for c in range(0, (seats - used) // C.SIZES[si] + 1):
            rec(si + 1, used + c * C.SIZES[si], cur + [c])

    rec(0, 0, [])
    return out


def pool_optimum(seats: int, probs, rate: float, tol: float = 1e-10, max_iter: int = 400000) -> float:
    """Größter möglicher Gewinn (Gäste je Stunde) im idealen Sitzplatz-Pool bei freier Annahme je Gruppe (Relative Value Iteration auf der gleichmäßig gemachten Kette)."""
    states = _pool_states(seats)
    idx = {s: i for i, s in enumerate(states)}
    n = len(states)
    lam = [rate * probs[si] for si in range(len(C.SIZES))]
    mu = [1.0 / mean_dwell(C.SIZES[si]) for si in range(len(C.SIZES))]
    dep = np.array([sum(c * mu[si] for si, c in enumerate(s)) for s in states])
    used = np.array([sum(c * C.SIZES[si] for si, c in enumerate(s)) for s in states])
    up = []      # je Klasse: (Zustände, in die passt, Folgezustand)
    down = []
    for si in range(len(C.SIZES)):
        src = np.array([i for i, s in enumerate(states) if used[i] + C.SIZES[si] <= seats])
        dst = np.array([idx[states[i][:si] + (states[i][si] + 1,) + states[i][si + 1:]] for i in src])
        up.append((src, dst))
        srcd = np.array([i for i, s in enumerate(states) if s[si] > 0])
        dstd = np.array([idx[states[i][:si] + (states[i][si] - 1,) + states[i][si + 1:]] for i in srcd])
        cnt = np.array([states[i][si] for i in srcd], float)
        down.append((srcd, dstd, cnt))
    big = sum(lam) + float(dep.max())
    h = np.zeros(n)
    for _ in range(max_iter):
        new = (big - sum(lam) - dep) * h
        for si in range(len(C.SIZES)):
            src, dst = up[si]
            gain = h.copy()        # Ablehnen: der Zustand bleibt
            if len(src):
                gain[src] = np.maximum(h[src], C.SIZES[si] + h[dst])
            new = new + lam[si] * gain
            srcd, dstd, cnt = down[si]
            if len(srcd):
                new[srcd] += cnt * mu[si] * h[dstd]
        new = new / big
        diff = new - h
        span = float(diff.max() - diff.min())
        h = new - new[0]
        if span < tol:
            break
    return float((diff.max() + diff.min()) / 2.0 * big * 60.0)
