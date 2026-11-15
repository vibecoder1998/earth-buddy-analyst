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

A value at or above 1e10 is a Giovanni fill value and is dropped. None of the eight files has one, and `series.monthly` counts them on every read (`FileAudit`: rows, fill values, repeated months, months present of the months from first to last). `imerg` and `m2rain` carry `pair: ["m2rain", "imerg"]`. The panel draws the ratio of the model rain to the satellite rain beside every measure, as the branch did.

Each measure also has a `made` key (`catalog.Made`): `kind` (`satellite` or `model`), the `product` and parameter with the title from the file's header, the `grid`, and `what`, one sentence in English and Khmer on what produces the series. The "What is measured" rows read it. Only `imerg` is `satellite`.

## Steps

1. Yearly means of whole calendar years inside `span` (`series.season_means`). No year inside the files is a 400 on `span`.
2. `base.tested()` on the yearly means. Fewer than `T.min_years` years is a 400 on `span`. Fewer than `T.reliable` gives `trend.too_short`.
3. The same test on three parts of the year (`monthly.by_part`): whole year, dry season (November to April, named by the year it ends) and wet season (May to October). A part with fewer than `T.min_years` values is left out.
4. Twelve calendar-month means over the span, each with its lowest and highest year (`monthly.typical_year`).
5. `stats.pettitt` on the yearly means. A jump counts only when its p-value is under `T.pettitt_p` and `stats.is_step` agrees. No year is typed in.
6. For every measure, the yearly ratio of MERRA-2 rain to GPM rain over the span, and `stats.pettitt` on it. The pair comes from the manifest's `pair`.
7. `base.card()` on the yearly means of the span with its months: the headline test, the straight-line fit (`stats.line_fit`), the second opinions, the seasonal test and the test on monthly departures over the months of the span, the memory and the jump.
8. The fixed cards (`monthly.whole_record`): the same for each of the five series over every year on file, 2001 to 2024. The chosen series' six p-values and their count make the robustness row. All five make the fixed table and the count of series whose plain p-value is under `T.alpha`. They ignore the controls.
9. The month-to-month links, fixed: `stats.pearson` between GPM rain and soil wetness, soil wetness and air temperature, and soil wetness and the Aqua fire counts of calendar years 2003 to 2024, first as they are and then on `stats.anomalies`. A month with no detection counts as zero.
10. `stats.pearson` between the two rain records over all the months on file.
11. `monthly.steps`: how many of the MERRA-2 series on file jump over their whole record, and when.
12. On every read, `series.monthly` counts each file's rows, fill values, repeated months, and the months present between its first and last (`FileAudit`).

## Charts, in order

| # | Type | Shows |
|---|---|---|
| 1 | `line` | yearly means with the Sen line and its 95% band. `mark_year` is the jump when step 5 finds one |
| 2 | `line` | every month in the span. `trend` is the Sen line of the yearly means, drawn at mid-year. `spans` shades each November to April |
| 3 | `intervals` | change per decade for whole year, dry season, wet season. The whole year is marked |
| 4 | `intervals` | twelve rows, January first: each month's mean, from its lowest to its highest year. The peak month is marked |
| 5 | `line` | one value per year: `y` is the wet-season mean and `compare` the dry-season mean, named by `labels` |
| 6 | `line` | for every measure: MERRA-2 rain over GPM rain per year. When Pettitt finds a break under `T.pettitt_p`, `mark_year` is its first year and `means` draws the level before and after |

## Tiles, notes, facts

- Tiles: change per decade, how sure, average, highest month.
- Notes, each with the condition that fires it: `note.parts` when the parts of the year that can be judged reach different levels. `note.panel.step` when step 5 finds a jump in the span. `note.water.model_step` when the chosen series is model output, its whole record jumps with a Pettitt p-value under `T.pettitt_p`, and the span holds years on both sides of the jump. `note.water.ratio` when the ratio breaks. `note.panel.few` when there are fewer than `T.reliable` years. Trend's `note.tied`.
- Method: the Giovanni read, trend's four steps, `step.opinions`, the parts of the year, the step check, `step.whole_record`, `step.water_links` and `step.files`.
- Summary rows, in order: what the chosen series is and what makes it. The average over the months with its highest and lowest month. Average, change, percent. The test card of the span, the straight-line fit, the seasonal tests and whether they agree with the plain test. The three parts of the year. Highest and lowest month. The jump, when there is one. The six-test robustness row over the whole record, with its count. The ratio before and after its break and the same as a share. Pearson r between the two rain records. How many of the five series reach a plain p-value under `T.alpha`, and how many the headline test calls clear. One fixed test card per series. The three month-to-month links. What is measured, for the other four series. One file check per file.
- Facts: every fact of `docs/06-trend.md`, `n_months`, `box`, `file_first`, `file_last`, `step_year`, `step_p`, `percent_per_decade` (percent measures), the parts facts, the peak and low facts, `ratio_over`, `ratio_under`, and when the ratio breaks `ratio_year`, `ratio_break_p`, `ratio_before`, `ratio_after`, `ratio_before_share`, `ratio_after_share`. Also `rain_r`, `rain_months`, `series`, `series_under`, `under_names`, `series_clear`, `model_series`, `model_steps`, `steps_first`, `steps_last`, `satellite_step_p`, `satellite_plain`, the card facts `sel_*`, `whole_*` and `all_<measure>_*`, and the level facts `here_*`.

