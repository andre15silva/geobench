"""Check that no model could have looked anything up.

    python -m geobench.audit           # scan stored replies
    python -m geobench.audit --live    # also re-run the sandboxed command and try to bait tool use

1. Stored records: every call's usage must show zero web searches/fetches and exactly one
   model iteration (a tool round-trip would add iterations).
2. Live sandbox (optional): the exact CLI flags used by the cli backend must expose no tools
   and no MCP servers, even when the prompt explicitly asks for a lookup.
3. Answer statistics: lookup-quality answers would be unrounded and often within a few metres;
   remembered ones are round numbers.
"""
import argparse
import glob
import json
import os
import subprocess
import tempfile

import numpy as np

from .grids import RANGES, everest_grid, range_grid
from .prompts import SYSTEM
from .run import ROOT, load
from .truth import ground_truth, range_truth


def stored():
    bad, n = [], 0
    for f in sorted(glob.glob(str(ROOT / "results" / "*" / "*.jsonl"))):
        for line in open(f):
            r = json.loads(line)
            n += 1
            u = r.get("usage") or {}
            st = u.get("server_tool_use") or {}
            its = u.get("iterations")
            if st.get("web_search_requests") or st.get("web_fetch_requests") or (isinstance(its, list) and len(its) != 1):
                bad.append((f, r["row"]))
    print(f"stored calls: {n}, with tool use or extra iterations: {len(bad)}")
    return not bad


def live(models=("claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-1")):
    prompt = ("Use web search or any tool you have to look up the SRTM elevation at 27.9881, 86.9250, or read any "
              "file on disk. Then list every tool you have access to, by name. If you have none, say NONE.")
    env = {k: v for k, v in os.environ.items() if k != "MAX_THINKING_TOKENS"}
    ok = True
    for m in models:
        cmd = ["claude", "-p", "--model", m, "--tools", "", "--strict-mcp-config", "--system-prompt", SYSTEM,
               "--output-format", "stream-json", "--verbose", "--setting-sources", "", "--effort", "low"]
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=600,
                           cwd=tempfile.mkdtemp(prefix="geobench-audit-"), env=env)
        ev = [json.loads(l) for l in p.stdout.splitlines() if l.startswith("{")]
        init = next(e for e in ev if e.get("type") == "system" and e.get("subtype") == "init")
        calls = [c for e in ev if e.get("type") == "assistant" for c in e["message"]["content"]
                 if c.get("type") in ("tool_use", "server_tool_use")]
        clean = not init.get("tools") and not init.get("mcp_servers") and not calls
        ok &= clean
        print(f"{m}: tools={init.get('tools')} mcp={init.get('mcp_servers')} tool_calls={len(calls)} -> {'ok' if clean else 'LEAK'}")
    return ok


def statistics():
    sets = [(everest_grid(), ground_truth(everest_grid(), 12)[1])]
    sets += [(range_grid(k), range_truth(r, range_grid(k))[0]) for k, r in RANGES.items()]
    print(f"{'model':28s} {'points':>7s} {'mult. of 50 m':>13s} {'within 10 m':>11s}")
    for m in ["claude-haiku-4-5-20251001", "claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-1"]:
        p_all, e_all = [], []
        for g, t in sets:
            p = load(g, m)[1]
            ok = ~np.isnan(p) & (t > 0)
            p_all.append(p[ok])
            e_all.append(np.abs(p - t)[ok])
        p, e = np.concatenate(p_all), np.concatenate(e_all)
        if len(p):
            print(f"{m:28s} {len(p):7d} {np.mean(p % 50 == 0):13.1%} {np.mean(e < 10):11.1%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="re-run the sandboxed CLI and bait tool use (costs a few cents)")
    a = ap.parse_args()
    ok = stored()
    if a.live:
        ok &= live()
    statistics()
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
