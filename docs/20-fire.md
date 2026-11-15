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
4. Run `stats.trend_test` on Aqua, Terra and their sum over the same seasons, and `base.card()` on each: the headline test, the second opinions (`docs/03-stats.md`), the lag-1 memory and the Pettitt jump.
5. Share by calendar month, over the whole fire years among the chosen seasons. The shares of the season months and of `peak_months` (December to March) are added up from it.
6. Detections per province over the chosen seasons, the share of each of the five parts of the country, and the five busiest provinces. `zone` picks which provinces the province charts list. It does not change the season counts or the test.
7. Mean detections per season in each 0.1 degree square, over the chosen seasons. Squares with none are left out.
8. `stats.trend_test` on each province's season counts, where the span holds at least `T.reliable` seasons, the province at least `T.fire_min_total` detections and at least `T.fire_min_distinct` different counts. `stats.bh` across every province tested. A province is marked when its q-value is under `T.fdr_q`. BH always runs across all of them, whatever the zone.
9. The cross-check, fixed: `stats.trend_test` and `base.card()` on calendar years from the first season to the catalog's last year (2003 to 2024), for the catalog variable `fire` in Cambodia (`data/v/fire.json`) and the FIRMS Terra and Aqua calendar-year sums. `stats.spearman` and the median ratio compare the catalog series with Terra. It ignores `span`.
10. Every month on file, for the chosen satellite and the one drawn beside it.
11. The row counts of the cleaning steps: the archive, vegetation fires, kept, and the kept rows that fall in the season months and in the peak months. The last two are counted from the month table on every read.

## Charts, in order

The order is the branch's section order: is there a trend, when it burns, where it burns, where it is changing, the cross-check, the data check.

| # | Type | Shows |
|---|---|---|
| 1 | `line` | every season on file, 2003 to 2026. `y` is the chosen satellite and `compare` the other one (Aqua beside Terra, Terra beside Aqua, Aqua + Terra beside Aqua), named by `labels`. The Sen line and its 95% band cover the chosen seasons only. `spans` shades the seasons after `like_for_like_until`, and `span_label` says why |
| 2 | `intervals` | change per decade as a percent of the average, one row per satellite, the chosen one marked |
| 3 | `line` | every month on file, November 2001 to August 2026, `y` and `compare` as in chart 1. A month before a satellite starts is `null`. `spans` shades the chosen seasons, from the November before the first to the April of the last |
| 4 | `bars` | share of detections by calendar month, twelve rows, the fire season months marked |
| 5 | `cells` | mean detections per season in each square, `scale: "level"` (one hue), `warm_up: true`. The first `cells` chart, so it paints the map |
| 6 | `bars` | share of detections in each of the five parts of the country, largest first. The chosen zone is marked, or the largest when the zone is `all` |
| 7 | `bars` | mean detections per season by province, the zone's provinces, the five busiest in the country marked |
| 8 | `cells` | the province trend map: one cell at each tested province's centre point (`catalog.centre`), `cell_size` 0.3 degrees, value = Sen percent per decade, `scale: "change"`, `clear` = its q-value is under `T.fdr_q`. All tested provinces, whatever the zone. Left out with chart 9 |
| 9 | `intervals` | change per decade by province, the zone's tested provinces, highest first, marked where BH keeps them. Charts 8 and 9 are left out when the span is shorter than `T.reliable` |
| 10 | `intervals` | the cross-check: the catalog's fire series, Terra and Aqua, calendar years 2003 to 2024. The chosen satellite is marked |
| 11 | `bars` | rows left at each cleaning step: the archive, vegetation fires, kept, of those the season months, of those December to March. The kept row is marked |

## Tiles, notes, facts

- Tiles: change per decade, how sure, total detections, busiest season.
- Notes, each with the condition that fires it: `note.fire.both` when the satellite is Aqua + Terra. `note.fire.drift` when the span runs past `like_for_like_until`. `note.fire.months_stop` when it runs past the last whole fire year. `note.fire.provinces_short` and `note.panel.few` when it holds fewer than `T.reliable` seasons. Trend's `note.tied`. Fewer than `T.min_years` seasons is a 400, not a note.
- Method: the season count, the audit of the raw archive (`step.fire_audit`), trend's four steps, `step.opinions`, the province test (`step.fire_provinces`) and the cross-check (`step.fire_cross`).
- Summary rows, in order: the totals (detections, mean, busiest and quietest season, percent per decade). One test card each for Aqua, Terra and Aqua + Terra. Busiest month, the December to March share, the November to April share. Busiest province, the five busiest with their shares and per-season means, the share of the other 20. The busiest part of the country, then one row per part with its share and its provinces, then the chosen zone. The busiest map square. Provinces changing: how many reach a p-value under `T.alpha`, rising and falling, and how many BH keeps. Provinces not tested, when there are any. Both province rows are absent under `T.reliable` seasons, where nothing is tested and the note says so. One test card each for the three cross-check series, then the rho and median ratio of the catalog series against Terra. What is measured, and with what. The archive rows by satellite and each satellite's first date. The kept rows by satellite, the season and peak-month rows, the dropped rows. Months on file. Seasons used. The near-real-time file that is not used. The table row counts, the median distance to a province centre, and the 2,495 re-counts.
- Facts: every fact of `docs/06-trend.md`, the facts the rows above read, and one set of card facts per satellite (`aqua_*`, `terra_*`, `both_*`) and per cross-check series (`cross_catalog_*`, `cross_terra_*`, `cross_aqua_*`): `change`, `range`, `average`, `n`, `p_value`, `level`, `plain`, `prewhitened`, `hamed_rao`, `yue_wang`, `lag1`, `memory`, `step_after`, `step_p`, `line_change`, `line_range`, `line_p`, `found`, `of`.

