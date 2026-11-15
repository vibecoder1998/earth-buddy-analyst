# Fire panel

The first panel of Analyze mode. It answers one question: are fires around Cambodia becoming more or fewer, and when and where do they burn. Priority P1. Estimate 1.5 hours.

The numbers are MODIS active fire detections from the NASA FIRMS archive (`modis-mcd14ml`), counted per fire season. The catalog variable `fire` is a different series: one combined count per calendar year for each country. This panel keeps the two satellites apart and counts by season, month and province.

## Input and output

```python
class FireQ:
    kind: Literal["fire"]
    satellite: Literal["aqua", "terra", "both"] = "aqua"
    zone: Literal["all", "ne", "nw", "ts", "sw", "mk"] = "all"
    span: tuple[int, int] = (2003, 2022)      # fire seasons, each named by the year it ends
```

Every field has a default, so `{"kind": "fire"}` is a complete question and is the panel's reset.

The field is `span`, not `window`. The reader drops a `window` that ends after 2024 or holds fewer than `T.reliable` years, and fire seasons run to 2026.

`Result.detail` is `PanelDetail`, the same for every Analyze kind:

```python
{
  "fit": Fit,                               # the chosen satellite's season counts
  "size": {"word", "years"},                # as in docs/06-trend.md
  "sure": {"word", "coin"},
  "rows": [[label, value]]                  # the summary numbers, in reading order
}
```

The verdict keys are trend's (`trend.clear`, `trend.likely`, `trend.unclear`, `trend.too_short`), so the headline, the three audiences and the Khmer text need nothing new.

## The season rule

- A fire season is November to April. It is named by the year it ends: season 2020 is November 2019 to April 2020.
- Seasons 2003 to 2026 are offered. Season 2002 is left out: Aqua had not started, and the archive misses the first half of November 2001.
- A fire year is the twelve months from November to October. The share by month uses whole fire years only. The archive ends on 27 August 2026, so the last whole fire year is 2025.
- Seasons after 2022 are not like-for-like with earlier ones. Overpass times have drifted, and NASA changed the processing version on 1 January 2023. The default span stops at 2022, and a later span carries a note.

`data/firms/index.json` holds these facts (`season_months`, `seasons`, `like_for_like_until`). `series.fires()` works out the whole fire years from the month table.

## Steps

1. Clip `span` to the seasons on file. A span with no season on file is a 400 on `span`.
2. Add up the season counts of the chosen satellite. `both` adds Aqua and Terra, and a fire both saw counts twice.
3. Run `base.tested()` on the season counts. Fewer than `T.min_years` seasons is a 400 on `span`. Fewer than `T.reliable` gives `trend.too_short`.
4. Run `stats.trend_test` on Aqua, Terra and their sum over the same seasons, for the by-satellite chart.
5. Share by calendar month, over the whole fire years among the chosen seasons.
6. Mean detections per season for each province. `zone` picks which provinces the chart lists. It does not change the season counts or the test.

## Charts, in order

| # | Type | Shows |
|---|---|---|
| 1 | `line` | season counts of the chosen satellite, with the Sen line and its 95% band |
| 2 | `intervals` | change per decade as a percent of the average, one row per satellite, the chosen one marked |
| 3 | `bars` | share of detections by calendar month, twelve rows, the fire season months marked |
| 4 | `bars` | mean detections per season by province, the zone's provinces, the five busiest in the country marked |

## Tiles, notes, facts

- Tiles: change per decade, how sure, total detections, busiest season.
- Notes: `note.fire.both` for Aqua + Terra, `note.fire.drift` for a span past `like_for_like_until`, `note.fire.months_stop` for a span past the last whole fire year, and trend's `note.tied`.
- Facts: every fact of `docs/06-trend.md`, plus `satellite`, `zone`, `total_detections`, `mean_per_season`, `busiest_season`, `busiest_n`, `quietest_season`, `quietest_n`, `percent_per_decade`, `aqua_change`, `terra_change`, `both_change`, `busiest_month`, `busiest_month_share`, `season_months`, `season_share`, `months_until`, `top_province`, `top_province_share`, `top_provinces`, `top_share`, `top_zone`, `top_zone_share`, `zone_share`, `like_for_like_until`, `drift_year`, `archive_first`, `archive_last`, `min_confidence`, `season_first`, `season_last`, `box`.

## Investigation

The question names no catalog variable and no place, so the analysis sets `Finding.ground` (`docs/19-investigation.md`).

- Scope: the archive's box, and that it takes in border areas of Thailand, Laos and Vietnam.
- Context: the catalog variable `fire`, for the drivers, impacts and guidance text.
- Limits: a detection is not an area burned, seasons after 2022, double counting in Aqua + Terra, provinces by nearest centre point, and what the archive covers.
- `datasets` is empty. `sources` and the first method step carry the provenance.
- Follow-ups start from Cambodia and are Ask questions about the catalog variable `fire`.

## Data

`tools/firms_copy.py` copies four tables from the branch `feat/fire-watch-cambodia` into `data/firms/`, byte for byte, and writes `index.json`. The branch built them from the FIRMS MODIS Collection 6.1 archive, keeping vegetation fires (type 0) with a confidence of 30 percent or more.

| File | Holds |
|---|---|
| `fire_season_counts.csv` | detections per season and satellite |
| `fire_month_counts.csv` | detections per month and satellite, November 2001 to August 2026 |
| `fire_province_season.csv` | detections per province, season and satellite |
| `fire_cells_by_season.json` | detections per 0.1 degree square, season and satellite |
| `index.json` | sources, box, season rule, zones, the audit of the raw archive |

Each detection goes to the nearest NASA SEDAC province centre point (`gpw-adm-points`), because NASA publishes centre points and not borders. The five zones are our own grouping of the 25 provinces. The tables spell one province "Tboung Khmum". `index.json` maps it to the catalog's "Tbong Khmum", so province names and their Khmer come from the catalog group `cambodia_provinces`.

## Statistics

Every number comes from `earthbuddy/stats.py`. The branch computed in the browser with a pre-whitened Mann-Kendall test. This panel uses `trend_test`, the test `docs/03-stats.md` calibrates. The Sen slopes are the same. The p-values differ.

| Default view, seasons 2003 to 2022 | Branch | Here, measured |
|---|---|---|
| Aqua, percent per decade | -1.1 | -1.1 |
| Terra, percent per decade | +15.1 | +15.1 |
| Aqua p | 0.92 | 0.928 |
| Terra p | 0.23 | 0.348 |
| Level | not significant | `unclear` for both |

## Acceptance

- `POST /api/run {"question": {"kind": "fire"}}` returns `trend.unclear` and the four charts above, with no network call.
- The default view matches the branch's reference slopes (`tests/test_panels.py`).
- The four tables agree with each other: November to April months add up to the season totals, province counts add up to the season totals, density squares add up to the season totals, and the 25 province names are the catalog group's.
- `satellite: "both"` equals Aqua plus Terra and carries the double-count note.
- A span of 7 seasons returns a 400 with `field: "span"`.

## Not built here

The density map (`cells` with `Cells.scale = "level"`), the per-province trend with `stats.bh` at `T.fdr_q`, the cross-check against the catalog's `fire` series, the all-months line, and the audit method step. `series.fires()` already loads what they need: `cells`, `cell_counts`, `months` and `index.audit`.

## Reference

`fire-watch/tools/panel_template.html` and `build_fire_watch.py` on the branch `feat/fire-watch-cambodia`, for the season rule and the tables. Not for the statistics.
