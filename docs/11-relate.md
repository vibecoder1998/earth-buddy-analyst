# Relate

The person asks whether two variables move together at a place: "Is rainfall linked to soil moisture in Cambodia?" The answer is a pattern, never a cause. Priority P2. Estimate 1.5 hours.

## Input and output

`RelateQ(region, x, y, window)`.

`Result.detail`:

```python
{
  "n_years": int, "rho": float, "rho_raw": float, "p": float, "effective_years": float,
  "strength": "no" | "weak" | "moderate" | "strong", "direction": "together" | "opposite",
  "share_moving_together": float,
  "sensitivity": {"value": float, "lo": float, "hi": float},   # Sen slope of detrended y on detrended x
  "x_leads_one_year": {"rho": float, "p": float} | None,
  "points": [[x_resid, y_resid, year]],
  "short_record": bool                                         # n < 20
}
```

## Steps

1. Get both series and keep the shared years. Require at least `T.reliable` shared years and two non-constant series.
2. Remove each series' Sen line. Two variables that both trend would otherwise look linked.
3. Compute Spearman rho on the residuals.
4. Correct for memory with an effective sample size: `n_eff = min(n, max(T.neff_floor, n · (1 − r1x·r1y) / (1 + r1x·r1y)))`. Here `r1x` and `r1y` are the lag-1 autocorrelations, and the product is floored at 0. Compute p from a t-test with `n_eff − 2` degrees of freedom.
5. Strength by `|rho|`: `no` under 0.2, `weak` under 0.4, `moderate` under 0.6, else `strong`.
6. One-year lead: rho of `x[t]` with `y[t+1]`, when n is at least 11.
7. Headline: "Rain and soil moisture in Cambodia **move together** (strong, clear). This is a pattern, not proof that one causes the other."
8. Chart: a scatter of the residuals, labelled by year.

## Rules

- Never claim a cause. The headline always carries the "pattern, not proof" sentence.
- When both variables come from MERRA-2, add a note: one model produced both, so part of the link can come from the model itself.

## Acceptance

- Two independent synthetic series, 24 years each, whose trends are 10 times their noise, give `rho_raw` above 0.5 and a detrended `rho` under 0.3 in at least 90% of 500 runs.
- A pair from the same MERRA-2 source shows the shared-model note.

## Reference

`~/earth-buddy/earth-buddy-analyst/earthbuddy/insights.py` function `relate` and `stats.py` function `relation`.
