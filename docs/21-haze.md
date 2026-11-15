# Soot and haze panel

The second panel of Analyze mode. It answers two questions: is smoke-type aerosol around Cambodia changing in the dry season, and does it follow fire. Priority P1. Estimate 1 hour.

The aerosol numbers are three monthly MERRA-2 series from NASA Giovanni over one box around Cambodia, 2001 to 2024 (`data/giovanni/`). The fire numbers are the Fire panel's MODIS season and month counts (`data/firms/`, `docs/20-fire.md`).

## Input and output

```python
class HazeQ:
    kind: Literal["haze"]
    measure: Literal["bc", "pm25", "aod"] = "bc"
    satellite: Literal["aqua", "terra", "both"] = "aqua"
    span: tuple[int, int] = (2003, 2022)      # fire seasons, each named by the year it ends
```

`{"kind": "haze"}` is a complete question and is the panel's reset. `Result.detail` is `PanelDetail`. The verdict keys are trend's. `satellite` changes only the fire side of the comparison.

## The measures

| `measure` | File parameter | Factor | Unit | Context variable |
|---|---|---|---|---|
| `bc` | BCSMASS | 1e9 (kg/m³ to µg/m³) | µg/m³ | `smoke` |
| `pm25` | TOTSMASS25 | 1e9 | µg/m³ | `pm25` |
| `aod` | TOTEXTTAU | 1 | AOD | `aerosol` |

Each is a `measure` key in `data/giovanni/index.json` (`docs/22-water.md`). Every change is read as a percent of the average.

## The season rule

- The headline record is the dry-season mean, November to April, named by the year it ends. A season counts only when all six months are on file.
- `span` is clipped to the fire seasons on file, 2003 to 2026. The aerosol files end in December 2024, so the last whole season is 2024.
- The months the panel reads run from November before the first season to October of the last, so each month is counted once.

## Steps

1. Dry-season means inside the clipped span (`series.season_means`). None is a 400 on `span`.
2. `base.tested()` on them. Fewer than `T.min_years` seasons is a 400 on `span`.
3. `monthly.by_part` on whole year, dry season and wet season over the same years. The dry season is marked.
4. Twelve calendar-month means over the months read, for the aerosol and for the fire counts.
5. Season by season: `stats.relation` on the dry-season means against the season fire totals.
6. Month to month: `stats.anomalies` takes each calendar month's own average out of both series, then `stats.relation` runs on the anomalies in month order. It runs only with at least `T.stl_min_months` months.
7. `stats.pettitt` on the dry-season record, as in `docs/22-water.md`.
8. The branch's three plain figures: `stats.spearman` on the raw months, on the anomalies, and on the dry-season means against the season fire totals. Each gets one of two reading sentences: the first when its p-value is under `T.alpha` and rho is positive, the second otherwise.
9. `base.card()` on the dry-season record: the headline test, the second opinions, the memory and the jump.
10. The fixed card (`monthly.whole_record`): the same on the yearly means of every year on file, 2001 to 2024, with the seasonal test and the test on monthly departures over all 288 months. It ignores the controls.
11. `monthly.levels` twice: over the months read, and over the whole file.
12. `stats.trend_test` on the fire counts of the same seasons, for the row that sets the aerosol's long run beside fire.
13. `monthly.steps`: Pettitt over the whole record of every Giovanni series, for the limit that counts the model series that jump.

## Charts, in order

| # | Type | Shows |
|---|---|---|
| 1 | `line` | dry-season means with the Sen line and its 95% band, and the jump when step 7 finds one |
| 2 | `line` | every month read. `spans` shades each November to April, and `span_label` names it |
| 3 | `intervals` | twelve rows, January first: each month's mean, from its lowest to its highest year. The peak month is marked |
| 4 | `bars` | mean fire detections of the chosen satellite in each calendar month, over the same months. The peak month is marked |
| 5 | `line` | through the year: x is the calendar month, `y` the aerosol and `compare` the fire counts, each as a percent of its own average month. `labels` names both |
| 6 | `intervals` | change per decade for whole year, dry season, wet season. The dry season is marked |
| 7 | `line` | fixed: the yearly mean of every year on file, 2001 to 2024, with the Sen line and band, and the jump when Pettitt's p-value is under `T.pettitt_p` and `is_step` agrees. The title says it ignores the controls |
| 8 | `scatter` | one dot per season: dry-season mean against the season's fire detections |

## Tiles, notes, facts

