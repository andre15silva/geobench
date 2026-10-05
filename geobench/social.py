"""Phone-legible figures for an X/Twitter thread (2x resolution, mostly 16:9).

    python -m geobench.social      # -> figures/twitter/*.png
"""
import json

import matplotlib.pyplot as plt
import numpy as np

from .grids import RANGES, everest_grid, global_grid
from .render import ACCENT, BG, FIG, INK, MODELS, MUTED, _surface, _terrain
from .render_ranges import _cmap, _exag, _hillshade, _limits, _load_range, _ticks
from .run import ROOT, load
from .truth import dem_patch, ground_truth

OUT = FIG / "twitter"
W, H, DPI = 16, 9, 150  # 2400 x 1350 px
HANDLE = "no tools, no internet · github.com/andre15silva/geobench"


def _fig(w=W, h=H):
    return plt.figure(figsize=(w, h), facecolor=BG)


def _title(fig, title, sub=None):
    h = fig.get_figheight()
    fig.text(0.03, 1 - 0.32 / h, title, fontsize=34, weight="bold", va="top", color=INK)
    if sub:
        fig.text(0.03, 1 - 1.0 / h, sub, fontsize=17, va="top", color=MUTED)


def _foot(fig, text=HANDLE):
    fig.text(0.97, 0.025, text, fontsize=12, ha="right", color=MUTED)


def _save(fig, name):
    fig.savefig(OUT / name, dpi=DPI, facecolor=BG)
    plt.close(fig)
    print("wrote", OUT / name)


def _3d(fig, rect, lats, lons, z, label, vmin, vmax, exag, zticks, cmap=None, sub=None):
    ax = fig.add_axes(rect, projection="3d", computed_zorder=False)
    _surface(ax, lats, lons, z, "", vmin, vmax, exag=exag, zticks=zticks, cmap=cmap)
    ax.set_zticks([])  # 3-D tick labels collide with the terrain at this size; the subtitle gives the scale
    fig.text(rect[0] + 0.02, rect[1] + rect[3] - 0.005, label, fontsize=24, weight="bold", va="top", color=INK)
    if sub:
        fig.text(rect[0] + 0.02, rect[1] + rect[3] - 0.06, sub, fontsize=16, va="top", color=MUTED)
    return ax


# ----------------------------------------------------------------------------- 1 · Everest hero
def everest(scores):
    g = everest_grid()
    lat_r, lon_r = (g.lats[-1], g.lats[0]), (g.lons[0], g.lons[-1])
    hl, hn, hz = dem_patch(lat_r, lon_r, z=12, res=400)
    best = min(scores["everest"], key=lambda m: scores["everest"][m]["mae"])
    s = scores["everest"][best]
    pred = load(g, best)[1]
    fig = _fig()
    _title(fig, "Mount Everest, drawn by Claude from memory",
           f"{MODELS[best]} gave the elevation of 2,576 points, 1 km apart, as text · no images, no tools, no internet")
    _3d(fig, [0.03, 0.03, 0.47, 0.78], hl, hn, hz, "Real", 2000, 9000, 2.2, (3000, 5000, 7000, 9000),
        sub="SRTM satellite elevation")
    _3d(fig, [0.5, 0.03, 0.5, 0.78], g.lats, g.lons, pred, MODELS[best], 2000, 9000, 2.2, (3000, 5000, 7000, 9000),
        sub=f"off by {s['mae']:.0f} m on average · summit on the right spot")
    _foot(fig)
    _save(fig, "1_everest.png")