## Investigation

`Finding.ground` supplies the scope (the Giovanni box, read from the file's header), the context variable of the measure, and six limits: MERRA-2 is model output, how many of the MERRA-2 series on file jump over their whole record and when, the box is not Cambodia alone, the tests have limited power with this many values, wet-bulb against air temperature with both whole-record changes, and the years the files cover. `datasets` is empty. `sources` lists the chosen series' sources first, then those of every other series the fixed rows read: the other Giovanni files and the fire tables. Follow-ups are Ask questions about the context variable in Cambodia.

## Statistics

Every number comes from `earthbuddy/stats.py`. The level comes from `trend_test`. The branch's pre-whitened, Hamed-Rao, Yue-Wang, seasonal and anomalies tests are on the panel as second opinions (`docs/03-stats.md`). They set nothing.

| Whole record, 2001 to 2024 | Branch | Here, measured |
|---|---|---|
| GPM rain, percent per decade | +1.0 | +1.03 |
| MERRA-2 rain, percent per decade | +11.3 | +11.29 |
| Soil wetness, percent per decade | +4.1 | +4.09 |
| Air temperature, °C per decade | -0.01 | -0.012 |
| Wet-bulb temperature, °C per decade | +0.51 | +0.506 |
| MERRA-2 over GPM, before and after the break | 0.70, 0.94 after 2016, p 0.003 | 0.70, 0.94 from 2017, p 0.003 |
| MERRA-2 rain: branch p, headline p | 0.045 | plain 0.045, headline 0.400 |
| GPM rain, six p-values | 0.8233, 0.8327, 0.8233, 0.4766, 0.9486, 0.6343: 0 of 6 | the same to 4 decimals, 0 of 6 |
| MERRA-2 rain, six p-values | 0.0445, 0.0083, 0.1361, 0.0053, 0.0093, 0.0010: 5 of 6 | the same, 5 of 6 |
| Soil wetness, six p-values | 0.0445, 0.0037, 0.1589, 0.0079, 0.0000, 0.0000: 5 of 6 | the same, 5 of 6 |
| Air temperature, six p-values | 0.9013, 0.8741, 0.9013, 0.7694, 0.6416, 0.8644: 0 of 6 | the same, 0 of 6 |
| Wet-bulb temperature, six p-values | 0.0012, 0.0000, 0.0012, 0.0000, 0.0000, 0.0000: 6 of 6 | the same, 6 of 6 |
| Series under 0.05 on the plain test | 3 of 5 | 3 of 5 |
| Most likely jump: MERRA-2 rain, soil, wet-bulb, air, GPM | after 2017 p 0.012, after 2016 p 0.005, after 2016 p 0.002, p 0.65, p 0.99 | after 2017 p 0.012, after 2016 p 0.005, after 2016 p 0.002, p 0.648, p 0.993 |
| The two rain records, Pearson r, 288 months | 0.93 | 0.93 |
| Rain to soil, r and with the cycle out | +0.68, +0.28 | 0.68, 0.28 |
| Soil to air temperature | -0.57, -0.50 | -0.57, -0.50 |
| Soil to Aqua fire, 264 months | -0.61, -0.21 | -0.61, -0.21 |
| Wet-season soil wetness, 2001 and 2022, percent | 76.8, 86.8 | 76.8, 86.8 |

The six p-values are in the order plain, pre-whitened, Hamed-Rao, Yue-Wang, seasonal, anomalies.

## Acceptance

- `POST /api/run {"question": {"kind": "water"}}` returns `trend.unclear` and the six charts above, with no network call.
- The reference numbers in the table above match the branch (`tests/test_panels.py`).
- The ratio of the two rain records breaks at 2017 with means 0.70 and 0.94, beside every measure.
- MERRA-2 rain marks a jump at 2018 over the whole record and none over 2001 to 2014.
- The fixed rows are the same for every span.
- A span of 7 years, or one outside 2001 to 2024, is a 400 with `field: "span"`.

## Reference

`fire-watch/tools/water_template.html` and `build_fire_watch.py` on the branch `feat/fire-watch-cambodia`, for the units and the ratio. Not for the statistics.
