"""Szenario: Restaurant mit Tischen, Gruppenverteilung, Last und Regeln.

`Params` hat nur Schlüsselwörter (ein später eingefügtes Feld verschiebt nie still Werte)."""

from dataclasses import dataclass

import rtm_constants as C


def mean_dwell(size: int) -> float:
    """Mittlere Verweildauer einer Gruppe der Größe `size` in Minuten (Annahme: 45 + 10 · Größe)."""
    return C.DWELL_BASE + C.DWELL_PER_GUEST * size


@dataclass(frozen=True, kw_only=True)
class Params:
    t2: int = 4                 # Zahl der Zweiertische
    t4: int = 4                 # Zahl der Viertische
    t6: int = 0                 # Zahl der Sechsertische
    dist: str = "paare"         # Gruppenverteilung (Schlüssel von C.DISTRIBUTIONS)
    rho: float = 1.0            # Last: angebotene Gastminuten je Platzminute
    combine: str = "aus"        # Kombination: aus, nur 2er, beliebig, Nachbarn
    extra: float = 10.0         # Umbauzeit in Minuten, um die eine kombinierte Gruppe beide Tische länger belegt
    patience: float = 0.0       # Geduld in Minuten (0: Gäste gehen sofort, wenn kein Tisch passt)
    rule: str = "best"          # Tischwahl: best (Best-Fit) oder worst (Worst-Fit)
    arrangement: str = "sortiert"  # Grundriss: sortiert (kleine Tische zuerst) oder verteilt (größere Tische gleichmäßig über das Raster)

    def __post_init__(self):
        for name in ("t2", "t4", "t6"):
            v = getattr(self, name)
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= C.TABLES_MAX:
                raise ValueError(f"{name} muss eine ganze Zahl von 0 bis {C.TABLES_MAX} sein")
        if self.t2 + self.t4 + self.t6 < 1:
            raise ValueError("mindestens ein Tisch")
        if self.seats > C.SEATS_MAX:
            raise ValueError(f"höchstens {C.SEATS_MAX} Plätze")
        if self.dist not in C.DISTRIBUTIONS:
            raise ValueError(f"dist muss eines von {sorted(C.DISTRIBUTIONS)} sein")
        if not C.RHO_MIN <= self.rho <= C.RHO_MAX:
            raise ValueError(f"rho muss zwischen {C.RHO_MIN} und {C.RHO_MAX} liegen")
        if self.combine not in C.COMBINE_MODES:
            raise ValueError(f"combine muss eines von {C.COMBINE_MODES} sein")
        if not 0.0 <= self.extra <= C.EXTRA_MAX:
            raise ValueError(f"extra muss zwischen 0 und {C.EXTRA_MAX} liegen")
        if not 0.0 <= self.patience <= C.PATIENCE_MAX:
            raise ValueError(f"patience muss zwischen 0 und {C.PATIENCE_MAX} liegen")
        if self.rule not in C.RULES:
            raise ValueError(f"rule muss eines von {C.RULES} sein")
        if self.arrangement not in C.ARRANGEMENTS:
            raise ValueError(f"arrangement muss eines von {C.ARRANGEMENTS} sein")

    @property
    def tables(self) -> tuple:
        """Größen der Tische im Grundriss, zeilenweise im Raster der Breite C.GRID_COLS.

        sortiert: kleine Tische zuerst. verteilt: die größeren Tische gleichmäßig über das Raster (Position des k-ten größeren Tisches: ganzzahliger Anteil von (k + 0,5) · n / Zahl der größeren Tische)."""
        small = [2] * self.t2
        big = [4] * self.t4 + [6] * self.t6
        n = len(small) + len(big)
        if self.arrangement == "sortiert":
            return tuple(small + big)
        positions = []
        for k in range(len(big)):
            pos = int((k + 0.5) * n / len(big))
            while pos in positions:
                pos += 1
            positions.append(pos)
        slots = {pos: size for pos, size in zip(positions, big)}
        it = iter(small)
        return tuple(slots[i] if i in slots else next(it) for i in range(n))

    @property
    def seats(self) -> int:
        return 2 * self.t2 + 4 * self.t4 + 6 * self.t6

    @property
    def probs(self) -> tuple:
        return C.DISTRIBUTIONS[self.dist]

    @property
    def mean_guests(self) -> float:
        """Mittlere Gruppengröße der Verteilung."""
        return sum(p * s for p, s in zip(self.probs, C.SIZES))

    @property
    def rate(self) -> float:
        """Ankunftsrate der Gruppen je Minute: Last · Plätze / (mittlere Gastminuten je Gruppe)."""
        guest_minutes = sum(p * s * mean_dwell(s) for p, s in zip(self.probs, C.SIZES))
        return self.rho * self.seats / guest_minutes * sum(self.probs)


def neighbours(n_tables: int, cols: int = C.GRID_COLS) -> frozenset:
    """Paare (i, j), i < j, von Tischen, die im Raster (zeilenweise, `cols` Spalten) Nachbarn sind (oben, unten, links, rechts)."""
    pairs = set()
    for i in range(n_tables):
        r, c = divmod(i, cols)
        if c + 1 < cols and i + 1 < n_tables:
            pairs.add((i, i + 1))
        if i + cols < n_tables:
            pairs.add((i, i + cols))
    return frozenset(pairs)
