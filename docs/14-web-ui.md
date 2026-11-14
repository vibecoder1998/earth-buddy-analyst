# Web UI

One page laid out like the analyst prototype: a sidebar, a region picker in the top bar, a thread of questions, and a composer fixed to the bottom. Each question in the thread goes through ask, card, and result. Vanilla JS with no build step. Priority P0 for ask, card, result, and the share link. P1 for the map. Estimate 4 hours.

## Layout

- **Sidebar.** **New analysis** clears the thread. **Data by topic** lists the topics, each with a one-line description and its number of measures; a topic opens to its measures, and a click asks how that measure is changing in the current region. **Data sources** shows every entry from `GET /api/sources` with its citation and DOI, read only. **Claims written first** holds the audit strip. Below 900 px the sidebar stacks above the page, as in the prototype.
- **Region picker.** A dialog with a place search (catalog names first, then `GET /api/geocode`) and the map; a click on the map picks a point. The region starts as Phnom Penh, Cambodia, at the place's catalog centre. A question whose reading misses its `region` or `point` takes the current region before it runs. A `point` field gets a city's SEDAC centre, or else the place's or country's catalog centre (`docs/01-catalog-and-data.md`).
- **Thread.** One entry per question: the question as a bubble, then the verdict headline, the short explanation, the measure's definition and the notes as **About the data**, and **Tell me more**. The newest answer opens its card (see Result view); older answers fold to their text and a **Show charts** chip. **Edit**, **Share** and **Hide charts** are small links under the card. A sentence that reads into a complete question runs at once; otherwise its card opens inside the entry. **Edit** opens the card in the entry, and running it replaces that entry's result.
- **Start screen.** With an empty thread: six questions (`chip.*` in `web/i18n.js`, most about the current region, two rankings) and **Build it by hand**, as chips.
- **Composer.** Enter asks, Shift+Enter starts a new line. The line under it states the AI use and links to **Data sources**.

## Files

- `web/index.html` holds the shell: sidebar, top bar, thread, composer, the region dialog, and the parked map.
- `web/app.js` holds state, the thread render path, and routing.
- `web/charts.js` holds the SVG chart helpers.
- `web/map.js` holds the MapLibre setup and layers.
- `web/i18n.js` holds the string tables and `t(key, vars)`.
- `web/styles.css` holds the styles.
- `web/vendor/` holds MapLibre GL and the fonts (Inter, Noto Sans Khmer).

Every interpolated value goes through `esc()` or `t()`. Nothing from the server or the URL goes into `innerHTML` unescaped.

## State

```js
const S = {
  lang: "en" | "km",
  region: null,            // Region from the picker; fills a question that names no place
  thread: [],              // Entry[], one per question
  editing: null,           // id of the one entry whose card is open
  mapFor: null,            // id of the entry whose charts hold the map
};
// Entry = {id, text, read, asked, question, revision, ran, shown, result, explanation,
//          audience, charts_open, open, tab, fallbacks, busy, error, notice, seq, explainSeq}
// open: which disclosures are open; fallbacks: answers a picture tab borrows (see Result view)
```

`render()` rebuilds the thread from `S`. Each async call carries a sequence number on its entry, and only the newest answer is applied. One card is open at a time, so card control ids stay unique. One MapLibre map moves between the region dialog and the open charts of `S.mapFor`.

## Ask view

- The composer: a textarea, at most 600 characters. Enter submits; Shift+Enter starts a new line.
- Example chips: six questions the built kinds answer, most about the current region. The five demo sentences are typed into the composer:
  1. "Cambodia is getting hotter and drier"
  2. "How is rain changing in Siem Reap?"
  3. "Where around Phnom Penh is it warming?"
  4. "Which Southeast Asian capital is warming fastest?"
  5. "What is changing in the Mekong Delta?"
- The audit strip (`docs/12-scan-and-audit.md`), in the sidebar.
- A **Build it by hand** chip, which opens an empty card.

## Card view

The card shows the `Draft` as editable controls. One component per field, chosen from a table keyed by `kind`. No view branches on kind outside that table.

```js
const FIELDS = {
  claim:    ["region", "tests", "window"],
  trend:    ["region", "variable", "window"],
  where:    ["point", "variable", "window"],
  baseline: ["point", "variable", "baseline"],
  rank:     ["variable", "among", "metric", "order", "top_n", "window"],
  extremes: ["region", "variable", "year", "window"],
  relate:   ["region", "x", "y", "window"],
  scan:     ["region"],
};
```

