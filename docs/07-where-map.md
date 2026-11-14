# Where map

The person asks where around a place a variable is changing. The answer is a grid of NASA cells around the place, each coloured by its own trend. Priority P1. Estimate 2 hours.

## Input and output

`WhereQ(point, variable, window)`. A country or place in the draft becomes its centre point.

`Result.detail`:

```python
{
  "box": [lat_min, lat_max, lon_min, lon_max],
  "cell_size": [dlat, dlon],
  "cells": [ {"lat": float, "lon": float, "slope_per_decade": float, "p": float, "clear": bool, "mean": float} ],
  "counts": {"rising": int, "falling": int, "clear": int, "total": int},
  "strongest": {"lat", "lon", "slope_per_decade", "bearing": str},   # "north-east", or "close to the centre" within 0.6°
  "nearest": {"lat", "lon", "slope_per_decade", "p"}
}
```

## Steps

1. Build a 4° × 4° box centred on the point rounded to 0.5°, clamped to the globe.
2. Fetch the box with `get_grid` (POWER monthly regional, one parameter per request). Each cell becomes an annual series.
3. Run `trend_test` on each cell with at least `T.min_years` years.
4. Headline: "{n_clear} of {total} cells around {place} show a clear {rise}. The strongest is {bearing}."
5. Chart: a `cells` chart that the map layer draws as coloured squares. The colour scale is symmetric around 0. Warm colours mean a rise when the variable's `warm_up` is true.

## Rules

- No false-discovery correction across cells. The method says this in one sentence: with 64 cells, about 3 can look clear by chance.
- Variables without `point_param` cannot be mapped. The card disables "where" for them.

## Acceptance

- With `EB_OFFLINE=1`, `WhereQ(Phnom Penh, heat)` returns a cell list that covers the box, with counts that sum to `total`.
- A point at latitude 89 clamps the box to the pole and still returns cells.

## Reference

`~/earth-buddy/earth-buddy-analyst/earthbuddy/analyses.py` function `where`, and `web/charts.js` function `trendMap`.
