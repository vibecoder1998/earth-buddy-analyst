# Investigation layout

Every result is shown as one investigation with nine parts in a fixed order. The same `Result` feeds a short view for a farmer and a full view for a scientist. Code builds every line of it. No language model writes any part of the investigation block.

The aim is the NASA "Earth System Trend Detective" brief: say what changed, show it, say where and how much, separate what was measured from what is only possible, show the statistics, and name the data.

## What the person sees

| # | Section | Comes from | Discover | Explore adds | Investigate adds |
|---|---|---|---|---|---|
| 1 | Answer | `headline`, the explainer text | headline, short text, voice | | |
| 2 | Visual evidence | `charts`, chosen by the analysis | the chart, its legend, one line on why this chart | | the values table and a CSV download |
| 3 | Where | `investigation.scope` | what the numbers stand for | the limit of the grid, and a map of the grid cells | |
| 4 | How much | `tiles`, the trend insight | size and certainty cards, or the tiles | the kind's panel of numbers | tiles and insight together |
| 5 | Why | `investigation.why` | the measured line and its interpretation | possible explanations, each marked as a hypothesis | |
| 6 | Possible impact | `investigation.impact` | why the measure matters, and impacts only when a change is clear or likely | | |
| 7 | Scientific validation | `investigation.validation`, `limits`, `method` | status, method, p-value, sample | | every row with its explanation, the interval chart, assumptions and limits, the method steps |
| 8 | Data provenance | `investigation.datasets`, `sources` | dataset, parameter, type, coverage, source names | | resolution, processing, providers, full citations, the evidence download |
| 9 | What next | `investigation.next`, `guidance` | follow-up questions as buttons, guidance lines | | |

Every level shows all nine sections. A deeper level shows more inside each one. A section with nothing to say is left out, so no empty box appears.

The top bar has one switch with two modes. **Public** sets the explainer audience to `student` and opens results at Discover. **Scientific** sets the audience to `researcher` and opens results at Investigate. Both modes read the same `Result`, and the evidence stays one click away in both.

## Response schema

`Result` gains one required field, `investigation` (`earthbuddy/types.py`).

```python
Basis = Literal["measured", "interpretation", "hypothesis", "guidance"]

class Statement:  basis: Basis; text: str
class Row:        id: str; label: str; value: str; help: str
class Scope:      kind: "country" | "place" | "point" | "group"; name: str; text: str; limit: str
class Dataset:    variable; label; parameter; kind; resolution; coverage; processing; sources: list[str]
class FollowUp:   id: str; label: str; question: dict      # a Question that parses
class Investigation:
    scope: Scope | None
    why: list[Statement]         # first line is the headline, basis "measured"
    impact: list[Statement]      # never "measured"
    validation: list[Row]        # row 0 is the status or level, row 1 the method
    limits: list[str]
    datasets: list[Dataset]      # one per variable the question names
    next: list[FollowUp]         # at most 4
    guidance: list[Statement]    # all "guidance"
```

`Dataset.sources` holds ids that are in `Result.sources`. Every number in the block is a fact value, a year of the record, the span, or `T.climate_years`. `tests/test_investigation.py` checks both for every kind.

## How it is built

`analyses/investigate.py` builds the block inside `analyses.run()`, the one place a `Result` is made. It reads three things.

1. **The question's field names.** `variable`, `x`, `y` and `tests` name the measures. `region` and `point` name the place. `among` names a group. The module names no kind, so a new kind that reuses these fields gets its investigation with no new code.
2. **The facts.** A validation row appears when its fact key exists (`p_value`, `leader_p`, `nearest_p`, `<variable>_p`, the interval keys, `effective_years`, `alpha`, `fdr_q`). The method row uses the `test` fact, or the method step titles when there is none.
3. **The catalog and `data/context.json`.** The catalog gives parameter, resolution, caveats and sources. `context.json` gives the curated lines: why a topic matters, general drivers, what a rise or fall could mean, guidance, related measures. `catalog.context(id)` merges topic defaults with per-variable overrides.