- A kind selector at the top.
- Region: a search box over catalog places and countries, with geocoding for anything else.
- Tests: one row per variable with a **Rising / Falling / Any change** segment and a remove button, plus an **Add a measure** select grouped by topic.
- The quote, shown read-only. The `leads` and `unmapped` notes, shown as "We can't measure: ..." and "We didn't understand: ...".
- A **Run** button. It is disabled while `missing` is not empty, and the missing field is named.
- If `ai_failed` is true, a one-line note says the AI reader was unavailable and keywords were used.
- Editing any field after `S.shown` raises `S.revision` by 1, once per edit session.

## Result view

All panels read from `Result`. The view computes nothing. Every kind uses the same anatomy, styled like the prototype's answer.

- **Headline.** The headline segments, with `hl` in the accent colour.
- **Explanation.** The short answer, **About the data**, then **Tell me more**. The web page always explains for a student.
- **Top of the card.** A kind with an `INSIGHTS` entry shows it: a trend shows "How big is the change?" (the size word, the years one normal year's swing takes, a bar of ten years of change against that swing; when the certainty is "can't tell" or the record is too short, the title reads "If real, the change is …" and the 95% range of the change per decade replaces the years) and "Is the change real?" (the certainty word, a Can't tell / Probably real / Clearly real scale, the coin-heads comparison, the test and p-value). Other kinds show their 2 to 4 tiles.
- **The picture.** A label, a tab strip, the chart and its legend. A kind with a `PICTURES` entry lists its tabs; others get one tab per chart. A trend has **Trend** (each dot is one year, the Sen line and its 95% range), **Seasonal cycle**, **Residual** and **Where**. When the trend's own record is yearly (a place or country), the two monthly tabs borrow the same measure and years at the region's centre point, and say so in the legend. **Where** runs the where question at the centre point and draws its grid cells on the GIBS map.
- **Show the statistics.** The tiles (when the top shows insight cards), the kind panel, and the current chart's values. Each kind has one panel render function in a `PANELS` table.
- **How this was processed, and why.** The `method` steps, then the sources: one row per source with the citation, a DOI link, "via NASA POWER" where it applies, the access date, and a "from cache" mark.
- **Notes.** The second-look warning, the caveats and the shared-grid-cell notes sit in **About the data**.
- **Edit** opens the card inside the entry. **Share** copies the link.

## Charts

`Chart` is a tagged union. `charts.js` has one function per type.

```python
Chart = Annotated[Line | Bars | Scatter | Cells | Intervals, Field(discriminator="type")]
class Line:      type: "line"; title: str; x: list[int | float]; y: list[float | None]; compare: list[float | None] | None; trend: [[x0, y0], [x1, y1]] | None; band: [[x, lo, hi]] | None; mark_year: int | None; unit: str
class Bars:      type: "bars"; title: str; labels: list[str]; values: list[float]; highlight: list[bool]; unit: str
class Scatter:   type: "scatter"; title: str; points: [[x, y, label]]; x_label: str; y_label: str
class Cells:     type: "cells"; title: str; cells: [[lat, lon, value, clear]]; cell_size: [dlat, dlon]; unit: str; warm_up: bool
class Intervals: type: "intervals"; title: str; rows: [[label, value, lo, hi, highlight]]; unit: str
```

Charts use plain SVG with axes and a unit label, drawn at the card's width like the prototype's. The title is the chart's accessible name, and **Show the statistics** lists its values as a table.

## Map

- MapLibre GL, vendored. The background is the NASA GIBS `BlueMarble_ShadedRelief_Bathymetry` raster layer, and the map shows the GIBS acknowledgement (`docs/16-data-sources.md`). No other tile source is used.
- `countries.geojson` is one fill layer. Each country is drawn as its 1° cells, so the map shows exactly the area that the numbers average.
- Idle: countries are coloured by `summary.json` for the selected variable (heat by default). Countries without a clear trend after the false-discovery check are grey. The legend says so.
- With a result: fly to the region. Draw a place's bbox or a point's marker. A `Cells` chart draws its squares on the map.
- Clicking a country opens a card with `TrendQ(country, selected variable)`.

## Share link

`#q=<base64url of JSON {question, revision}>`. On load, the app sends the decoded JSON to `POST /api/run`. The server passes it through `guard` with `via: "link"` before it parses the `Question`. A link that fails opens the ask view with a "This link could not be read" note.

## Acceptance

- Each of the five demo sentences runs end to end with AI off and with AI on.
- Editing a claim after its result and running it again shows the second-look note.
- A copied share link opened in a new tab shows the same result.
- At 375 px wide the page has no horizontal scroll, and the map sits below the panel.
- Keyboard only: the ask box, the card controls, and the result tabs are all reachable, with visible focus.

## Reference

Screens of the Earth Buddy analyst prototype are in `docs/screenshots/README.md`.

`~/earth-buddy/js/caseview.js` (ask, card, board, scan), `~/earth-buddy/js/charts.js`, and `~/earth-buddy/earth-buddy-analyst/web/app.js` and `web/charts.js`.
