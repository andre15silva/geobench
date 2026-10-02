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
