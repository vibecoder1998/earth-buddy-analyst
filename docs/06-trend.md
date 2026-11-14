# Trend at a place

The person asks how one variable is changing at one place. The answer covers what is changing, how much, and how sure we are. Priority P0. Estimate 2 hours.

## Input and output

`TrendQ(region, variable, window)`.

`Result.detail`:

```python
{
  "fit": Fit,
  "annual": [[year, value]],
  "decomposition": {               # points only: needs at least 36 months
      "t": [str], "observed": [float], "trend": [float], "seasonal": [float], "residual": [float],
      "variance_share": {"trend": float, "seasonal": float, "residual": float}
  } | None,
  "seasonal_cycle": {               # points only
      "months": [1..12], "early": [float], "late": [float],   # first and last 10 years of the monthly means
      "peak_month": int, "low_month": int, "amplitude": float
  } | None,
  "size": {"word": "small" | "moderate" | "large" | "none", "years": float},
  "sure": {"word": "clearly" | "probably" | "cant_tell", "coin": str}
}
```

## Steps

1. Get the series. For a point, keep the monthly values.
2. Run `trend_test` on the annual values.
3. For a point with at least 36 months, run STL: `statsmodels.tsa.seasonal.STL(period=12, robust=True)`, after interpolating missing months. Report the variance share of each part.
4. Headline, chosen by `fit.level`:
   - `clear`: "{Place}'s {noun} is **clearly rising**: about {change} more every ten years since {first_year}."
   - `likely`: "{noun} is **probably rising**, but the record is not long enough to be sure."
   - `unclear`: "**No clear change** in {noun} since {first_year}."
   - `too_short`: "**Too few years** to judge."
5. Tiles: change per decade with the 95% range, how sure (level and p), and the seasonal peak month. A yearly-only series shows the highest year instead of the peak month.
6. Facts: `place`, `variable`, `unit`, `period`, `n_years`, `direction`, `change_per_decade`, `change_per_decade_95pct_range`, `total_change`, `percent_change` (`rel` variables only), `average`, `p_value`, `certainty`, `typical_swing`, `size_word`, `test`, `data_source`. Points also get `peak_month` and `seasonal_share`.
7. Charts: the annual line with the Sen line and its band. For points, add the STL tabs (trend, seasonal, residual) and the early-versus-late seasonal cycle.
8. Method: five to eight steps, from "fetched" through "tested", each with "did" and "why".

## Rules

- The headline wording comes from the level only. It never comes from the model.
- A country or place trend covers 2001 to 2024. A point trend covers the variable's `first_year` to the last complete year. The result says which, and why.
- "No clear change" never means "nothing is happening". The method says so in one sentence.

## Acceptance

- With `EB_OFFLINE=1`, `TrendQ(Point Phnom Penh, heat)` returns a clear rise, an STL decomposition, and a seasonal cycle.
- `TrendQ(Country KHM, heat)` returns a result with no decomposition and no network call.
- A series of 9 years returns the `too_short` headline. A series of 7 years returns a 400 error with `field: "window"`.

## Reference

`~/earth-buddy/earth-buddy-analyst/earthbuddy/analyses.py` functions `trend`, `_method_trend`, and `_method_annual`. `stats.py` functions `decompose` and `seasonal_cycle`.
