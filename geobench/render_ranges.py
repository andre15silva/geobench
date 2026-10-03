"""Figures for the famous-mountain-range experiment (one ~400 x 300 km window per continent)."""
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LightSource

from .grids import RANGES, range_grid
from .render import ACCENT, BG, FIG, MODELS, SEA, _header, _ice, _surface, _terrain, _xy_km, available
from .run import load
from .score import range_scores
from .truth import range_truth

STEP_KM = 5.0
OUT = FIG / "ranges"


def _limits(hz, preds):
    top = max([float(np.nanmax(hz))] + [float(np.nanmax(p)) for p in preds.values()])
    return 0.0, float(np.ceil(top / 500) * 500)


def _exag(lats, lons, vmin, vmax):
    """Vertical exaggeration that makes the relief box ~14% as tall as the window is wide."""
    x, _ = _xy_km(lats, lons)
    return 0.14 * x[-1] / ((vmax - vmin) / 1000)


def _ticks(vmax):
    step = 1000 if vmax <= 5000 else 2000
    return list(range(step, int(vmax) + 1, step))


def _cmap(r):
    return _ice() if r.truth == "etopo1" else _terrain()


def _hillshade(z, vmin, vmax, cmap):
    zz = np.where(np.isnan(z), 0, z)
    rgb = LightSource(azdeg=315, altdeg=40).shade(zz, cmap=cmap, vert_exag=3, dx=STEP_KM * 1000,
                                                    dy=STEP_KM * 1000, blend_mode="soft", vmin=vmin, vmax=vmax)
    rgb[zz <= 0] = SEA
    rgb[np.isnan(z)] = (0.5, 0.5, 0.5, 1)
    return rgb


def _load_range(key):
    r = RANGES[key]
    g = range_grid(key, STEP_KM)
    models = available(g)
    if not models:
        return None
    elev_t, (hl, hn, hz) = range_truth(r, g)
    hl, hn, hz = hl[::2], hn[::2], hz[::2, ::2]  # ~2.5 km: detailed, but not a bed of needles
    preds = {m: load(g, m)[1] for m in models}
    scores = {m: range_scores(g, elev_t, preds[m], r.peaks, STEP_KM) for m in models}
    return r, g, elev_t, (hl, hn, hz), preds, scores


def _real_label(r):
    return "Real (ETOPO1 ice surface)" if r.truth == "etopo1" else "Real (SRTM / Terrain Tiles)"