- Tiles: change per decade, how sure, the season-by-season fire link, highest month.
- Notes, each with the condition that fires it: `note.parts` when the parts of the year that can be judged reach different levels. `note.panel.step` when step 7 finds a jump. `note.fire.both` when the satellite is Aqua + Terra. `note.fire.drift` when the span runs past `like_for_like_until`. `note.haze.files_end` when the span asks for seasons after the aerosol file ends. `note.panel.few` when there are fewer than `T.reliable` seasons. Trend's `note.tied`.
- Method: the dry-season means, trend's four steps, `step.opinions`, the parts of the year, the step check, `step.whole_record`, the fire link, and `step.files`.
- Summary rows, in order: the average over the months read with its highest and lowest month, and how many times higher the peak is. The dry-season average, change and percent. The three parts of the year. The dry-season test card. The fixed whole-year card with its seasonal tests. Highest and lowest month. The peak month of the aerosol beside the peak month of fire. The three `relation` links. The three plain Spearman figures with their readings. Its own long run against fire. The jump, when there is one. The whole-record level: mean, peak, low, ratio, dry-season and wet-season average. What is measured, one row per aerosol series and one for fire. One file check per aerosol file: rows, months present, fill values, repeated dates, range and mean.
- Facts: every fact of `docs/06-trend.md`, `satellite`, `measure`, `n_months`, `box`, `file_first`, `file_last`, `step_year`, `step_p`, `like_for_like_until`, `drift_year`, `percent_per_decade`, the parts facts, the peak and low facts, `season_rho`, `season_rho_raw`, `season_link_p`, `season_strength`, `season_level`, `n_link_seasons`, `month_rho`, `month_link_p`, `month_rho_raw`, `n_link_months`, `plain_raw_rho`, `plain_raw_p`, `plain_anom_rho`, `plain_anom_p`, `plain_season_rho`, `plain_season_p` and their `_reading`, `fire_peak_month`, `fire_trend_p`, `fire_trend_level`, the card facts `sel_*` and `whole_*`, the level facts `here_*` and `record_*`, and `model_series`, `model_steps`, `steps_first`, `steps_last`, `satellite_step_p`.

## Investigation

`Finding.ground`: the Giovanni box as scope, the measure's context variable and `fire` as context, and nine limits. MERRA-2 aerosol is model output. How many of the MERRA-2 series on file jump over their whole record, and when, counted by `monthly.steps`. The box is not Cambodia alone. What this measure is and is not, one text each for black carbon, PM2.5 and optical depth. A link is not a cause. The years on file. Fire counts after 2022 are not like-for-like. A detection is a hot spot. The tests have limited power with this many values. `datasets` is empty.

## Statistics

The level comes from `trend_test`, and each headline link from `stats.relation`, which detrends both series with a Sen line and corrects the p-value for memory (`docs/11-relate.md`). The branch's own figures are on the panel too, labelled as plain or as second opinions (`docs/03-stats.md`). They set nothing.

| Default view: black carbon, Aqua, seasons 2003 to 2022 | Branch | Here, measured |
|---|---|---|
| Season by season, plain Spearman rho, p, n | 0.56, 0.011, 20 | 0.56, 0.011, 20 |
| Season by season, detrended rho, p | n/a | 0.59, p 0.006 |
| Month to month, plain rho, 240 months | 0.71 | 0.71 |
| Month to month, yearly cycle out, plain rho | 0.27 | 0.27 (0.30 after detrending) |
| PM2.5 and AOD season by season, rho | 0.75, 0.71 | 0.75, 0.71 |
| Dry-season trend: branch p, headline p | 0.048 | plain 0.048, headline 0.084 `trend.likely` |
| Whole year 2001 to 2024, black carbon: percent per decade, plain p, seasonal p, anomalies p | -6.4, 0.008, 0.24, 0.093 | -6.4, 0.008, 0.243, 0.093 |
| Black carbon, most likely jump | after 2008, p 0.059 | after 2008, p 0.059 |
| PM2.5: plain, seasonal, anomalies, jump | 0.264, 0.221, 0.349, after 2016 p 0.403 | the same |
| AOD: plain, seasonal, anomalies, jump | 0.087, 0.000, 0.000, after 2016 p 0.009 | 0.087, < 0.001, < 0.001, after 2016 p 0.009 |
| Black carbon, whole record: mean, January, July, ratio, dry, wet | 0.79, 1.45, 0.39, 3.7, 1.08, 0.50 | 0.788, 1.45, 0.394, 3.7, 1.08, 0.500 |
| Aqua fire counts over the same seasons, p | 0.92 | plain 0.922, headline 0.928 |

## Acceptance

- `POST /api/run {"question": {"kind": "haze"}}` returns `trend.likely` and the eight charts above, with no network call.
- The reference numbers in the table above match the branch (`tests/test_panels.py`).
- `satellite: "both"` changes the scatter's fire totals and the notes, and leaves the aerosol record alone.
- The fixed card and chart 7 are the same for every span.
- A span past 2024 stops at 2024 and carries the like-for-like note. A span of 7 seasons is a 400 with `field: "span"`.

## Reference

`fire-watch/tools/soot_template.html` and `build_fire_watch.py` on the branch `feat/fire-watch-cambodia`, for the window, season and unit rules. Not for the statistics.
