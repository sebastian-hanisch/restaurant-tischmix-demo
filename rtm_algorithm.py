"""Kern: Ereignissimulation des Restaurants (Gruppen kommen als Poisson-Strom, werden an einen Tisch oder eine Tischkombination gesetzt oder warten).

* Ankünfte: Poisson mit der Rate `Params.rate`; Gruppengröße nach der Verteilung; Verweildauer exponentiell mit dem Mittel 45 + 10 · Größe Minuten.
* Tischwahl: Best-Fit (kleinster freier Einzeltisch, der passt) oder Worst-Fit (größter freier Einzeltisch, der passt); passt kein Einzeltisch und ist Kombination erlaubt,
  die freie Tischkombination mit der kleinsten Platzsumme, die passt (bei gleicher Summe das Paar, dessen kleinerer Tisch der kleinste ist, dann nach Reihenfolge im Grundriss).
  Eine kombinierte Gruppe belegt beide Tische um `extra` Minuten länger.
* Warteschlange: ist `patience` > 0, wartet eine Gruppe höchstens so lange (konstante Geduld) und wird gesetzt, sobald ein Tisch frei wird und sie passt (Reihenfolge der Ankunft;
  eine Gruppe, die nicht passt, lässt die folgenden vorbei).
* Alle Zufallsfolgen kommen aus dem eigenen SplitMix64."""

import heapq
import math
from dataclasses import dataclass

import rtm_constants as C
from rtm_rng import SplitMix64
from rtm_scenario import Params, mean_dwell, neighbours


def allowed_pairs(params: Params):
    """Erlaubte Tischpaare (i, j), i < j: None = Kombination aus, 'alle' = jedes Paar, sonst eine Menge von Paaren."""
    tables = params.tables
    if params.combine == "aus":
        return None
    if params.combine == "beliebig":
        return "alle"
    if params.combine == "nur 2er":
        return frozenset((i, j) for i in range(len(tables)) for j in range(i + 1, len(tables)) if tables[i] == 2 and tables[j] == 2)
    return neighbours(len(tables))


def choose_tables(caps, free, size, rule, pairs):
    """Tische für eine Gruppe der Größe `size`: Tupel der Tischnummern oder None.

    `caps`: Plätze je Tisch, `free`: Freizeichen je Tisch, `pairs`: None, 'alle' oder Menge erlaubter Paare (i < j)."""
    order = sorted(range(len(caps)), key=lambda i: (caps[i], i))
    fits = [i for i in order if free[i] and caps[i] >= size]
    if fits:
        if rule == "best":
            return (fits[0],)
        return (max(fits, key=lambda i: (caps[i], -i)),)
    if pairs is None:
        return None
    best = None
    free_sorted = [i for i in order if free[i]]
    for a in range(len(free_sorted)):
        for b in range(a + 1, len(free_sorted)):
            x, y = free_sorted[a], free_sorted[b]
            if pairs != "alle" and (min(x, y), max(x, y)) not in pairs:
                continue
            total = caps[x] + caps[y]
            if total >= size and (best is None or total < best[0]):
                best = (total, x, y)
    return None if best is None else (best[1], best[2])


@dataclass(frozen=True)
class RunResult:
    guests_per_hour: float       # bediente Gäste je Stunde
    offered_per_hour: float      # angekommene Gäste je Stunde
    guest_occupancy: float       # mittlere Zahl sitzender Gäste / Plätze (Gastbelegung)
    seat_occupancy: float        # mittlere Zahl belegter Tischplätze / Plätze (Tischbelegung)
    combined_share: float        # Anteil der gesetzten Gruppen auf kombinierten Tischen
    mean_wait: float             # mittlere Wartezeit der gesetzten Gruppen in Minuten (0 bei Geduld 0)


