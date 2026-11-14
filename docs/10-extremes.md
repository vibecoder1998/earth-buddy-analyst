# Extremes

The person asks about record years and unusual years: "Was 2024 Cambodia's hottest year?" or "Which month is changing most?" Priority P2. Estimate 2 hours.

## Input and output

`ExtremesQ(region, variable, year, window)`. `year` defaults to the last year of the series.

`Result.detail`:

```python
{
  "highest": [{"year", "value"}],           # top 3
  "lowest":  [{"year", "value"}],           # bottom 3
  "focus": {"year", "value", "rank_high", "rank_low", "deviation", "times_normal": float,
            "word": "ordinary" | "unusual" | "exceptional"},
  "clustering": {"top_k": int, "window": int, "highest": {"count", "chance"}, "lowest": {"count", "chance"}},
  "months": [ {"month", "slope_per_decade", "lo", "hi", "p", "q", "clear"} ] | None,   # points only
  "timing": {"centre_day": float, "shift_days_per_decade": float, "p": float} | None   # rain at points only
}
```

## Steps

1. Get the series. Require at least `T.reliable` years.
2. Highest and lowest: sort the yearly values.
3. Focus year: `times_normal = (value − Sen line at that year) / swing`. The word is `ordinary` under 1, `unusual` under 2, and `exceptional` at 2 or more.
4. Record clustering: do the most extreme years bunch in the recent past? `top_k = max(3, min(10, n // 4))` and `window = min(10, n // 2)`. `chance` is the hypergeometric tail probability of at least `count` of the top `top_k` years falling in the last `window` years.
5. Points only: run `trend_test` on each calendar month across years, then `bh` across the 12 tests.
6. Rain at points only: the season's centre is the circular mean of monthly totals on a 365-day circle. Skip it when the concentration is under 0.15 or there are fewer than 8 years. Then run `trend_test` on the yearly centre day.
7. Headline from the focus word and the clustering. Template for a record year: "{year} was {place}'s **{highest} year** on record, **{word}** even allowing for the trend."

## Rules

- "Unusual" is measured from the trend line, not the plain mean. A warming place must not label every recent year exceptional.
- The 12 monthly tests always go through `bh`.

## Acceptance

- A synthetic series whose last year sits 3 swings above the trend returns `exceptional`.
- A trendless synthetic series returns a clustering `chance` above 0.05.

## Reference

`~/earth-buddy/earth-buddy-analyst/earthbuddy/insights.py` function `extremes` and its helpers.
