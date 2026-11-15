# Where map

The person asks where around a place a variable is changing. The answer is a grid of NASA cells around the place, each coloured by its own trend. Priority P1. Estimate 2 hours.

## Input and output

`WhereQ(point, variable, window)`. A country or place in the draft becomes its centre point.

`Result.detail`:

```python
{
  "box": [lat_min, lat_max, lon_min, lon_max],
  "cell_size": [dlat, dlon],
  "cells": [ {"lat": float, "lon": float, "slope_per_decade": float, "p": float,
              "q": float,        # Benjamini-Hochberg across the map's cells
              "clear": bool,     # stats.field_test
              "mean": float} ],
  "counts": {"rising": int, "falling": int, "flat": int,
             "clear": int,       # cells clear after stats.field_test
             "raw": int,         # cells whose own level is clear
             "total": int},
  "strongest": {"lat", "lon", "slope_per_decade", "bearing": str},   # the largest observed change; "north-east", or "close to the centre" within 0.6°
  "nearest": {"lat", "lon", "slope_per_decade", "p"}
}
```

## Steps

1. Build a 4° × 4° box centred on the point rounded to 0.5°, clamped to the globe.
2. Fetch the box with `get_grid` (POWER monthly regional, one parameter per request). Each cell becomes an annual series.
3. Run `trend_test` on each cell with at least `T.min_years` years.
4. Run `stats.field_test` on every fit (`docs/03-stats.md`). A cell is clear when its own level is `clear` and its Benjamini-Hochberg q across the map is under `T.field_q`.
5. Verdict: `where.too_short` when every fit is `too_short`. Otherwise `where.clear` when any cell is clear after step 4, and `where.chance` when none is.
6. Headline: "{n_clear} of {total} grid cells around {place} show a clear {change} in {noun}. The largest observed change is {bearing}." The `where.chance` headline says that no grid cell stays clear once all {total} are checked together, that {n_raw} look clear on their own, and that chance alone gives about {by_chance}.
7. Chart: a `cells` chart that the map layer draws as coloured squares. The colour scale is symmetric around 0. Warm colours mean a rise when the variable's `warm_up` is true.

## Rules

- **One map is one family of tests** (Wilks 2016). The method step `field_fdr` says how many cells passed on their own, how many stayed clear, and that with 63 cells about 3 can look clear by chance. `n_clear`, `n_clear_all`, and the outlined squares count cells clear after `field_test`. `n_raw` counts cells that pass on their own. `by_chance` is `round(T.alpha × total)`.
- **The largest observed change is not the change for the area.** `strongest` is the cell with the largest absolute slope. The largest of {total} noisy cell slopes overstates the change, so the text calls it "the largest observed change" and the researcher text says it is not an estimate for the area. The API field keeps the name `strongest`.
- The real box around Phnom Penh is 9 × 7 cells of 0.5° × 0.625° (63 cells), and the cached NASA POWER record has 45 years.
- Variables without `point_param` cannot be mapped. The card disables "where" for them.

## Error rates

`tools/error_audit.py` simulates maps with spatial correlation `exp(−distance / length)` between cells and AR(1) memory in each cell, and scores each map with `stats.field_test`. "Before" is the rule this replaced: the map read clear when more than `T.alpha × total` cells were clear in one direction, with no correction across cells. Each no-trend row has 1,200 maps, and each trend row has 1,200 (before: 800).

| Map | No trend, before | No trend, now | 0.6 sd per decade, before | 0.6 sd per decade, now |
| --- | --- | --- | --- | --- |
| 8 × 6 cells, 24 years, memory 0.17, length 0 | 21.9% | 5.5% | 100% | 87.2% |
| The same, length 1.5 cells | 28.5% | 5.7% | 99.2% | 73.6% |
| The same, length 3 cells | 30.4% | 5.1% | 92.8% | 56.8% |
| 9 × 7 cells, 45 years, memory 0.24, length 19 (the real map) | 18.2% | 3.0% | 99.9% | 96.5% |

Length 19 gives a neighbour correlation of 0.95, the value measured on the cached NASA T2M grid around Phnom Penh. The old rule called a map with no trend clear one time in five. The new rule holds that near 5%. It pays in power on short records with strong spatial correlation: on 24 years at length 3, a real trend of 0.6 standard deviations per decade now reads clear 57% of the time. On the real map's 45 years it reads clear 96.5% of the time.

At 0.6 standard deviations per decade, the largest absolute cell slope averages 1.39 on the 8 × 6 maps with independent cells and 0.74 on the real map. That is why the text calls it the largest observed change and not the change for the area.

On the cached NASA POWER heat grid around Phnom Penh (1981 to 2025), 24 of 63 cells pass on their own and 15 stay clear after `field_test`. The verdict stays `where.clear`.

## Acceptance

- With `EB_OFFLINE=1`, `WhereQ(Phnom Penh, heat)` returns a cell list that covers the box, with counts that sum to `total`.
- A point at latitude 89 clamps the box to the pole and still returns cells.
- The method ends with `field_fdr`, every cell carries `q`, and `counts.clear <= counts.raw`.
- `tools/error_audit.py` passes: a map with no trend reads `where.clear` in at most 6% of runs on every row above.

## Reference

`~/earth-buddy/earth-buddy-analyst/earthbuddy/analyses.py` function `where`, and `web/charts.js` function `trendMap`.
