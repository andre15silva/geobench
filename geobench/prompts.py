"""Prompts and response parsing.

Two tasks:
  * ``surface``   - "Land or Water?" plus, for land, the elevation (global grid).
  * ``elevation`` - elevation only, for points known to be on land (Everest close-up).

Coordinates are batched one latitude row per request; every point has an index so
answers can be matched back even if the model skips or reorders one.
"""
import re

SYSTEM = (
    "You are being tested on your internal geographic knowledge. You have no tools, "
    "no internet access and no maps: answer from memory only. Always give your best "
    "guess - never refuse or leave a point out."
)

SURFACE = """For each coordinate below (latitude, longitude in decimal degrees, WGS84), decide whether the point lies on Land or Water (ocean, sea or large lake). For Land points, also estimate the elevation of the surface in metres above sea level (for ice sheets and glaciers, the ice surface).

Answer with exactly one line per point, in this format and nothing else:
<index> L <elevation_m>
<index> W

{points}"""

ELEVATION = """For each coordinate below (latitude, longitude in decimal degrees, WGS84), estimate the elevation of the ground surface in metres above sea level (for glaciers, the ice surface). Be as precise as you can - neighbouring points are about 1 km apart.

Answer with exactly one line per point, in this format and nothing else:
<index> <elevation_m>

{points}"""


def render(task: str, pts) -> str:
    body = "\n".join(f"{k}: {lat:.4f}, {lon:.4f}" for k, (lat, lon) in enumerate(pts))
    return (SURFACE if task == "surface" else ELEVATION).format(points=body)


_NUM = r"(-?\d[\d,]*(?:\.\d+)?)"
_SURF = re.compile(rf"^\s*(\d+)\s*[:.)]?\s*(L|W|land|water)\b[ \t:=,~]*{_NUM}?", re.I | re.M)
_ELEV = re.compile(rf"^\s*(\d+)\s*[:.)]?\s+[~≈]?\s*{_NUM}", re.M)


def _f(s):
    return None if s is None else float(s.replace(",", ""))


def parse(task: str, text: str, n: int):
    """-> list of n (is_land: bool|None, elevation: float|None)."""
    out = [(None, None)] * n
    if task == "surface":
        for m in _SURF.finditer(text):
            k = int(m.group(1))
            if 0 <= k < n:
                land = m.group(2)[0].upper() == "L"
                out[k] = (land, _f(m.group(3)) if land else None)
    else:
        for m in _ELEV.finditer(text):
            k = int(m.group(1))
            if 0 <= k < n:
                out[k] = (True, _f(m.group(2)))
    return out
