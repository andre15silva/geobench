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


def box_blur(a: np.ndarray, k: int) -> np.ndarray:
    """k x k moving average (k odd), edges padded by replication."""
    if k <= 1:
        return a
    from numpy.lib.stride_tricks import sliding_window_view

    p = np.pad(a, k // 2, mode="edge")
    return sliding_window_view(p, (k, k)).mean(axis=(-1, -2))


def effective_resolution_km(elev_true, mae: float, step_km: float, max_cells: int = 61) -> float:
    """Blur width (km) at which the *real* DEM, box-blurred, is as wrong as the model.

    Small = the model knows fine detail; large = it only knows the broad shape. inf if
    even a max_cells-wide blur of the truth beats the model.
    """
    prev_k, prev = 1, 0.0
    for k in range(3, max_cells + 1, 2):
        cur = float(np.abs(box_blur(elev_true, k) - elev_true).mean())
        if cur >= mae:  # linear interpolation between blur widths
            return step_km * (prev_k + (k - prev_k) * (mae - prev) / (cur - prev))
        prev_k, prev = k, cur
    return float("inf")


def range_scores(grid, elev_true, elev_pred, peaks: dict, step_km: float) -> dict:
    ok = ~np.isnan(elev_pred)
    err = (elev_pred - elev_true)[ok]
    mae = float(np.abs(err).mean())
    ip = np.unravel_index(np.nanargmax(elev_pred), grid.shape)
    lat_p, lon_p = grid.lats[ip[0]], grid.lons[ip[1]]
    # which named peak is the model's highest point closest to?
    def km(a, b):
        return float(np.hypot((a[0] - b[0]) * 110.57, (a[1] - b[1]) * 111.32 * np.cos(np.radians(a[0]))))
    near = min(peaks, key=lambda n: km(peaks[n], (lat_p, lon_p)))
    return {
        "answered": float(ok.mean()), "mae": mae, "rmse": float(np.sqrt((err**2).mean())),
        "bias": float(err.mean()), "r": float(np.corrcoef(elev_pred[ok], elev_true[ok])[0, 1]),
        "effective_resolution_km": effective_resolution_km(elev_true, mae, step_km),
        "max_pred": float(elev_pred[ip]), "max_true": float(elev_true.max()),
        "max_pred_near": near, "max_pred_offset_km": km(peaks[near], (lat_p, lon_p)),
    }
