"""Reservierungen (Reiter „Walk-in gegen Reservierung“): ein Abend mit sieben Tischen, 22 Reservierungsanfragen zu Startzeiten im 30-Minuten-Raster.

Annahme nach der GEPLANTEN Dauer (Planungsfaktor f mal Mittel der Gruppengröße): eine Anfrage wird angenommen, wenn ein passender Tisch in dem geplanten Zeitfenster frei ist
(kleinster passender Tisch). Die WIRKLICHE Dauer ist lognormal mit dem Mittel der Gruppengröße und dem Variationskoeffizienten `cv`. Überzieht ein Gast, wartet die Folgegruppe;
muss sie länger als die Wartegrenze `tol` warten, geht sie (zugesagt, aber abgewiesen). Gemeinsame Zufallszahlen für alle f: derselbe Abend wird mit jedem Faktor durchgespielt.
Nettowert = bediente Gäste − w · abgewiesene Zusagen − c · Gästestunden Wartezeit der Bedienten (w und c sind Annahmen)."""

import math
from dataclasses import dataclass

import rtm_constants as C
from rtm_rng import SplitMix64
from rtm_scenario import mean_dwell

TABLES = (2, 2, 2, 4, 4, 4, 6)
REQUESTS = 22
STARTS = tuple(range(0, 241, 30))            # neun Startzeiten, Minuten ab Öffnung
DIST = "paare"
F_GRID = (0.5, 0.6, 0.7, 0.85, 1.0, 1.15, 1.3, 1.5)
CV_CHOICES = (0.25, 0.5, 0.75)
TOL_CHOICES = (15.0, 30.0)


@dataclass(frozen=True)
class EveningResult:
    served: float          # bediente Gäste
    lost: float            # zugesagte, aber an der Tür abgewiesene Gäste
    wait_gh: float         # Gästestunden Wartezeit der Bedienten
    accepted: float        # angenommene Gäste (bedient plus abgewiesen)


def evening(seed: int, f: float, cv: float, tol: float) -> EveningResult:
    """Ein Abend; `seed` bestimmt Anfragen und Verweildauern (unabhängig von f)."""
    req = SplitMix64(seed)
    dur = SplitMix64(seed + 5_000_000_011)
    probs = C.DISTRIBUTIONS[DIST]
    sizes = [C.SIZES[req.choice(probs)] for _ in range(REQUESTS)]
    starts = [STARTS[req.below(len(STARTS))] for _ in range(REQUESTS)]
    sigma2 = math.log(1.0 + cv * cv)
    sigma = math.sqrt(sigma2)
    factor = [math.exp(sigma * dur.normal() - sigma2 / 2.0) for _ in range(REQUESTS)]
    plan = [[] for _ in TABLES]
    for i in range(REQUESTS):
        s = float(starts[i])
        e = s + f * mean_dwell(sizes[i])
        best = None
        for t, cap in enumerate(TABLES):
            if cap < sizes[i]:
                continue
            if all(e <= a or s >= b for a, b, _ in plan[t]):
                if best is None or cap < TABLES[best]:
                    best = t
        if best is not None:
            plan[best].append((s, e, i))
    served = lost = wait = accepted = 0.0
    for t in range(len(TABLES)):
        free_at = 0.0
        for s, _e, i in sorted(plan[t]):
            accepted += sizes[i]
            start = max(s, free_at)
            if start - s > tol:
                lost += sizes[i]
                continue
            free_at = start + factor[i] * mean_dwell(sizes[i])
            served += sizes[i]
            wait += sizes[i] * (start - s)
    return EveningResult(served, lost, wait / 60.0, accepted)


@dataclass(frozen=True)
class ReserveStudy:
    f: float
    cv: float
    tol: float
    evenings: int
    served: float
    served_se: float
    lost: float
    wait_gh: float
    accepted: float

    def net(self, w: float, c: float) -> float:
        """Nettowert je Abend: bediente Gäste − w · abgewiesene Zusagen − c · Gästestunden Wartezeit (Mittel über die Abende)."""
        return self.served - w * self.lost - c * self.wait_gh


def study(f: float, cv: float, tol: float, evenings: int, seed: int) -> ReserveStudy:
    """Mittel über `evenings` Abende; der Abend k hat den Zufalls-Seed seed · 10 000 019 + k (gleich für jeden Faktor f)."""
    res = [evening(seed * 10_000_019 + k, f, cv, tol) for k in range(evenings)]
    n = len(res)
    mean = lambda g: sum(g(r) for r in res) / n          # noqa: E731
    sv = mean(lambda r: r.served)
    var = sum((r.served - sv) ** 2 for r in res) / (n - 1) if n > 1 else 0.0
    return ReserveStudy(f, cv, tol, n, sv, math.sqrt(var / n), mean(lambda r: r.lost), mean(lambda r: r.wait_gh), mean(lambda r: r.accepted))


def best_f(studies, w: float, c: float):
    """Planungsfaktor mit dem größten Nettowert unter `studies` (Liste von ReserveStudy zu verschiedenen f)."""
    return max(studies, key=lambda s: (s.net(w, c), -s.f)).f
