# Rain, soil and heat panel

The third panel of Analyze mode. It answers one question: is rain, soil wetness or heat around Cambodia changing, and does the answer hold in every part of the year. Priority P1. Estimate 1 hour.

The numbers are five monthly NASA Giovanni area averages over one box around Cambodia, 2001 to 2024. They are already on main in `data/giovanni/`. One is a satellite-based estimate (GPM IMERG). Four are MERRA-2 model output.

## Input and output

```python
class WaterQ:
    kind: Literal["water"]
    measure: Literal["imerg", "m2rain", "soil", "t2m", "wet"] = "imerg"
    span: tuple[int, int] = (2001, 2024)      # calendar years
```

`{"kind": "water"}` is a complete question and is the panel's reset. `Result.detail` is `PanelDetail` (`docs/20-fire.md`). The verdict keys are trend's.

## The measures

Each `data/giovanni/index.json` entry has a `measure` key, typed by `catalog.MeasureInfo`. It is the one place a measure's file, unit, factor and source ids are named. `catalog.measure(id)` reads it and `series.monthly(id)` returns the series in the measure's unit.

| `measure` | File parameter | Factor | Unit | Percent per decade | Context variable |
|---|---|---|---|---|---|
| `imerg` | GPM_3IMERGM precipitation | 1 | mm/day | yes | `rain_sat` |
| `m2rain` | PRECTOTLAND | 86400 | mm/day | yes | `rain` |
| `soil` | GWETROOT | 100 | % | yes | `soil` |
| `t2m` | T2M | 1 | °C | no | `heat` |
| `wet` | T2MWET | 1 | °C | no | `wetbulb` |

A value at or above 1e10 is a Giovanni fill value and is dropped. None of the eight files has one. `imerg` and `m2rain` carry `pair: ["m2rain", "imerg"]`, so each draws the ratio of the model rain to the satellite rain.

## Steps

1. Yearly means of whole calendar years inside `span` (`series.season_means`). No year inside the files is a 400 on `span`.
2. `base.tested()` on the yearly means. Fewer than `T.min_years` years is a 400 on `span`. Fewer than `T.reliable` gives `trend.too_short`.
3. The same test on three parts of the year (`monthly.by_part`): whole year, dry season (November to April, named by the year it ends) and wet season (May to October). A part with fewer than `T.min_years` values is left out.
4. Twelve calendar-month means over the span, each with its lowest and highest year (`monthly.typical_year`).
5. `stats.pettitt` on the yearly means. A jump counts only when its p-value is under `T.pettitt_p` and `stats.is_step` agrees. No year is typed in.
6. For the two rain measures, the yearly ratio of MERRA-2 rain to GPM rain over the span, and `stats.pettitt` on it.

## Charts, in order

| # | Type | Shows |
|---|---|---|
| 1 | `line` | yearly means with the Sen line and its 95% band. `mark_year` is the jump when step 5 finds one |
| 2 | `line` | every month in the span |
| 3 | `intervals` | change per decade for whole year, dry season, wet season. The whole year is marked |
| 4 | `intervals` | twelve rows, January first: each month's mean, from its lowest to its highest year. The peak month is marked |
| 5 | `line` | rain measures only. MERRA-2 rain over GPM rain per year. When Pettitt finds a break under `T.pettitt_p`, `mark_year` is its first year and `means` draws the level before and after |

## Tiles, notes, facts

- Tiles: change per decade, how sure, average, highest month.
- Notes. `note.parts` when the parts of the year that can be judged reach different levels. `note.panel.step` when step 5 finds a jump in the span. `note.water.ratio` when the ratio breaks. Trend's `note.tied`.
- Facts: every fact of `docs/06-trend.md`, plus `n_months`, `box`, `file_first`, `file_last`, `step_year`, `step_p`, `percent_per_decade` (percent measures), `year_change`, `dry_change`, `wet_change`, `parts_agree`, `parts_tested`, `peak_month`, `peak_level`, `low_month`, `low_level`, and for the rain measures `ratio_over`, `ratio_under`, `ratio_year`, `ratio_break_p`, `ratio_before`, `ratio_after`.

## Investigation

`Finding.ground` supplies the scope (the Giovanni box, read from the file's header), the context variable of the measure, and three limits: MERRA-2 is model output, the box is not Cambodia alone, and the years the files cover. `datasets` is empty. Follow-ups are Ask questions about the context variable in Cambodia.

## Statistics

Every number comes from `earthbuddy/stats.py`. The branch ran a pre-whitened Mann-Kendall, Hamed-Rao, Yue-Wang and a seasonal Mann-Kendall in the browser. This panel runs `trend_test` on three yearly series instead (`docs/03-stats.md`). Sen slopes match. p-values differ.

| Whole record, 2001 to 2024 | Branch | Here, measured |
|---|---|---|
| GPM rain, percent per decade | +1.0 | +1.03 |
| MERRA-2 rain, percent per decade | +11.3 | +11.29 |
| Soil wetness, percent per decade | +4.1 | +4.09 |
| Air temperature, °C per decade | -0.01 | -0.012 |
| Wet-bulb temperature, °C per decade | +0.51 | +0.506 |
| MERRA-2 over GPM, before and after the break | 0.70, 0.94 after 2016, p 0.003 | 0.70, 0.94 from 2017, p 0.003 |
| MERRA-2 rain p | 0.045 | 0.400 |

## Acceptance

- `POST /api/run {"question": {"kind": "water"}}` returns `trend.unclear` and the five charts above, with no network call.
- The slopes match the branch (`tests/test_panels.py`).
- The ratio of the two rain records breaks at 2017 with means 0.70 and 0.94.
- MERRA-2 rain marks a jump at 2018 over the whole record and none over 2001 to 2014.
- A span of 7 years, or one outside 2001 to 2024, is a 400 with `field: "span"`.

## Reference

`fire-watch/tools/water_template.html` and `build_fire_watch.py` on the branch `feat/fire-watch-cambodia`, for the units and the ratio. Not for the statistics.
