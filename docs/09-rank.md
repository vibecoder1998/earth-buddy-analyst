# Rank

The person asks which places lead: "Which Southeast Asian capital is warming fastest?" or "Top 10 hottest countries". The answer ranks the places and says honestly when the leaders cannot be told apart. Priority P1. Estimate 2 hours.

## Input and output

`RankQ(variable, among, metric, order, top_n, window)`. `among` is a group id or an explicit list of 2 to 60 regions.

`Result.detail`:

```python
{
  "rows": [ {
      "region": Region, "name": str, "rank": int,
      "value": float,                 # change: slope per decade; level: mean of the last 10 years
      "lo": float, "hi": float,       # 95% interval
      "p": float, "q": float, "clear": bool,
      "same_as_leader": bool,         # not distinguishable from first place
      "shares_grid_cell": bool
  } ],
  "skipped": [ {"name": str, "reason": str} ],
  "tied_with_first": int
}
```

## Steps

1. Resolve the group to regions. `countries` and `places` use the precomputed series and need no network call. `southeast_asia_capitals` and `cambodia_provinces` are points and use live POWER.
2. Get each series. Skip a place with fewer than `T.min_years` usable years, and give the reason.
3. Metric `change`: run `trend_test` on each series. Metric `level`: take the mean of the last 10 years.
4. Run `bh` across the places' trend p-values. A place is `clear` when `q < T.fdr_q`.
5. Compare each place with the leader on the year-by-year difference of their two series. For `change`, run Mann-Kendall on the difference. For `level`, run the Wilcoxon signed-rank test. Run `bh` across these comparisons. `q >= T.fdr_q` means `same_as_leader`.
6. A constant difference means the two places share one grid cell. Mark both rows, and treat the pair as tied.
7. Headline: "{leader} is warming fastest, and its lead is clear." If others tie the leader: "{leader} leads, but {n} others are too close to tell apart." If no place stands out: "None of these can be told apart."
8. Chart: a dot-and-interval plot of the top `top_n` places.

## Rules

- A province or capital is its capital's grid cell, about 50 km across. The result says so in `notes`.
- A country in the `countries` group is its cos(latitude)-weighted area series. This is better than the prototype, which used each capital's cell.
- Live groups run at most 3 POWER requests at once (`docs/02-series.md`). The first run of `cambodia_provinces` makes 25 requests. Later runs use the cache.

## Acceptance

- `RankQ(heat, among="countries", top_n=10)` runs with no network call and returns 10 rows.
- Two places in the same cell return `shares_grid_cell` on both rows, and the second is `same_as_leader` when the first leads.
- A list with only one place returns a 400 error.

## Reference

`~/earth-buddy/earth-buddy-analyst/earthbuddy/insights.py` function `rank`, and `brain/places.json` for the groups.
