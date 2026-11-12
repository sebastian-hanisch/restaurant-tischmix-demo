"""Konstanten: Regler-Grenzen, feste Annahmen, Farben und Presets."""

SEED_MAX, DEFAULT_SEED = 999999, 35
SWEEP_SEEDS = tuple(range(100000, 100012))   # feste Zufalls-Seeds der vorgerechneten Simulations-Messreihen: nie ein einzelner Seed als Befund
SUBSEED_STRIDE = 1000                        # Zufalls-Seed k eines Laufs: seed * SUBSEED_STRIDE + k (Läufe überlappen sich nie)
LIVE_HOURS = 3000                            # Stunden je Lauf der Live-Rechnung (nach der Einschwingzeit WARMUP_MIN)
LIVE_RUNS = 8
WARMUP_MIN = 300.0
LIVE_STATE_LIMIT = 6000                      # größte Zustandszahl der exakten Kette in der App

TABLES_MAX = 10                              # je Tischart höchstens so viele Tische
SEATS_MAX = 120                              # 10 Tische je Art: 20 + 40 + 60 Plätze
SIZES = (2, 3, 4, 6)                         # Gruppengrößen
TABLE_SIZES = (2, 4, 6)
DWELL_BASE, DWELL_PER_GUEST = 45.0, 10.0     # mittlere Verweildauer (Minuten): 45 + 10 · Gruppengröße
RHO_MIN, RHO_MAX = 0.3, 1.8
EXTRA_MAX = 40.0
PATIENCE_MAX = 60.0
GRID_COLS = 5                                # Grundriss: Tische zeilenweise in einem Raster mit dieser Spaltenzahl

DISTRIBUTIONS = {
    "paare": (0.45, 0.17, 0.28, 0.10),
    "klein": (0.70, 0.15, 0.10, 0.05),
    "gross": (0.15, 0.20, 0.35, 0.30),
    "gemischt": (0.30, 0.20, 0.30, 0.20),
}
DIST_SHORT = {"paare": "Paare", "klein": "kleine Gruppen", "gross": "große Gruppen", "gemischt": "gemischt"}
DIST_LABELS = {"paare": "Paare (45 % Zweiergruppen)", "klein": "Kleine Gruppen (70 % Zweiergruppen)", "gross": "Große Gruppen (65 % ab vier)", "gemischt": "Gemischt"}
COMBINE_MODES = ("aus", "nur 2er", "beliebig", "Nachbarn")
RULES = ("best", "worst")
RULE_LABELS = {"best": "Best-Fit (kleinster passender Tisch)", "worst": "Worst-Fit (größter freier Tisch)"}
ARRANGEMENTS = ("sortiert", "verteilt")

# Messreihe der exakten Kette: 24 Plätze, 19 Tischmixe (Zahl der 2er, 4er, 6er), Last 1,0
MIX_SEATS = 24
EXTRAS = (0.0, 10.0, 20.0)

COLOR_GOOD = "#2F6B65"
COLOR_BAD = "#c0504d"
COLOR_NEUTRAL = "#4c78a8"
COLOR_GRAY = "rgba(150,150,150,0.55)"
COLOR_TABLE = {2: "#8fb8b3", 4: "#4c9a91", 6: "#2F6B65"}

# Presets: jeder Eintrag nennt nur, was vom Standard (Params()) abweicht; der Rest bleibt Standard.
PRESETS = {
    "Restaurant für Paare": {},
    "Gleicher Mix, große Gruppen": {"t2": 4, "t4": 4, "dist": "gross"},
    "Mit Kombination": {"dist": "gross", "combine": "beliebig"},
    "Mit Umbauzeit": {"dist": "gross", "combine": "beliebig", "extra": 20.0},
    "Mit Warteschlange": {"patience": 15.0},
    "Robuster Mix": {"t2": 6, "t4": 3, "t6": 0, "dist": "gross", "combine": "beliebig"},
}
PRESET_HELP = {
    "Restaurant für Paare": "Vier Zweier- und vier Viertische, 24 Plätze, überwiegend Paare und kleine Gruppen: der Mix passt zur Nachfrage.",
    "Gleicher Mix, große Gruppen": "Derselbe Tischmix, aber die Gäste kommen überwiegend in Gruppen ab vier: die Annahme über die Gruppen war falsch, die Tische passen nicht mehr.",
    "Mit Kombination": "Wie zuvor, aber zwei freie Tische dürfen für eine Gruppe zusammengestellt werden (Standard-Umbauzeit 10 Minuten je kombinierter Gruppe).",
    "Mit Umbauzeit": "Kombination mit 20 Minuten Umbau je kombinierter Gruppe: der Zuwachs schrumpft, ein Teil bleibt.",
    "Mit Warteschlange": "Gäste warten bis zu 15 Minuten auf einen Tisch: mehr Gäste werden bedient, der Mix zählt weiter.",
    "Robuster Mix": "Sechs Zweier- und drei Viertische mit Kombination: der Mix, bei dem der beste Mix für die eingetretene Verteilung am wenigsten mehr Gäste bedient (exakte Messreihe, 24 Plätze).",
}