A `Finding` carries three new fields. `signals` lists each measure's direction and level, and `_impact` reads only these. `tested=False` marks a result whose level is not a significance test (extremes). `focus` names the place a group result centres on, so its follow-ups have a place.

`T.climate_years` (30) lives in `stats.py`. A record shorter than that gets a line saying it shows recent change and not a climate trend.

## Chart selection

The keyword reader picks the kind. Each analysis then picks its chart in code. A language model never names a chart. The client maps the chart to a named view and shows one line on why it fits.

| Question | Kind | Chart | View |
|---|---|---|---|
| Is Phnom Penh getting hotter? | claim | line with trend and band | `TimeSeriesChart`, by level |
| Is rainfall decreasing in Cambodia? | trend | line with trend and band | `TimeSeriesChart`, by level |
| Are temperature and rainfall related? | relate | scatter | `MultiVariableChart` |
| Which regions are warming fastest? | rank | intervals | `TrendComparisonChart` |
| Where around Phnom Penh is it getting hotter? | where | cells on the map | `GeographicTrendMap` |
| Compare with a baseline | baseline | line with two period averages | `BeforeAfterComparison` |
| Seasonal cycle of a trend | trend, month tab | line by month | `TimeSeriesChart` |
| What is changing in Cambodia? | scan | none, the table of measures | the kind panel |

### A yearly record has one view per level

A line of yearly values (60 points or fewer, no seasonal comparison) is drawn three ways. `YEARLY` in `web/investigation.js` maps the level to the view. The data and the numbers are the same in all three.

| Level | View | Draws | Why |
|---|---|---|---|
| Discover | `anomaly` | one bar per year from the average of the years shown, warm or cool by the variable's `warm_up`, arrows that say above and below | height plus labels reads more accurately than colour alone (Dawson et al., Risk Analysis 2025) |
| Explore | `line` with `view: "story"` | the years joined, the trend, a value at each end of the trend | the format of NASA's own yearly temperature graph |
| Investigate | `line` with `view: "range"` | the trend and the two edges of its 95% range as labelled lines | a shaded band is often misread as more certain than it is (Kale, Kay and Hullman 2020) |

The old fan-shaped band set the vertical scale. On a short record it squeezed the years flat and showed rainfall below zero. The story and range views fit the scale to the years and clip the range lines to the plot. A record with no band stops at the story view. `tests/test_charts_js.py` draws all three in Node.

Two views were sketched and rejected. Counting years above the average, and comparing the first ten years with the last ten, both read as a clear rise on a rainfall record the test calls unclear.

No distribution chart exists, because no analysis computes a distribution. Adding one means adding it to the `Chart` union, `CHARTS` and an analysis that produces it.

## Client

`web/investigation.js` loads before `app.js`. It holds the layout and these components. Each is a function from one `Result` to an HTML string, over the renderers that already existed.

| Component | Draws |
|---|---|
| `InvestigationHeader` | level badge, place, period, kind |
| `FindingSummary` | section 1: headline and explanation |
| `MetricCard` | one tile |
| `TimeSeriesChart`, `BeforeAfterComparison`, `TrendComparisonChart`, `MultiVariableChart` | `CHARTS` renderers plus the reason for the chart |
| `GeographicTrendMap` | the cells on the MapLibre map, or as SVG when the map is in use elsewhere |
| `StatisticalSignificance` | the status box, brief or full |
| `ConfidenceInterval` | the trend's interval as one whisker, when `detail.fit` exists |
| `ImpactCard` | the impact statements |
| `MethodologyPanel` | the method steps |
| `DataSourcePanel` | datasets, citations, the evidence download |
| `FollowUpInvestigation` | follow-up buttons and guidance |

`SECTIONS` is the table of section id to view. `section()` wraps each view in `try`, so one failing section shows a short notice and the other eight still render.

