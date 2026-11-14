# Baseline compare

The person asks whether a recent period differs from a reference period: "Is Phnom Penh hotter than in the 1980s?" Priority P2. Estimate 1.5 hours.

## Input and output

`BaselineQ(point, variable, baseline=(1981, 2010))`. The recent period runs from the year after the baseline to the last complete year.

`Result.detail`:

```python
{
  "baseline": {"start", "end", "mean", "fit": Fit | None},
  "recent":   {"start", "end", "mean", "fit": Fit | None},
  "level":    {"difference": float, "percent": float | None, "p": float, "test": "mann-whitney", "level": Level},
  "pace":     {"difference_per_decade": float, "z": float, "p": float, "level": Level} | None
}
```

## Steps

1. Get the point series. Split it into the baseline and recent periods.
2. Level: run Mann-Whitney U, two-sided, on the yearly values of the two periods.
3. Pace: when both periods have at least `T.reliable` years, compare the Sen slopes. `se = (hi − lo) / (2 × 1.96)` for each period, floored at 1e-12. `z = Δslope / hypot(se_recent, se_base)`, and `p = 2 · (1 − Φ(|z|))`.
4. Headline: if pace is present, say whether the change is speeding up. Otherwise talk about the level only.
5. Chart: the annual line with each period's mean drawn as a flat segment.

## Rules

- The baseline needs at least 8 years and must end at least 2 years before the last complete year. The recent period needs at least 3 years. Otherwise return a 400 error with `field: "baseline"`.
- The pace test is a normal approximation built from two intervals. The method says so.
- Countries and places cannot run a baseline, because their record starts in 2001. The card offers the country's centre point instead.

## Acceptance

- With `EB_OFFLINE=1`, `BaselineQ(Phnom Penh, heat)` returns a positive level difference with a clear p.
- A baseline of (2018, 2023) returns a 400 error.

## Reference

`~/earth-buddy/earth-buddy-analyst/earthbuddy/analyses.py` function `baseline` and `stats.py` function `compare_periods`.
