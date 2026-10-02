"""Figures: global land/altitude maps and the Everest 3-D comparison.

    python -m geobench.render            # renders every model that has results
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LightSource, ListedColormap  # noqa: E402

from .grids import everest_grid, global_grid  # noqa: E402
from .run import ROOT, load, results_path  # noqa: E402
from .score import everest_scores, global_scores  # noqa: E402
from .truth import dem_patch, ground_truth  # noqa: E402

FIG = ROOT / "figures"
BG, INK, MUTED, ACCENT = "#faf9f5", "#1f1e1d", "#6b6a66", "#d97757"
MODELS = {  # display order
    "claude-haiku-4-5-20251001": "Haiku 4.5",
    "claude-sonnet-5-5": "Sonnet 5.5",
    "claude-opus-5-5": "Opus 5.5",
    "claude-fable-5-1": "Fable 5.1",
}
PEAKS = {"Everest": (27.9881, 86.9250), "Lhotse": (27.9617, 86.9333),
         "Makalu": (27.8897, 87.0883), "Cho Oyu": (28.0942, 86.6608)}
EVEREST_Z = 12

plt.rcParams.update({"figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
                     "text.color": INK, "axes.labelcolor": MUTED, "xtick.color": MUTED,
                     "ytick.color": MUTED, "font.size": 11})


def available(grid):
    return [m for m in MODELS if results_path(grid.name, m).exists()]


def _terrain():
    """Hypsometric tints tuned for 0-9000 m: lowland green, brown slopes, grey rock, snow."""
    from matplotlib.colors import LinearSegmentedColormap

    stops = [(0.0, "#3d6b35"), (0.15, "#8fa65a"), (0.3, "#c9b27a"), (0.45, "#9c7a55"),
             (0.6, "#7a6a5e"), (0.7, "#a8a29a"), (0.8, "#e6e3de"), (1.0, "#ffffff")]
    return LinearSegmentedColormap.from_list("hypso", stops)


def _header(fig, title, sub):
    fig.text(0.02, 0.975, title, fontsize=22, weight="bold", va="top")
    fig.text(0.02, 0.925, sub, fontsize=11, color=MUTED, va="top")


# ----------------------------------------------------------------------------- global
def render_global():
    g = global_grid()
    land_t, elev_t = ground_truth(g)
    models = available(g)
    if not models:
        return {}
    ext = [-180, 180, -90, 90]
    scores, panels = {}, [("Real", land_t.astype(float), np.where(land_t, elev_t, np.nan))]
    for m in models:
        lp, ep = load(g, m)
        scores[m] = global_scores(g, land_t, elev_t, lp, ep)
        panels.append((MODELS[m], lp, np.where(lp == 1, ep, np.nan)))

    n = len(panels)
    cols = 2 if n <= 4 else 3
    rows = -(-n // cols)
    # 1) land / water, as in the original
    fig, axs = plt.subplots(rows, cols, figsize=(6.2 * cols, 3.6 * rows + 1.1), squeeze=False)
    fig.subplots_adjust(top=1 - 1.25 / (3.6 * rows + 1.1), bottom=0.04, left=0.03, right=0.97, hspace=0.35, wspace=0.08)
    _header(fig, f"How {len(models)} blind Claudes see the Earth",
            "Asked “Land or Water?” at every 2° of the globe · 16,200 points · no tools, no internet · white = “Land”, grey = no answer")
    for ax, (name, lp, _) in zip(axs.flat, panels):
        img = np.where(np.isnan(lp), 0.5, lp)
        ax.imshow(img, cmap="gray", vmin=0, vmax=1, extent=ext, interpolation="nearest")
        acc = "" if name == "Real" else f"   {scores[_key(name)]['land_acc']:.1%}"
        ax.set_title(f"{name}{acc}", loc="left", fontsize=14)
        ax.set_axis_off()
    for ax in axs.flat[n:]:
        ax.set_axis_off()
    fig.savefig(FIG / "global_land.png", dpi=130)
    plt.close(fig)

    # 2) altitude
    cmap = _terrain()
    cmap.set_bad("#141413")
    fig, axs = plt.subplots(rows, cols, figsize=(6.2 * cols, 3.6 * rows + 1.6), squeeze=False)
    fig.subplots_adjust(top=1 - 1.25 / (3.6 * rows + 1.6), bottom=0.13, left=0.03, right=0.97, hspace=0.35, wspace=0.08)
    _header(fig, f"How {len(models)} blind Claudes see the Earth’s relief",
            "Elevation each model gives for the points it calls Land · black = “Water”, grey = no answer · MAE on points both truth and model call land (area-weighted)")
    for ax, (name, lp, ep) in zip(axs.flat, panels):
        im = ax.imshow(ep, cmap=cmap, vmin=0, vmax=6000, extent=ext, interpolation="nearest")
        ax.imshow(np.where(np.isnan(lp), 0.5, np.nan), cmap="gray", vmin=0, vmax=1, extent=ext,
                  interpolation="nearest")  # unanswered = grey
        lab = "" if name == "Real" else (f"   MAE {scores[_key(name)]['elev_mae']:.0f} m · r={scores[_key(name)]['elev_r']:.2f}")
        ax.set_title(f"{name}{lab}", loc="left", fontsize=14)
        ax.set_axis_off()
    for ax in axs.flat[n:]:
        ax.set_axis_off()
    cax = fig.add_axes([0.3, 0.07, 0.4, 0.018])
    fig.colorbar(im, cax=cax, orientation="horizontal", label="elevation (m)", extend="max")
    fig.text(0.98, 0.01, "truth: Natural Earth 1:10m land mask · ETOPO1 ice surface",
             ha="right", fontsize=9, color=MUTED)
    fig.savefig(FIG / "global_altitude.png", dpi=130)
    plt.close(fig)
    return scores


def _key(name):
    return next(k for k, v in MODELS.items() if v == name)


# ----------------------------------------------------------------------------- everest
def _xy_km(lats, lons):
    lat0 = np.mean(lats)
    x = (np.asarray(lons) - lons[0]) * 111.32 * np.cos(np.radians(lat0))
    y = (np.asarray(lats) - lats[-1]) * 110.57
    return x, y


def _surface(ax, lats, lons, z, title, vmin, vmax):
    x, y = _xy_km(lats, lons)
    X, Y = np.meshgrid(x, y)
    hole = np.isnan(z)
    zz = np.where(hole, np.nanmean(z), z)
    ls = LightSource(azdeg=315, altdeg=35)
    rgb = ls.shade(zz, cmap=_terrain(), vert_exag=0.02, blend_mode="soft", vmin=vmin, vmax=vmax)
    rgb[hole] = (0, 0, 0, 0)  # unanswered points: leave a hole rather than invent terrain
    zz = np.where(hole, np.nan, zz)
    stride = max(1, len(lats) // 200)
    ax.plot_surface(X, Y, zz, facecolors=rgb, rstride=stride, cstride=stride,
                    linewidth=0, antialiased=False, shade=False)
    ax.set_box_aspect((x[-1], y[0], (vmax - vmin) / 1000 * 2.2), zoom=1.25)  # 2.2x vertical exaggeration
    ax.set_zlim(vmin, vmax)
    ax.view_init(elev=32, azim=-115)
    ax.text2D(0.03, 0.97, title, transform=ax.transAxes, fontsize=13, va="top")
    ax.set_xticks([]), ax.set_yticks([])
    ax.set_zticks([3000, 5000, 7000, 9000])
    ax.tick_params(axis="z", labelsize=8, pad=0)
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.set_pane_color((0, 0, 0, 0))
        a.line.set_color((0, 0, 0, 0.15))


def render_everest():
    g = everest_grid()
    _, elev_t = ground_truth(g, EVEREST_Z)
    models = available(g)
    if not models:
        return {}
    lat_r, lon_r = (g.lats[-1], g.lats[0]), (g.lons[0], g.lons[-1])
    hl, hn, hz = dem_patch(lat_r, lon_r, z=EVEREST_Z, res=400)
    scores, preds = {}, {}
    for m in models:
        preds[m] = load(g, m)[1]
        scores[m] = everest_scores(g, elev_t, preds[m])
    vmin, vmax = 2000, 9000
    sub = (f"Asked for the elevation of {g.shape[0] * g.shape[1]:,} points on a 0.01° (~1 km) grid, "
           f"{lat_r[0]:.2f}–{lat_r[1]:.2f}°N, {lon_r[0]:.2f}–{lon_r[1]:.2f}°E · no tools, no internet · 2.2× vertical exaggeration")

    # 1) 3-D: real vs every model
    n = len(models) + 1
    cols = min(n, 3)
    rows = -(-n // cols)
    fig = plt.figure(figsize=(6.4 * cols, 5.0 * rows + 1.2))
    _header(fig, "Mount Everest, as remembered by Claude", sub)
    panels = [("Real (SRTM, ~30 m)", hl, hn, hz)] + [
        (f"{MODELS[m]}   MAE {scores[m]['mae']:.0f} m · peak {scores[m]['max_pred']:.0f} m", g.lats, g.lons, preds[m])
        for m in models]
    for k, (title, la, lo, z) in enumerate(panels):
        ax = fig.add_subplot(rows, cols, k + 1, projection="3d", computed_zorder=False)
        _surface(ax, la, lo, z, title, vmin, vmax)
    fig.subplots_adjust(top=1 - 1.2 / (5.0 * rows + 1.2), bottom=0.0, left=0.0, right=1.0, wspace=0.0, hspace=0.0)
    fig.savefig(FIG / "everest_3d.png", dpi=130)
    plt.close(fig)

    # 2) Single big head-to-head with the best model
    best = min(models, key=lambda m: scores[m]["mae"])
    fig = plt.figure(figsize=(16, 7.4))
    _header(fig, f"Everest: {MODELS[best]} from memory vs. the real thing", sub)
    for k, (title, la, lo, z) in enumerate([panels[0], (MODELS[best] + " (no tools)", g.lats, g.lons, preds[best])]):
        ax = fig.add_subplot(1, 2, k + 1, projection="3d", computed_zorder=False)
        _surface(ax, la, lo, z, title, vmin, vmax)
    fig.subplots_adjust(top=0.88, bottom=0.0, left=0.0, right=1.0, wspace=0.0)
    fig.savefig(FIG / "everest_3d_best.png", dpi=130)
    plt.close(fig)

    # 3) 2-D maps with peak markers, plus error maps
    fig, axs = plt.subplots(2, n, figsize=(4.2 * n, 8.4), squeeze=False)
    fig.subplots_adjust(top=0.86, bottom=0.04, left=0.02, right=0.93, wspace=0.08, hspace=0.25)
    _header(fig, "Everest region: elevation (top) and error vs. SRTM (bottom)", sub)
    ext = [lon_r[0] - 0.005, lon_r[1] + 0.005, lat_r[0] - 0.005, lat_r[1] + 0.005]
    for k, (name, z) in enumerate([("Real", elev_t)] + [(MODELS[m], preds[m]) for m in models]):
        ax = axs[0, k]
        im = ax.imshow(z, cmap=_terrain(), vmin=vmin, vmax=vmax, extent=ext, interpolation="nearest")
        ax.contour(g.lons, g.lats, elev_t, levels=[5000, 6000, 7000, 8000], colors="k", linewidths=0.4, alpha=0.35)
        for pk, (la, lo) in PEAKS.items():
            ax.plot(lo, la, "^", color=ACCENT, ms=6, mec="k", mew=0.5)
            if k == 0:
                ax.annotate(pk, (lo, la), xytext=(4, 4), textcoords="offset points", fontsize=8)
        ax.set_title(name, loc="left")
        ax.set_xticks([]), ax.set_yticks([])
        ax2 = axs[1, k]
        if k == 0:
            ax2.set_axis_off()
            continue
        er = ax2.imshow(z - elev_t, cmap="RdBu_r", vmin=-2500, vmax=2500, extent=ext, interpolation="nearest")
        m = models[k - 1]
        ax2.set_title(f"MAE {scores[m]['mae']:.0f} m · bias {scores[m]['bias']:+.0f} m · r={scores[m]['r']:.2f}", loc="left", fontsize=10)
        ax2.set_xticks([]), ax2.set_yticks([])
    fig.colorbar(im, cax=fig.add_axes([0.945, 0.5, 0.01, 0.34]), label="elevation (m)")
    if n > 1:
        fig.colorbar(er, cax=fig.add_axes([0.945, 0.06, 0.01, 0.34]), label="model − real (m)")
    fig.savefig(FIG / "everest_maps.png", dpi=130)
    plt.close(fig)

    _plotly(g, hl, hn, hz, models, preds, scores)
    return scores


def _plotly(g, hl, hn, hz, models, preds, scores):
    """Interactive side-by-side 3-D surfaces (drag to orbit)."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    panels = [("Real (SRTM)", hl, hn, hz)] + [(MODELS[m], g.lats, g.lons, preds[m]) for m in models]
    cols = min(len(panels), 3)
    rows = -(-len(panels) // cols)
    fig = make_subplots(rows=rows, cols=cols, specs=[[{"type": "surface"}] * cols] * rows,
                        subplot_titles=[p[0] + ("" if i == 0 else f" · MAE {scores[models[i - 1]]['mae']:.0f} m")
                                        for i, p in enumerate(panels)],
                        horizontal_spacing=0.01, vertical_spacing=0.05)
    for k, (name, la, lo, z) in enumerate(panels):
        x, y = _xy_km(la, lo)
        s = max(1, len(la) // 160)
        fig.add_trace(go.Surface(x=x[::s], y=y[::s], z=z[::s, ::s], colorscale=[[0, "#3d6b35"], [0.15, "#8fa65a"], [0.3, "#c9b27a"], [0.45, "#9c7a55"], [0.6, "#7a6a5e"], [0.7, "#a8a29a"], [0.8, "#e6e3de"], [1, "#ffffff"]], cmin=2000, cmax=9000,
                                 showscale=False, name=name, hovertemplate="%{z:.0f} m<extra>" + name + "</extra>"),
                      row=k // cols + 1, col=k % cols + 1)
    cam = dict(eye=dict(x=-1.1, y=-1.5, z=0.9))
    for k in range(len(panels)):
        key = "scene" if k == 0 else f"scene{k + 1}"
        fig.layout[key].update(aspectmode="manual", aspectratio=dict(x=1.08, y=1.0, z=0.3), camera=cam,
                               xaxis=dict(visible=False), yaxis=dict(visible=False),
                               zaxis=dict(range=[2000, 9000], title="m"))
    fig.update_layout(height=520 * rows, margin=dict(l=0, r=0, t=40, b=0), paper_bgcolor=BG,
                      title="Mount Everest: real vs. Claude from memory (drag to rotate)")
    fig.write_html(FIG / "everest_3d.html", include_plotlyjs="cdn")


def main():
    FIG.mkdir(exist_ok=True)
    out = {"global": render_global(), "everest": render_everest()}
    (ROOT / "results" / "scores.json").write_text(json.dumps(out, indent=2))
    for k, v in out.items():
        for m, s in v.items():
            print(k, MODELS[m], {a: (round(b, 3) if isinstance(b, float) else b) for a, b in s.items()})


if __name__ == "__main__":
    main()