# ----------------------------------------------------------------------------- 2 · globe
def globe(scores):
    g = global_grid()
    land_t, elev_t = ground_truth(g)
    cmap = _terrain()
    cmap.set_bad("#141413")
    panels = [("Real", land_t.astype(float), np.where(land_t, elev_t, np.nan), None)]
    for m in MODELS:
        lp, ep = load(g, m)
        panels.append((MODELS[m], lp, np.where(lp == 1, ep, np.nan), scores["global"][m]))
    fig = _fig()
    _title(fig, "How 4 blind Claudes see the Earth — and its mountains",
           "“Land or water? If land, how high?” at every 2° · 16,200 points · black = water")
    w, h, x0, y0, gx, gy = 0.305, 0.34, 0.03, 0.06, 0.02, 0.07
    for k, (name, lp, ep, s) in enumerate(panels):
        r, c = divmod(k, 3)
        ax = fig.add_axes([x0 + c * (w + gx), y0 + (1 - r) * (h + gy), w, h])
        im = ax.imshow(ep, cmap=cmap, vmin=0, vmax=6000, extent=[-180, 180, -90, 90], interpolation="nearest")
        ax.set_axis_off()
        lab = name if s is None else f"{name}   {s['land_acc']:.1%} · ±{s['elev_mae']:.0f} m"
        ax.text(0, 1.03, lab, transform=ax.transAxes, fontsize=19, weight="bold", color=INK)
    # sixth cell: legend + how to read
    cax = fig.add_axes([x0 + 2 * (w + gx) + 0.02, y0 + 0.2, w - 0.04, 0.035])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal", extend="max")
    cb.set_label("elevation (m)", fontsize=14, color=INK)
    cb.ax.tick_params(labelsize=12)
    fig.text(x0 + 2 * (w + gx) + 0.02, y0 + 0.1,
             "% = land/water accuracy\n± = average elevation error\n(area-weighted)",
             fontsize=14, color=MUTED, va="top")
    _foot(fig)
    _save(fig, "2_globe.png")


# ----------------------------------------------------------------------------- 3 · one range per image
def range_pair(key, model="claude-opus-5-5"):
    r, g, elev_t, (hl, hn, hz), preds, scores = _load_range(key)
    vmin, vmax = _limits(hz, preds)
    exag = _exag(g.lats, g.lons, vmin, vmax)
    s = scores[model]
    fig = _fig()
    _title(fig, f"The {r.title}, drawn by Claude from memory" if not r.title.startswith("Rocky")
           else "The Rocky Mountains, drawn by Claude from memory",
           f"{r.continent} · a {r.size_km[0]} km window, one elevation guess every 5 km · "
           f"{exag:.0f}× vertical exaggeration")
    _3d(fig, [0.03, 0.03, 0.47, 0.8], hl, hn, hz, "Real", vmin, vmax, exag, _ticks(vmax), cmap=_cmap(r))
    _3d(fig, [0.5, 0.03, 0.5, 0.8], g.lats, g.lons, preds[model], MODELS[model], vmin, vmax, exag, _ticks(vmax),
        cmap=_cmap(r), sub=f"off by {s['mae']:.0f} m on average")
    _foot(fig)
    _save(fig, f"3_range_{key}.png")


# ----------------------------------------------------------------------------- 4 · all ranges, portrait
def ranges_grid(models=("claude-opus-5-5", "claude-fable-5-1")):
    datas = [_load_range(k) for k in RANGES]
    cols = 1 + len(models)
    fig = _fig(10.8, 13.5)  # 4:5 -> 1620 x 2025 px
    h = fig.get_figheight()
    fig.text(0.04, 1 - 0.3 / h, "One mountain range per continent", fontsize=28, weight="bold", va="top")
    fig.text(0.04, 1 - 0.85 / h, "Real terrain vs. Claude from memory · ~5 km grid · ▲ = famous peaks",
             fontsize=14, color=MUTED, va="top")
    top, bottom, left, right = 1 - 1.55 / h, 0.03, 0.04, 0.98
    rh = (top - bottom) / len(datas)
    cw = (right - left) / cols
    for c, name in enumerate(["Real"] + [MODELS[m] for m in models]):
        fig.text(left + c * cw + cw / 2, top + 0.006, name, ha="center", fontsize=17, weight="bold")
    for i, (r, g, elev_t, (hl, hn, hz), preds, scores) in enumerate(datas):
        vmin, vmax = _limits(hz, preds)
        y = top - (i + 1) * rh
        for c, m in enumerate([None] + list(models)):
            ax = fig.add_axes([left + c * cw + 0.005, y + 0.022, cw - 0.01, rh - 0.03])
            z = elev_t if m is None else preds[m]
            ax.imshow(_hillshade(z, vmin, vmax, _cmap(r)), interpolation="nearest",
                      extent=[g.lons.min(), g.lons.max(), g.lats.min(), g.lats.max()],
                      aspect=1 / np.cos(np.radians(np.mean(g.lats))))
            for la, lo in r.peaks.values():
                ax.plot(lo, la, "^", color=ACCENT, ms=6, mec="k", mew=0.5)
            ax.set_axis_off()
            lab = f"{r.title.split(' (')[0]} · {r.continent}" if m is None else f"±{scores[m]['mae']:.0f} m"
            ax.text(0.5, -0.02, lab, transform=ax.transAxes, ha="center", va="top", fontsize=12.5,
                    color=INK if m is None else MUTED)
    _save(fig, "4_ranges_grid.png")


