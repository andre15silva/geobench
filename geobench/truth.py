"""Ground truth: Natural Earth 1:10m land mask (minus lakes) plus elevation.

Global elevation is point-sampled from ETOPO1 *Ice Surface* (1 arc-minute, via NOAA
ERDDAP), so Antarctica and Greenland are measured at the top of the ice. Terrain Tiles
cannot be used there: they carry bedrock under the ice sheets.

High-resolution elevation (Everest) comes from the public `elevation-tiles-prod` Terrarium tiles (SRTM / GMTED /
ETOPO1 / NED composite, https://registry.opendata.aws/terrain-tiles/), decoded as
    h = R*256 + G + B/256 - 32768   [metres]
"""
import io
import math
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
from PIL import Image

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache"
TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
NE_URL = "https://naciscdn.org/naturalearth/10m/physical/{name}.zip"


# ----------------------------------------------------------------------------- land mask
def _ne_shapes(name: str):
    import shapefile
    from shapely.geometry import shape

    d = CACHE / name
    if not (d / f"{name}.shp").exists():
        d.mkdir(parents=True, exist_ok=True)
        r = requests.get(NE_URL.format(name=name), timeout=120)
        r.raise_for_status()
        zipfile.ZipFile(io.BytesIO(r.content)).extractall(d)
    return [shape(s.__geo_interface__) for s in shapefile.Reader(str(d / f"{name}.shp")).shapes()]