class Restaurant:
    """Ein Restaurant im Lauf; `advance(t)` führt die Simulation bis zur Zeit `t` (Minuten) fort."""

    def __init__(self, params: Params, seed: int, warmup: float = C.WARMUP_MIN):
        self.p = params
        self.caps = list(params.tables)
        self.free = [True] * len(self.caps)
        self.pairs = allowed_pairs(params)
        self.rng = SplitMix64(seed)
        self.rate = params.rate
        self.warmup = warmup
        self.t = 0.0
        self.events = []     # (Zeit, laufende Nummer, Art, Daten): Art 0 = Abgang, 1 = Ankunft
        self.seq = 0
        self.queue = []      # (Frist, Größe, Verweildauer, Ankunftszeit)
        self.busy = {}       # Tischtupel -> Größe der Gruppe
        self.guests_seated = 0
        self.seats_busy = 0
        self.served = self.offered = 0.0
        self.groups_seated = self.groups_combined = 0
        self.wait_sum = 0.0
        self.area_guests = self.area_seats = 0.0
        self.last = 0.0
        self._push(self.rng.expovariate(1.0 / self.rate), 1, None)

    def _push(self, t, kind, payload):
        self.seq += 1
        heapq.heappush(self.events, (t, self.seq, kind, payload))

    def _account(self, t):
        lo = max(self.last, self.warmup)
        if t > lo:
            self.area_guests += self.guests_seated * (t - lo)
            self.area_seats += self.seats_busy * (t - lo)
        self.last = t

    def _seat(self, size, dwell, t, arrived):
        tabs = choose_tables(self.caps, self.free, size, self.p.rule, self.pairs)
        if tabs is None:
            return False
        for i in tabs:
            self.free[i] = False
        combined = len(tabs) == 2
        stay = dwell + (self.p.extra if combined else 0.0)
        seats = sum(self.caps[i] for i in tabs)
        self.guests_seated += size
        self.seats_busy += seats
        self.busy[tabs] = size
        self._push(t + stay, 0, (tabs, size, seats))
        if t >= self.warmup:
            self.served += size
            self.groups_seated += 1
            self.groups_combined += 1 if combined else 0
            self.wait_sum += t - arrived
        return True

    def advance(self, t_end: float):
        """Führt die Simulation bis `t_end` fort (die Zeit ist ab Beginn gezählt, die Einschwingzeit `warmup` eingeschlossen)."""
        while self.events and self.events[0][0] <= t_end:
            t, _, kind, payload = heapq.heappop(self.events)
            self._account(t)
            self.t = t
            if kind == 1:
                self._push(t + self.rng.expovariate(1.0 / self.rate), 1, None)
                size = C.SIZES[self.rng.choice(self.p.probs)]
                dwell = self.rng.expovariate(mean_dwell(size))
                if t >= self.warmup:
                    self.offered += size
                if not self._seat(size, dwell, t, t) and self.p.patience > 0:
                    self.queue.append((t + self.p.patience, size, dwell, t))
            else:
                tabs, size, seats = payload
                for i in tabs:
                    self.free[i] = True
                self.guests_seated -= size
                self.seats_busy -= seats
                self.busy.pop(tabs, None)
                still = []
                for entry in self.queue:
                    frist, qsize, qdwell, arrived = entry
                    if frist < t:
                        continue
                    if not self._seat(qsize, qdwell, t, arrived):
                        still.append(entry)
                self.queue = still
        self._account(t_end)
        self.t = t_end

    def snapshot(self):
        """Belegung jetzt: je Tisch (Größe der Gruppe oder 0, Nummer des Partnertisches oder -1)."""
        out = [(0, -1) for _ in self.caps]
        for tabs, size in self.busy.items():
            for k, i in enumerate(tabs):
                out[i] = (size, tabs[1 - k] if len(tabs) == 2 else -1)
        return out

    def result(self, t_end: float) -> RunResult:
        span = t_end - self.warmup
        seats = self.p.seats
        return RunResult(
            guests_per_hour=60.0 * self.served / span,
            offered_per_hour=60.0 * self.offered / span,
            guest_occupancy=self.area_guests / span / seats,
            seat_occupancy=self.area_seats / span / seats,
            combined_share=(self.groups_combined / self.groups_seated) if self.groups_seated else 0.0,
            mean_wait=(self.wait_sum / self.groups_seated) if self.groups_seated else 0.0,
        )


def run_once(params: Params, seed: int, hours: float = C.LIVE_HOURS) -> RunResult:
    sim = Restaurant(params, seed)
    t_end = C.WARMUP_MIN + hours * 60.0
    sim.advance(t_end)
    return sim.result(t_end)


@dataclass(frozen=True)
class Study:
    runs: int
    hours: float
    guests_per_hour: float
    guests_se: float             # Standardfehler des Mittels über die Läufe
    offered_per_hour: float
    guest_occupancy: float
    seat_occupancy: float
    combined_share: float
    mean_wait: float


def study(params: Params, seed: int, runs: int = C.LIVE_RUNS, hours: float = C.LIVE_HOURS) -> Study:
    """Mittel über `runs` Läufe mit den Zufalls-Seeds seed · 1000 + k."""
    results = [run_once(params, seed * C.SUBSEED_STRIDE + k, hours) for k in range(runs)]
    n = len(results)

    def mean(f):
        return sum(f(r) for r in results) / n

    g = mean(lambda r: r.guests_per_hour)
    var = sum((r.guests_per_hour - g) ** 2 for r in results) / (n - 1) if n > 1 else 0.0
    return Study(runs=n, hours=hours, guests_per_hour=g, guests_se=math.sqrt(var / n), offered_per_hour=mean(lambda r: r.offered_per_hour),
                 guest_occupancy=mean(lambda r: r.guest_occupancy), seat_occupancy=mean(lambda r: r.seat_occupancy),
                 combined_share=mean(lambda r: r.combined_share), mean_wait=mean(lambda r: r.mean_wait))
