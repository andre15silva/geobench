"""Query a model over a grid, one latitude row per request, resumable.

    python -m geobench.run --grid global  --model claude-opus-5-5 --backend cli
    python -m geobench.run --grid everest --model claude-opus-5-5 --backend api
"""
import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from . import backends
from .grids import GRIDS
from .prompts import parse, render

ROOT = Path(__file__).resolve().parent.parent
TASK = {"global": "surface", "everest": "elevation"}


def task_for(grid_key: str) -> str:
    return TASK.get(grid_key, "relief")


def results_path(grid_name: str, model: str) -> Path:
    return ROOT / "results" / grid_name / f"{model}.jsonl"


def load(grid, model: str):
    """-> (is_land, elevation) float arrays shaped like the grid (NaN = no answer)."""
    land = np.full(grid.shape, np.nan)
    elev = np.full(grid.shape, np.nan)
    p = results_path(grid.name, model)
    for line in p.read_text().splitlines() if p.exists() else []:
        r = json.loads(line)
        for j, (l, e) in enumerate(r["answers"]):
            land[r["row"], j] = np.nan if l is None else float(l)
            elev[r["row"], j] = np.nan if e is None else e
    return land, elev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", choices=GRIDS, required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--backend", choices=["api", "cli"], default="api")
    ap.add_argument("--effort", help="cli backend: --effort level")
    ap.add_argument("--thinking", type=int, help="api backend: thinking budget tokens")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--retries", type=int, default=3)
    a = ap.parse_args()

    grid = GRIDS[a.grid]()
    task = task_for(a.grid)
    kw = {"effort": a.effort} if a.backend == "cli" else {"thinking": a.thinking}
    call = backends.make(a.backend, a.model, **{k: v for k, v in kw.items() if v})
    out = results_path(grid.name, a.model)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["row"] for l in out.read_text().splitlines()} if out.exists() else set()
    todo = [(i, pts) for i, pts in grid.rows() if i not in done]
    print(f"{a.model} on {grid.name}: {len(todo)} rows to go ({len(done)} cached)")
    lock = threading.Lock()

    def work(i, pts):
        best = None
        for attempt in range(a.retries):
            try:
                r = call(render(task, pts))
            except Exception as e:  # noqa: BLE001 - network/CLI hiccups: back off and retry
                print(f"  row {i} attempt {attempt}: {e}")
                time.sleep(5 * 2**attempt)
                continue
            ans = parse(task, r["text"], len(pts))
            got = sum(x[0] is not None for x in ans)
            if best is None or got > best[0]:
                best = (got, ans, r)
            if got == len(pts):
                break
        if best is None:
            return i, 0
        got, ans, r = best
        rec = {"row": i, "lat": pts[0][0], "answers": ans, "raw": r["text"],
               "usage": r.get("usage"), "cost_usd": r.get("cost_usd"), "backend": a.backend,
               "effort": a.effort, "thinking": a.thinking}
        with lock, out.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        return i, got

    with ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(work, i, pts) for i, pts in todo]
        for k, f in enumerate(as_completed(futs), 1):
            i, got = f.result()
            print(f"  [{k}/{len(todo)}] row {i}: {got}/{grid.shape[1]} answered", flush=True)


if __name__ == "__main__":
    main()