def land_mask(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Boolean (len(lats), len(lons)) array, True where the point is on land (lakes = water)."""
    import shapely
    from shapely import STRtree

    lon2, lat2 = np.meshgrid(lons, lats)
    pts = shapely.points(lon2.ravel(), lat2.ravel())

    def hits(name):
        polys = _ne_shapes(name)
        idx = STRtree(polys).query(pts, predicate="intersects")[0]
        out = np.zeros(len(pts), bool)
        out[idx] = True
        return out

    return (hits("ne_10m_land") & ~hits("ne_10m_lakes")).reshape(lat2.shape)


# ----------------------------------------------------------------------------- elevation
def _tile_xy(lat, lon, z):
    n = 2**z
    x = (lon + 180.0) / 360.0 * n
    lr = math.radians(max(min(lat, 85.0511), -85.0511))
    y = (1.0 - math.asinh(math.tan(lr)) / math.pi) / 2.0 * n
    return x, y


def _tile(z, x, y) -> np.ndarray:
    p = CACHE / "terrarium" / str(z) / str(x) / f"{y}.npy"
    if p.exists():
        return np.load(p)
    for attempt in range(5):  # S3 occasionally answers 500/503
        r = requests.get(TILE_URL.format(z=z, x=x, y=y), timeout=60)
        if r.status_code < 500:
            break
        time.sleep(2**attempt)
    r.raise_for_status()
    a = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"), dtype=np.float32)
    h = (a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768).astype(np.float32)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.save(p, h)
    return h


def elevation(lats: np.ndarray, lons: np.ndarray, z: int) -> np.ndarray:
    """Bilinearly sampled elevation (m) at every grid point, from zoom-level `z` tiles.

    Beyond the Web-Mercator limit (|lat| > 85.05) the edge row is used, which is fine
    for 2-degree sampling of the polar ice/ocean.
    """
    lon2, lat2 = np.meshgrid(lons, lats)
    fx, fy = np.vectorize(lambda a, b: _tile_xy(a, b, z))(lat2, lon2)
    n = 2**z
    px, py = fx * 256 - 0.5, np.clip(fy * 256 - 0.5, 0, n * 256 - 1.001)
    x0, y0 = np.floor(px).astype(int), np.floor(py).astype(int)
    ymax = n * 256 - 1
    need = {(int(gx // 256) % n, int(min(gy, ymax) // 256))
            for dx in (0, 1) for dy in (0, 1)
            for gx, gy in zip((x0 + dx).ravel(), (y0 + dy).ravel())}
    with ThreadPoolExecutor(16) as ex:
        tiles = dict(zip(need, ex.map(lambda t: _tile(z, *t), need)))

    def at(gx, gy):
        gx = gx % (n * 256)
        gy = np.clip(gy, 0, n * 256 - 1)
        out = np.empty(gx.shape, np.float32)
        for k, (a, b) in enumerate(zip(gx.ravel(), gy.ravel())):
            out.flat[k] = tiles[(a // 256, b // 256)][b % 256, a % 256]
        return out

    wx, wy = px - x0, py - y0
    return ((1 - wx) * (1 - wy) * at(x0, y0) + wx * (1 - wy) * at(x0 + 1, y0)
            + (1 - wx) * wy * at(x0, y0 + 1) + wx * wy * at(x0 + 1, y0 + 1))


ETOPO_URL = ("https://coastwatch.pfeg.noaa.gov/erddap/griddap/etopo180.csv?"
             "altitude%5B({la0}):{st}:({la1})%5D%5B({lo0}):{st}:({lo1})%5D")


def etopo1(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """ETOPO1 ice-surface elevation at the nodes of a regular grid (spacing a multiple of 1')."""
    step = round(abs(lats[1] - lats[0]) * 60)
    assert step == round(abs(lons[1] - lons[0]) * 60), "need a square grid"
    url = ETOPO_URL.format(la0=lats.min(), la1=lats.max(), lo0=lons.min(), lo1=lons.max(), st=step)
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    rows = [l.split(",") for l in r.text.splitlines()[2:]]
    look = {(round(float(a), 4), round(float(b), 4)): float(c) for a, b, c in rows}
    return np.array([[look[(round(float(la), 4), round(float(lo), 4))] for lo in lons] for la in lats], np.float32)


def etopo1_box(lat_range, lon_range, stride: int = 1):
    """ETOPO1 ice surface over a lat/lon box: (lats south->north, lons, elev[lat, lon])."""
    p = CACHE / f"etopo1_{lat_range[0]:.3f}_{lat_range[1]:.3f}_{lon_range[0]:.3f}_{lon_range[1]:.3f}_{stride}.npz"
    if p.exists():
        d = np.load(p)
        return d["lats"], d["lons"], d["elev"]
    pad = 2 / 60  # make sure the box covers the requested range after snapping to the 1' grid
    url = ETOPO_URL.format(la0=lat_range[0] - pad, la1=lat_range[1] + pad,
                           lo0=lon_range[0] - pad, lo1=lon_range[1] + pad, st=stride)
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    a = np.array([[float(v) for v in l.split(",")] for l in r.text.splitlines()[2:]])
    lats, lons = np.unique(a[:, 0]), np.unique(a[:, 1])
    elev = a[:, 2].reshape(len(lats), len(lons)).astype(np.float32)  # ERDDAP order: lat-major, ascending
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez(p, lats=lats, lons=lons, elev=elev)
    return lats, lons, elev


def bilinear(src_lats, src_lons, src, lats, lons) -> np.ndarray:
    """Sample a regular ascending-lat/lon raster at every (lat, lon) node of a target grid."""
    fi = np.interp(lats, src_lats, np.arange(len(src_lats)))
    fj = np.interp(lons, src_lons, np.arange(len(src_lons)))
    i0 = np.clip(np.floor(fi).astype(int), 0, len(src_lats) - 2)
    j0 = np.clip(np.floor(fj).astype(int), 0, len(src_lons) - 2)
    wi, wj = (fi - i0)[:, None], (fj - j0)[None, :]
    I, J = i0[:, None], j0[None, :]
    return ((1 - wi) * (1 - wj) * src[I, J] + (1 - wi) * wj * src[I, J + 1]
            + wi * (1 - wj) * src[I + 1, J] + wi * wj * src[I + 1, J + 1])


def range_truth(rng, grid, res: int = 300):
    """(elev at grid points, (lats, lons, hi-res patch)) for a mountain range; sea clipped to 0."""
    p = CACHE / f"truth_{grid.name}_{rng.truth}.npz"
    lat_r, lon_r = (grid.lats.min(), grid.lats.max()), (grid.lons.min(), grid.lons.max())
    if p.exists():
        d = np.load(p)
        return d["elev"], (d["hl"], d["hn"], d["hz"])
    if rng.truth == "etopo1":
        bl, bn, bz = etopo1_box(lat_r, lon_r)
        elev = bilinear(bl, bn, bz, grid.lats, grid.lons)
        hl, hn = np.linspace(lat_r[1], lat_r[0], res), np.linspace(lon_r[0], lon_r[1], res)
        hz = bilinear(bl, bn, bz, hl, hn)
    else:
        elev = elevation(grid.lats, grid.lons, 10)
        hl, hn, hz = dem_patch(lat_r, lon_r, z=10, res=res)
    elev, hz = np.maximum(elev, 0), np.maximum(hz, 0)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez(p, elev=elev, hl=hl, hn=hn, hz=hz)
    return elev, (hl, hn, hz)


def dem_patch(lat_range, lon_range, z: int = 12, res: int = 400):
    """A regular lat/lon DEM raster (res x res) for high-resolution 3-D rendering."""
    lats = np.linspace(lat_range[1], lat_range[0], res)
    lons = np.linspace(lon_range[0], lon_range[1], res)
    return lats, lons, elevation(lats, lons, z)


def ground_truth(grid, elev_zoom: int | None = None):
    """Cached (land_mask, elevation) arrays. elev_zoom=None -> ETOPO1, else Terrain Tiles at that zoom."""
    p = CACHE / f"truth_{grid.name}_{'etopo1' if elev_zoom is None else f'z{elev_zoom}'}.npz"
    if p.exists():
        d = np.load(p)
        return d["land"], d["elev"]
    land = land_mask(grid.lats, grid.lons)
    elev = etopo1(grid.lats, grid.lons) if elev_zoom is None else elevation(grid.lats, grid.lons, elev_zoom)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez(p, land=land, elev=elev)
    return land, elev
