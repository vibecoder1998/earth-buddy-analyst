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
6. Month to month: `stats.anomalies` takes each calendar month's own average out of both series, then `stats.relation` runs on the anomalies in month order. It runs only with at least `T.stl_min_months` months. The Spearman rho of the raw months is shown too, with no p-value, because the shared yearly cycle drives most of it.
7. `stats.pettitt` on the dry-season record, as in `docs/22-water.md`.

## Charts, in order

| # | Type | Shows |
|---|---|---|
| 1 | `line` | dry-season means with the Sen line and its 95% band, and the jump when step 7 finds one |
| 2 | `line` | every month read |
| 3 | `line` | through the year: x is the calendar month, `y` the aerosol and `compare` the fire counts, each as a percent of its own average month. `labels` names both |
| 4 | `intervals` | change per decade for whole year, dry season, wet season. The dry season is marked |
| 5 | `scatter` | one dot per season: dry-season mean against the season's fire detections |

## Tiles, notes, facts

- Tiles: change per decade, how sure, the season-by-season fire link, highest month.
- Notes: `note.parts` when the parts of the year disagree, `note.panel.step` for a jump, the Fire panel's `note.fire.both` and `note.fire.drift`, and trend's `note.tied`.
- Facts: every fact of `docs/06-trend.md`, plus `satellite`, `n_months`, `box`, `file_first`, `file_last`, `step_year`, `step_p`, `like_for_like_until`, `drift_year`, `percent_per_decade`, `year_change`, `dry_change`, `wet_change`, `parts_agree`, `parts_tested`, `peak_month`, `peak_level`, `low_month`, `low_level`, `season_rho`, `season_rho_raw`, `season_link_p`, `season_strength`, `season_level`, `n_link_seasons`, `month_rho`, `month_link_p`, `month_rho_raw`, `n_link_months`.

## Investigation

`Finding.ground`: the Giovanni box as scope, the measure's context variable and `fire` as context, and five limits (MERRA-2 aerosol is model output, a link is not a cause, the box is not Cambodia alone, the years on file, a detection is a hot spot). `datasets` is empty.

## Statistics

The branch ran a pre-whitened Mann-Kendall and Spearman with a plain t p-value in the browser. Here the trend is `trend_test` and each link is `stats.relation`, which detrends both series with a Sen line and corrects the p-value for memory (`docs/11-relate.md`). Raw Spearman rho values match the branch. The detrended rho and every p-value differ.

| Default view: black carbon, Aqua, seasons 2003 to 2022 | Branch | Here, measured |
|---|---|---|
| Season by season, Spearman rho of the values | 0.56 | 0.56 (`season_rho_raw`) |
| Season by season, detrended rho, p | n/a | 0.59, p 0.006 |
| Month to month, raw rho, 240 months | 0.71 | 0.71 |
| Month to month, yearly cycle out, rho of the anomalies | 0.27 | 0.27 before detrending, 0.30 after |
| PM2.5 and AOD season by season, rho | 0.75, 0.71 | 0.75, 0.71 |
| Black carbon, January mean | 1.43 | 1.43 |
| Dry-season trend p | 0.048 | 0.084, `trend.likely` |
| Whole-year slopes 2001 to 2024, percent per decade (black carbon, PM2.5, AOD) | -6.4, -1.9, -7.2 | -6.40, -1.91, -7.23 (series check, the panel starts at 2003) |

## Acceptance

- `POST /api/run {"question": {"kind": "haze"}}` returns `trend.likely` and the five charts above, with no network call.
- The raw Spearman values match the branch (`tests/test_panels.py`).
- `satellite: "both"` changes the scatter's fire totals and the notes, and leaves the aerosol record alone.
- A span past 2024 stops at 2024 and carries the like-for-like note. A span of 7 seasons is a 400 with `field: "span"`.

## Reference

`fire-watch/tools/soot_template.html` and `build_fire_watch.py` on the branch `feat/fire-watch-cambodia`, for the window, season and unit rules. Not for the statistics.
