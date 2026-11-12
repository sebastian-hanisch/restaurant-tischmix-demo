"""Plotly-Abbildungen. Alle Achsen sind gesperrt (fixedrange), damit Touch-Geräte beim Scrollen nicht am Diagramm hängen bleiben."""

import plotly.graph_objects as go

import rtm_constants as C


def lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _base(fig, height=340, legend=True):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="rgba(0,0,0,0)", showlegend=legend, legend=dict(orientation="h", y=-0.25))
    return lock_axes(fig)


def build_floor(snapshot, tables, cols=C.GRID_COLS):
    """Ein Abend im Grundriss: freie Tische hell, besetzte Tische grün, kombinierte Tische blau; Zahl = Größe der Gruppe, Name des Tisches = Platzzahl."""
    n = len(tables)
    rows = (n + cols - 1) // cols
    z = [[None] * cols for _ in range(rows)]
    text = [[""] * cols for _ in range(rows)]
    for i, size in enumerate(tables):
        r, c = divmod(i, cols)
        group, partner = snapshot[i]
        if group == 0:
            z[r][c] = 0
            text[r][c] = f"{size}er<br>frei"
        elif partner >= 0:
            z[r][c] = 2
            text[r][c] = f"{size}er<br>{group} Gäste (mit Tisch {partner + 1})"
        else:
            z[r][c] = 1
            text[r][c] = f"{size}er<br>{group} Gäste"
    scale = [[0.0, "#e3efe9"], [0.34, "#e3efe9"], [0.34, C.COLOR_GOOD], [0.67, C.COLOR_GOOD], [0.67, C.COLOR_NEUTRAL], [1.0, C.COLOR_NEUTRAL]]
    fig = go.Figure(go.Heatmap(z=z, zmin=0, zmax=2, colorscale=scale, showscale=False, text=text, texttemplate="%{text}", xgap=4, ygap=4, hoverinfo="skip"))
    fig.update_yaxes(autorange="reversed", showticklabels=False)
    fig.update_xaxes(showticklabels=False)
    return _base(fig, height=120 + 70 * rows, legend=False)


def build_compare(items, title="Gäste je Stunde"):
    """Balken mit Standardfehler: items = Liste (Beschriftung, Wert, Standardfehler, Farbe)."""
    fig = go.Figure()
    for label, value, se, color in items:
        fig.add_trace(go.Bar(name=label, x=[label], y=[value], error_y=dict(type="data", array=[se], visible=se > 0), marker_color=color,
                             text=[f"{value:.2f}".replace(".", ",")], textposition="outside", hovertemplate=f"{label}: %{{y:.2f}}<extra></extra>"))
    fig.update_yaxes(title_text=title, rangemode="tozero")
    fig.update_xaxes(type="category")
    return _base(fig, legend=False)


def build_occupancy(study):
    """Tischbelegung gegen Gastbelegung."""
    fig = go.Figure()
    for name, value, color in (("Belegte Tischplätze", study.seat_occupancy, C.COLOR_NEUTRAL), ("Sitzende Gäste", study.guest_occupancy, C.COLOR_GOOD)):
        fig.add_trace(go.Bar(name=name, x=[name], y=[100 * value], marker_color=color, text=[f"{100 * value:.0f} %"], textposition="outside"))
    fig.update_yaxes(title_text="Anteil der Plätze (%)", range=[0, 100])
    fig.update_xaxes(type="category")
    return _base(fig, height=280, legend=False)


def build_regret(matrix: dict, dists):
    """Bedauern in Prozent (so viel mehr Gäste bedient der beste Mix): Zeile = Verteilung, für die der Mix gewählt wurde, Spalte = wirkliche Verteilung."""
    z = [[matrix["loss"][(a, w)] for w in dists] for a in dists]
    fig = go.Figure(go.Heatmap(z=z, x=list(dists), y=list(dists), colorscale=[[0, "#e3efe9"], [1, C.COLOR_BAD]], zmin=0, zmax=max(60.0, max(max(r) for r in z)), showscale=False,
                               text=[[f"{v:.1f} %".replace(".", ",") for v in r] for r in z], texttemplate="%{text}", xgap=3, ygap=3,
                               hovertemplate="gewählt für %{y}, wirklich %{x}: der beste Mix bedient %{text} mehr Gäste<extra></extra>"))
    fig.update_yaxes(autorange="reversed", title_text="Mix gewählt für")
    fig.update_xaxes(title_text="wirkliche Verteilung", side="top")
    return _base(fig, height=300, legend=False)


def build_geduld(rows):
    """Gäste je Stunde nach Geduld, ohne und mit Kombination (Mix und Verteilung passend: erste drei Zeilen je Gruppe der Messreihe)."""
    fig = go.Figure()
    for combine, color, name in (("aus", C.COLOR_GRAY, "ohne Kombination"), ("beliebig", C.COLOR_GOOD, "mit Kombination (10 Minuten Umbau)")):
        sel = [r for r in rows if r["combine"] == combine and r["assumed"] == r["dist"]]
        xs = [f"{int(p)} min" for p in (0.0, 15.0, 30.0)]
        ys = [sum(r["gph"] for r in sel if r["patience"] == p) / len([r for r in sel if r["patience"] == p]) for p in (0.0, 15.0, 30.0)]
        fig.add_trace(go.Bar(name=name, x=xs, y=ys, marker_color=color))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="Gäste je Stunde (Mittel über drei Verteilungen)", rangemode="tozero")
    fig.update_xaxes(title_text="Geduld der Gäste")
    return _base(fig)


def build_reserve(studies, w, c):
    """Bediente Gäste und Nettowert je Planungsfaktor; der beste Faktor des Nettowerts ist markiert."""
    fs = [s.f for s in studies]
    served = [s.served for s in studies]
    net = [s.net(w, c) for s in studies]
    best = fs[net.index(max(net))]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=fs, y=served, mode="lines+markers", name="bediente Gäste", line=dict(color=C.COLOR_GRAY, width=3)))
    fig.add_trace(go.Scatter(x=fs, y=net, mode="lines+markers", name="Nettowert", line=dict(color=C.COLOR_GOOD, width=3)))
    fig.add_vline(x=best, line=dict(color=C.COLOR_BAD, dash="dot"))
    fig.update_xaxes(title_text="Planungsfaktor f (geplante Dauer / mittlere Dauer)")
    fig.update_yaxes(title_text="Gäste je Abend", rangemode="tozero")
    return _base(fig)
