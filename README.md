# GeoBench — how blind Claudes see the Earth (and its mountains)

A replication and extension of [@celestepoasts' "How blind Claudes see the Earth"](https://x.com/celestepoasts/status/2103232383139057950):
models are asked "Land or Water?" at every 2° of the globe **and, for land, the elevation in metres**.
A second experiment zooms in on **Mount Everest**: the model is asked for the elevation of
every point on a ~1 km grid, and its answers are rendered in 3-D next to the real terrain.

The models get **no tools, no internet, no images** — only coordinates as text.

<!-- RESULTS -->

## How it works

| | Global | Everest |
|---|---|---|
| Grid | 2° cell centres, 90 × 180 = 16,200 points | 0.01° (~1 km), 27.75–28.20°N × 86.60–87.15°E, 46 × 56 = 2,576 points |
| Question | Land or Water? If land, elevation (m) | Elevation (m) |
| Truth | Natural Earth 1:10m land minus lakes; elevation from AWS Terrain Tiles z6 | AWS Terrain Tiles z12 (SRTM ~30 m) |
| Metric | area-weighted (cos lat) land accuracy; elevation MAE/RMSE/r on points both truth and model call land | MAE, RMSE, bias, r; height & position of the predicted summit |

* **Batched by row.** Each request holds one latitude row (180 points global, 56 points
  Everest), each point indexed so answers are matched even if one is skipped. Unanswered
  points count as wrong (global) / are left as holes (Everest). The original asked point by point;
  batching cuts the number of calls ~100×, but lets a model see its neighbours *within a row*
  (not across rows — you can see the row-wise "streaks" in weaker models' Everest surfaces).
* **No internet.** `--backend api` calls the Messages API with no `tools`. `--backend cli`
  runs `claude -p` with `--tools ""`, `--strict-mcp-config`, `--setting-sources ""`, our own
  system prompt, in an empty temp dir, and rejects any reply that took more than one turn.
* Prompts are in [`geobench/prompts.py`](geobench/prompts.py).

## Reproduce

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...                 # or use --backend cli with a logged-in Claude Code
python -m geobench.run --grid everest --model claude-opus-5-5 --backend api
python -m geobench.run --grid global  --model claude-opus-5-5 --backend api --workers 16
python -m geobench.render                    # -> figures/*.png, figures/everest_3d.html, results/scores.json
```

Runs are resumable (`results/<grid>/<model>.jsonl` holds every raw reply). Add models to
`MODELS` in `geobench/render.py` to include them in the figures.