## Investigation

The question names no catalog variable and no place, so the analysis sets `Finding.ground` (`docs/19-investigation.md`).

- Scope: the archive's box, and that it takes in border areas of Thailand, Laos and Vietnam.
- Context: the catalog variable `fire`, for the drivers, impacts and guidance text.
- Limits: these counts do not show that fire is rising or falling and the satellites can disagree, a detection is not an area burned, seasons after 2022, double counting in Aqua + Terra, provinces by nearest centre point, and what the archive covers.
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
| `index.json` | sources, box, season rule, peak months, zones, and the audit of the raw archive: rows in, rows dropped, rows kept, rows and first date per satellite, the median distance to a province centre, the near-real-time file that is not used, and the re-count checks |

Each detection goes to the nearest NASA SEDAC province centre point (`gpw-adm-points`), because NASA publishes centre points and not borders. The five zones are our own grouping of the 25 provinces. The tables spell one province "Tboung Khmum". `index.json` maps it to the catalog's "Tbong Khmum", so province names and their Khmer come from the catalog group `cambodia_provinces`.

## Statistics

Every number comes from `earthbuddy/stats.py`. The level comes from `trend_test`, the test `docs/03-stats.md` calibrates. The branch's own p-value was the plain Mann-Kendall, or the pre-whitened one when the lag-1 memory was large. Both are on each card as second opinions and set nothing.

| Default view, seasons 2003 to 2022 | Branch | Here, measured |
|---|---|---|
| Aqua, percent per decade | -1.1 | -1.1 |
| Terra, percent per decade | +15.1 | +15.1 |
| Aqua headline p | n/a | 0.928, `unclear` |
| Terra headline p | n/a | 0.348, `unclear` |
| Aqua plain p, lag-1, jump | 0.92, -0.04, after 2016 p 0.88 | 0.922, -0.044, after 2016 p 0.876 |
| Terra plain p, lag-1, jump | 0.23, +0.10, after 2010 p 0.29 | 0.230, 0.10, after 2010 p 0.290 |
| December to March share, November to April share | 91%, 98% | 91%, 98% |
| Five busiest provinces, the other 20 | 52%, 47.7% | 52%, 47.7% |
| Preah Vihear, Stung Treng | 13.7% and 2,579, 11.3% and 2,121 | 13.7% and 2579, 11.3% and 2121 |
| Cross-check, percent per decade, 2003 to 2024: catalog, Terra, Aqua | +2.18, +3.76, -2.26 | +2.18, +3.76, -2.26 |
| Cross-check, the branch's p: catalog, Terra, Aqua | 1.00, 0.69, 0.74 | pre-whitened 1.000, pre-whitened 0.695, plain 0.735 |
| Catalog series against Terra: rho, median ratio | 0.95, 1.01 | 0.95, 1.01 |
| Rows: archive, vegetation, kept, November to April, December to March | 717,185, 678,839, 647,193, 629,913, 588,197 | the same five |
| Kept rows: Aqua, Terra | 447,469, 199,724 | the same |

The branch controlled the false discovery rate at 0.05. Here it is main's one rate, `T.fdr_q`. Over the default view it keeps four provinces: Stung Treng, Banteay Meanchey, Tbong Khmum and Pailin.

## Acceptance

- `POST /api/run {"question": {"kind": "fire"}}` returns `trend.unclear` and the eleven charts above, with no network call.
- The default view matches the branch's reference numbers in the table above (`tests/test_panels.py`).
- The four tables agree with each other: November to April months add up to the season totals, province counts add up to the season totals, density squares add up to the season totals, and the 25 province names are the catalog group's.
- `satellite: "both"` equals Aqua plus Terra and carries the double-count note.
- A span of 7 seasons returns a 400 with `field: "span"`.

## Not built here

The zone filter on the density map: the map shows every square. The province rings on the density map. The branch's figures for how well nearest-centre assignment matches real borders: they were measured once against a border file that is not NASA's and is not in the repo. The branch's count of checks between its JavaScript and Python: this panel does not run that JavaScript.

## Reference

`fire-watch/tools/panel_template.html` and `build_fire_watch.py` on the branch `feat/fire-watch-cambodia`, for the season rule and the tables. Not for the statistics.
