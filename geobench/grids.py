"""Sampling grids. Points are cell centres so the poles/antimeridian are never sampled twice."""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Grid:
    name: str
    lats: np.ndarray  # 1-D, north -> south
    lons: np.ndarray  # 1-D, west -> east

    @property
    def shape(self):
        return (len(self.lats), len(self.lons))

    def rows(self):
        """Yield (row_index, [(lat, lon), ...]) for every latitude row."""
        for i, lat in enumerate(self.lats):
            yield i, [(float(lat), float(lon)) for lon in self.lons]


def global_grid(step: float = 2.0) -> Grid:
    lats = np.arange(90 - step / 2, -90, -step)
    lons = np.arange(-180 + step / 2, 180, step)
    return Grid(f"global_{step:g}deg", np.round(lats, 4), np.round(lons, 4))


# Everest summit (2020 China-Nepal survey position) and a window that also contains
# Lhotse, Nuptse, Makalu, Cho Oyu, the Khumbu glacier and the Tibetan plateau edge.
EVEREST = (27.9881, 86.9250)


def everest_grid(step: float = 0.01, lat_range=(27.75, 28.20), lon_range=(86.60, 87.15)) -> Grid:
    lats = np.arange(lat_range[1], lat_range[0] - 1e-9, -step)
    lons = np.arange(lon_range[0], lon_range[1] + 1e-9, step)
    return Grid(f"everest_{step:g}deg", np.round(lats, 4), np.round(lons, 4))


GRIDS = {"global": global_grid, "everest": everest_grid}


# ----------------------------------------------------------------------------- mountain ranges
@dataclass(frozen=True)
class Range:
    key: str
    title: str
    continent: str
    center: tuple  # (lat, lon)
    size_km: tuple = (400, 300)  # (width, height)
    peaks: dict = None
    truth: str = "tiles"  # "tiles" (Terrain Tiles z10) or "etopo1" (ice surface, for Antarctica)


RANGES = {r.key: r for r in [
    Range("himalaya", "Himalaya", "Asia", (28.3, 86.0), (520, 300),
          {"Everest": (27.9881, 86.9250), "Kangchenjunga": (27.7025, 88.1475), "Makalu": (27.8897, 87.0883),
           "Cho Oyu": (28.0942, 86.6608), "Shishapangma": (28.3525, 85.7797), "Manaslu": (28.5497, 84.5597),
           "Annapurna": (28.5961, 83.8203)}),
    Range("alps", "Alps", "Europe", (46.35, 8.9), peaks={
        "Mont Blanc": (45.8326, 6.8652), "Matterhorn": (45.9763, 7.6586), "Monte Rosa": (45.9369, 7.8668),
        "Eiger": (46.5776, 8.0053), "Piz Bernina": (46.3822, 9.9081)}),
    Range("rockies", "Rocky Mountains (Colorado)", "North America", (39.3, -106.0), peaks={
        "Mt Elbert": (39.1178, -106.4454), "Longs Peak": (40.2549, -105.6160),
        "Pikes Peak": (38.8409, -105.0423), "Maroon Bells": (39.0708, -106.9890)}),
    Range("andes", "Andes (Aconcagua)", "South America", (-32.8, -70.0), peaks={
        "Aconcagua": (-32.6532, -70.0109), "Mercedario": (-31.9790, -70.1120), "Tupungato": (-33.3580, -69.7700)}),
    Range("atlas", "High Atlas", "Africa", (31.3, -7.0), peaks={
        "Toubkal": (31.0597, -7.9150), "M'Goun": (31.5050, -6.4500)}),
    Range("southern_alps", "Southern Alps", "Oceania", (-43.5, 170.5), peaks={
        "Aoraki / Mt Cook": (-43.5950, 170.1418), "Mt Aspiring": (-44.3814, 168.7275)}),
    Range("ellsworth", "Ellsworth Mountains", "Antarctica", (-78.5, -86.0), truth="etopo1", peaks={
        "Vinson Massif": (-78.5254, -85.6171), "Mt Tyree": (-78.4000, -86.0500)}),
]}


def range_grid(key: str, step_km: float = 5.0) -> Grid:
    """~step_km square cells: the longitude step widens with latitude."""
    r = RANGES[key]
    lat0, lon0 = r.center
    dlat = step_km / 110.57
    dlon = step_km / (111.32 * np.cos(np.radians(lat0)))
    ny, nx = round(r.size_km[1] / step_km) + 1, round(r.size_km[0] / step_km) + 1
    lats = lat0 + dlat * (np.arange(ny)[::-1] - (ny - 1) / 2)
    lons = lon0 + dlon * (np.arange(nx) - (nx - 1) / 2)
    return Grid(f"range_{key}", np.round(lats, 4), np.round(lons, 4))


for _k in RANGES:
    GRIDS[_k] = (lambda k: lambda: range_grid(k))(_k)
