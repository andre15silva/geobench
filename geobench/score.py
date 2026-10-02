"""Metrics. Global numbers are area-weighted (cos latitude); unanswered points count as wrong."""
import numpy as np


def _w(grid):
    return np.broadcast_to(np.cos(np.radians(grid.lats))[:, None], grid.shape)


def global_scores(grid, land_true, elev_true, land_pred, elev_pred) -> dict:
    w = _w(grid)
    answered = ~np.isnan(land_pred)
    correct = answered & ((land_pred == 1) == land_true)
    both = land_true & (land_pred == 1) & ~np.isnan(elev_pred)
    err = (elev_pred - elev_true)[both]
    ww = w[both]
    return {
        "land_acc": float((w * correct).sum() / w.sum()),
        "answered": float(answered.mean()),
        "elev_n": int(both.sum()),
        "elev_mae": float((np.abs(err) * ww).sum() / ww.sum()),
        "elev_rmse": float(np.sqrt((err**2 * ww).sum() / ww.sum())),
        "elev_bias": float((err * ww).sum() / ww.sum()),
        "elev_r": float(np.corrcoef(elev_pred[both], elev_true[both])[0, 1]),
    }


def everest_scores(grid, elev_true, elev_pred) -> dict:
    ok = ~np.isnan(elev_pred)
    err = (elev_pred - elev_true)[ok]
    ip = np.unravel_index(np.nanargmax(elev_pred), grid.shape)
    it = np.unravel_index(np.argmax(elev_true), grid.shape)
    # great-circle-ish distance (km) between predicted and true highest grid point
    dlat = (grid.lats[ip[0]] - grid.lats[it[0]]) * 111.2
    dlon = (grid.lons[ip[1]] - grid.lons[it[1]]) * 111.2 * np.cos(np.radians(grid.lats[it[0]]))
    return {
        "answered": float(ok.mean()),
        "mae": float(np.abs(err).mean()),
        "rmse": float(np.sqrt((err**2).mean())),
        "bias": float(err.mean()),
        "r": float(np.corrcoef(elev_pred[ok], elev_true[ok])[0, 1]),
        "max_pred": float(elev_pred[ip]),
        "max_pred_at": (float(grid.lats[ip[0]]), float(grid.lons[ip[1]])),
        "peak_offset_km": float(np.hypot(dlat, dlon)),
    }