def _per_range(data):
    r, g, elev_t, (hl, hn, hz), preds, scores = data
    vmin, vmax = _limits(hz, preds)
    exag = _exag(g.lats, g.lons, vmin, vmax)
    panels = [(_real_label(r), hl, hn, hz)] + [
        (f"{MODELS[m]}   MAE {scores[m]['mae']:.0f} m · r={scores[m]['r']:.2f}", g.lats, g.lons, preds[m])
        for m in preds]
    cols = 2
    rows = -(-len(panels) // cols)
    fig = plt.figure(figsize=(14, 5.2 * rows + 1.2))
    _header(fig, f"{r.title}, as remembered by Claude",
            f"{r.continent} · {g.shape[0] * g.shape[1]:,} points on a ~{STEP_KM:g} km grid, "
            f"{g.lats.min():.2f}–{g.lats.max():.2f}°, {g.lons.min():.2f}–{g.lons.max():.2f}° "
            f"· no tools, no internet · {exag:.0f}× vertical exaggeration")
    for k, (title, la, lo, z) in enumerate(panels):
        ax = fig.add_subplot(rows, cols, k + 1, projection="3d", computed_zorder=False)
        _surface(ax, la, lo, z, title, vmin, vmax, exag=exag, zticks=_ticks(vmax), cmap=_cmap(r))
    fig.subplots_adjust(top=1 - 1.2 / (5.2 * rows + 1.2), bottom=0.0, left=0.0, right=1.0, wspace=0.0, hspace=0.0)
    fig.savefig(OUT / f"{r.key}_3d.png", dpi=110)
    plt.close(fig)


def _overview(datas, models):
    """Rows = ranges, columns = real + each model. Kind = '3d' or 'map'."""
    n_rows, n_cols = len(datas), len(models) + 1
    for kind in ("3d", "map"):
        fig = plt.figure(figsize=(4.6 * n_cols, 3.5 * n_rows + 1.3))
        _header(fig, "The world’s mountains, as remembered by Claude",
                "One famous range per continent · elevation asked on a ~5 km grid · no tools, no internet "
                "· “eff. res.” = blur of the real DEM that is as wrong as the model")
        for i, (r, g, elev_t, (hl, hn, hz), preds, scores) in enumerate(datas):
            vmin, vmax = _limits(hz, preds)
            exag = _exag(g.lats, g.lons, vmin, vmax)
            cells = [("Real", None)] + [(MODELS[m], m) for m in models]
            for j, (name, m) in enumerate(cells):
                idx = i * n_cols + j + 1
                if m is not None and m not in preds:
                    continue
                if m is None:
                    lab = f"{r.title} · {r.continent}"
                else:
                    s = scores[m]
                    er = s["effective_resolution_km"]
                    lab = f"{name} · MAE {s['mae']:.0f} m · eff. res. {er:.0f} km" if np.isfinite(er) \
                        else f"{name} · MAE {s['mae']:.0f} m"
                if kind == "3d":
                    ax = fig.add_subplot(n_rows, n_cols, idx, projection="3d", computed_zorder=False)
                    if m is None:
                        _surface(ax, hl, hn, hz, lab, vmin, vmax, exag=exag, zticks=_ticks(vmax), cmap=_cmap(r))
                    else:
                        _surface(ax, g.lats, g.lons, preds[m], lab, vmin, vmax, exag=exag, zticks=_ticks(vmax), cmap=_cmap(r))
                    for t in ax.texts:
                        t.set_fontsize(10.5)
                else:
                    ax = fig.add_subplot(n_rows, n_cols, idx)
                    z = elev_t if m is None else preds[m]
                    ext = [g.lons.min(), g.lons.max(), g.lats.min(), g.lats.max()]
                    ax.imshow(_hillshade(z, vmin, vmax, _cmap(r)), extent=ext, interpolation="nearest",
                              aspect=1 / np.cos(np.radians(np.mean(g.lats))))  # square km
                    for pk, (la, lo) in r.peaks.items():
                        ax.plot(lo, la, "^", color=ACCENT, ms=5, mec="k", mew=0.5)
                    ax.set_title(lab, loc="left", fontsize=10.5)
                    ax.set_xticks([]), ax.set_yticks([])
        top = 1 - 1.3 / (3.5 * n_rows + 1.3)
        if kind == "3d":
            fig.subplots_adjust(top=top, bottom=0.0, left=0.0, right=1.0, wspace=0.0, hspace=0.0)
        else:
            fig.subplots_adjust(top=top - 0.01, bottom=0.01, left=0.01, right=0.99, wspace=0.04, hspace=0.25)
        fig.savefig(FIG / f"ranges_{'overview_3d' if kind == '3d' else 'overview_maps'}.png", dpi=100)
        plt.close(fig)


def _plotly(datas, models):
    """One interactive page: pick a range from the dropdown, drag to orbit."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    names = ["Real"] + [MODELS[m] for m in models]
    cols = 2
    rows = -(-len(names) // cols)
    fig = make_subplots(rows=rows, cols=cols, specs=[[{"type": "surface"}] * cols] * rows,
                        subplot_titles=names, horizontal_spacing=0.01, vertical_spacing=0.04)
    cs = [[0, "#3d6b35"], [0.15, "#8fa65a"], [0.3, "#c9b27a"], [0.45, "#9c7a55"], [0.6, "#7a6a5e"],
          [0.7, "#a8a29a"], [0.8, "#e6e3de"], [1, "#ffffff"]]
    per_range, buttons = len(names), []
    for i, (r, g, elev_t, (hl, hn, hz), preds, scores) in enumerate(datas):
        vmin, vmax = _limits(hz, preds)
        for j, m in enumerate([None] + models):
            la, lo, z = (hl, hn, hz) if m is None else (g.lats, g.lons, preds.get(m))
            if z is None:
                z = np.full((len(la), len(lo)), np.nan)
            x, y = _xy_km(la, lo)
            ice = [[0, "#9fb4c8"], [0.5, "#d9e2ea"], [1, "#ffffff"]]
            fig.add_trace(go.Surface(x=x, y=y, z=z, colorscale=ice if r.truth == "etopo1" else cs, cmin=vmin, cmax=vmax, showscale=False,
                                     visible=(i == 0), name=names[j],
                                     hovertemplate="%{z:.0f} m<extra>" + names[j] + "</extra>"),
                          row=j // cols + 1, col=j % cols + 1)
        vis = [False] * (len(datas) * per_range)
        vis[i * per_range:(i + 1) * per_range] = [True] * per_range
        label = f"{r.continent}: {r.title}"
        sub = " · ".join(f"{MODELS[m]} MAE {scores[m]['mae']:.0f} m" for m in models if m in scores)
        layout = {f"scene{'' if k == 0 else k + 1}.zaxis.range": [vmin, vmax] for k in range(per_range)}
        layout["title.text"] = f"{label}<br><sup>{sub}</sup>"
        buttons.append(dict(label=label, method="update", args=[{"visible": vis}, layout]))
    cam = dict(eye=dict(x=-1.1, y=-1.5, z=0.9))
    for k in range(per_range):
        key = "scene" if k == 0 else f"scene{k + 1}"
        fig.layout[key].update(aspectmode="manual", aspectratio=dict(x=1.3, y=1.0, z=0.3), camera=cam,
                               xaxis=dict(visible=False), yaxis=dict(visible=False),
                               zaxis=dict(range=buttons[0]["args"][1]["scene.zaxis.range"], title="m"))
    fig.update_layout(height=470 * rows, margin=dict(l=0, r=0, t=90, b=0), paper_bgcolor=BG,
                      title=buttons[0]["args"][1]["title.text"],
                      updatemenus=[dict(buttons=buttons, x=1.0, xanchor="right", y=1.08, yanchor="top")])
    fig.write_html(FIG / "ranges_3d.html", include_plotlyjs="cdn")


def render_ranges() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    datas = [d for d in (_load_range(k) for k in RANGES) if d is not None]
    if not datas:
        return {}
    models = [m for m in MODELS if any(m in d[4] for d in datas)]
    for d in datas:
        _per_range(d)
    _overview(datas, models)
    _plotly(datas, models)
    return {f"range_{d[0].key}": d[5] for d in datas}