# ----------------------------------------------------------------------------- 5 · scoreboard
def scoreboard(scores):
    order = list(MODELS)
    rng = [k for k in scores if k.startswith("range_")]
    metrics = [
        ("Land vs. water\naccuracy (globe)", {m: 100 * scores["global"][m]["land_acc"] for m in order}, "%", True),
        ("Elevation error\nglobe, 2° grid", {m: scores["global"][m]["elev_mae"] for m in order}, " m", False),
        ("Elevation error\nEverest, 1 km grid", {m: scores["everest"][m]["mae"] for m in order}, " m", False),
        ("Elevation error\n7 ranges, 5 km grid", {m: np.mean([scores[k][m]["mae"] for k in rng])
                                                   for m in order if all(m in scores[k] for k in rng)}, " m", False),
    ]
    fig = _fig()
    _title(fig, "Scoreboard", "Lower error is better · Haiku 4.5 was not run on the mountain ranges")
    pw, gap, x0 = 0.185, 0.03, 0.12
    for j, (title, vals, unit, higher) in enumerate(metrics):
        ax = fig.add_axes([x0 + j * (pw + gap), 0.1, pw, 0.62])
        names = [m for m in order if m in vals]
        best = (max if higher else min)(names, key=lambda m: vals[m])
        y = np.arange(len(order))[::-1]
        for yi, m in zip(y, order):
            if m not in vals:
                ax.text(0, yi, "  not run", va="center", fontsize=14, color=MUTED)
                continue
            ax.barh(yi, vals[m], height=0.62, color=ACCENT if m == best else "#bdb8ad")
            ax.text(vals[m], yi, f" {vals[m]:.1f}{unit}" if unit == "%" else f" {vals[m]:.0f}{unit}",
                    va="center", fontsize=16, color=INK, weight="bold" if m == best else "normal")
        top = max(vals.values())
        ax.set_xlim(0, top * 1.45)
        ax.set_ylim(-0.6, len(order) - 0.4)
        ax.set_yticks(y)
        ax.set_yticklabels([MODELS[m] for m in order] if j == 0 else [], fontsize=16, color=INK)
        ax.tick_params(left=False, bottom=False, labelbottom=False)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.axvline(0, color=INK, lw=1)
        ax.set_title(title, loc="left", fontsize=17, color=INK, pad=12)
    _foot(fig)
    _save(fig, "5_scoreboard.png")


# ----------------------------------------------------------------------------- 6 · method
def method():
    from playwright.sync_api import sync_playwright

    svg = (FIG / "evaluation_pipeline.svg").read_text()
    html = (f"<html><body style='margin:0;background:{BG};display:flex;align-items:center;justify-content:center;"
            f"width:1387px;height:780px'>{svg.replace('<svg ', '<svg width=1240 height=780 ', 1)}</body></html>")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        pg = b.new_page(viewport={"width": 1387, "height": 780}, device_scale_factor=2)
        pg.set_content(html)
        pg.screenshot(path=str(OUT / "6_method.png"))
        b.close()
    print("wrote", OUT / "6_method.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scores = json.loads((ROOT / "results" / "scores.json").read_text())
    everest(scores)
    globe(scores)
    for k in RANGES:
        range_pair(k)
    ranges_grid()
    scoreboard(scores)
    try:
        method()
    except Exception as e:  # playwright/chromium missing: the SVG is still in figures/
        print("skipped method diagram:", e)


if __name__ == "__main__":
    main()