Status is never colour alone. Each level has its own icon shape and its word. Each statement carries a text label for its basis. Each statistics term has a "?" that opens a plain explanation.

The map in section 3 runs a `where` question at the centre of the place for any result with a measure and a place. A claim uses its first measure. The evidence download is the full `Result` with the question and the share link. Posting its `question` to `/api/run` computes the result again.

## Integrity rules and where they live

| Rule | Enforced by |
|---|---|
| Every number is traceable | `test_every_number_in_the_investigation_comes_from_the_facts` |
| Only the headline is "measured" | `test_every_line_says_what_kind_of_claim_it_is` |
| An impact is never presented as observed | same test, and `_impact` writes none for an unclear result |
| A link is never called a cause | `test_a_link_is_never_explained_as_a_cause` |
| Air temperature is not surface temperature | `distinct` in `context.json`, `test_air_temperature_and_surface_temperature_are_told_apart` |
| A short record is not a climate trend | `T.climate_years`, `test_a_short_record_is_not_called_a_climate_trend` |
| Too few years is said plainly | `test_too_few_years_is_reported_as_untestable` |
| No finer detail than the grid | `Scope.limit`, `test_scope_never_claims_finer_detail_than_the_grid` |
| Things the catalog cannot measure are named | `reader.NOT_MEASURED`, `test_keywords_name_what_the_catalog_cannot_measure` |
| Sources are the registered ones | `test_every_dataset_cites_sources_the_result_lists` |

## Decisions

1. **The block is built on the server.** The repo has pytest and no JS test runner, so server code is the only place the rules above can be gated.
2. **Built from field names, not kinds.** One module serves all eight kinds, and the CLAUDE.md rule against `if kind ==` holds.
3. **Existing parts are reused.** Sections 2 and 4 show the `charts` and `tiles` each analysis already made. Nothing is computed twice.
4. **Curated text sits in `data/context.json`.** It keeps general science out of `catalog.json` and lets tests check that it has both languages, no digits, and covers every topic.
5. **All nine sections at every level.** Hiding sections made the numbering skip and hid provenance from the public view.
6. **Two modes map to two existing audiences.** No new explainer templates were needed.

## Checked on 2026-11-15

`pytest`: 438 passed. 66 of them are new (`tests/test_investigation.py`, `tests/test_charts_js.py`, and one reader test with 5 cases). The AI reader's tests left with it.

In Chrome against `python run.py`, template explanations, live NASA POWER:

| Question | Read as | Verdict | Chart drawn |
|---|---|---|---|
| Is Phnom Penh getting hotter? | claim | `claim.unsupported` | line |
| Is rainfall decreasing in Cambodia? | trend | `trend.unclear` | line |
| Is vegetation declining in Mondulkiri? | trend, no measure | card says "We can't measure: vegetation and forest cover" | none |
| Are temperature and rainfall related? | relate | `relate.opposite` | scatter |
| Which regions are experiencing the greatest changes? | rank among Cambodian provinces, no measure | card asks for the measure | none |
| Which regions are warming fastest? | rank | `rank.tied` | intervals |

Also checked: the three yearly views on the rainfall trend and on both charts of a two-measure claim, in English and Khmer. Khmer in Scientific mode, 360 px width with no sideways scroll, the map of 63 cells around Phnom Penh, JSON and CSV downloads, a follow-up button, a forced section failure, and switching language and mode on an open result. The console showed no errors.

## Limits

- The catalog on `main` has no vegetation measure. The reader says so and does not substitute another measure.
- The lines in `context.json` are general science written with AI help. No domain scientist has reviewed them, and they cite no papers. They are always labelled hypothesis or guidance.
- The Khmer text is a draft, as the footer says.
- Follow-up rankings always compare Southeast Asian capitals (`RANK_GROUP`).
- The yearly views follow published research on UK and US readers. No Khmer reader or farmer has tested them.
