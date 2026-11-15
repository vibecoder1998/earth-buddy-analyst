# Web UI

One page laid out like the analyst prototype: a sidebar, a region picker in the top bar, a thread of questions, and a composer fixed to the bottom. Each question in the thread goes through ask, card, and result. Vanilla JS with no build step. Priority P0 for ask, card, result, and the share link. P1 for the map. Estimate 4 hours.

## Layout

- **Sidebar.** **New analysis** clears the thread. **Data by topic** lists the topics, each with a one-line description and its number of measures; a topic opens to its measures, and a click asks how that measure is changing in the current region. **Data sources** lists every entry from `GET /api/sources` by name, each linked to its DOI or provider page. The full citations sit under each answer. **Case files** lists each prepared case with its numbered steps; a click runs that step as a new answer (`docs/12-scan-and-audit.md`). **Claims written first** holds the audit strip. Below 900 px the sidebar becomes a drawer: a menu button in the top bar opens it over the page, and Escape, a click outside, or any action inside it closes it.
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
- The case files and the audit strip (`docs/12-scan-and-audit.md`), in the sidebar.
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
class Line:      type: "line"; title: str; x: list[int | float]; y: list[float | None]; compare: list[float | None] | None; trend: [[x0, y0], [x1, y1]] | None; band: [[x, lo, hi]] | None; mark_year: int | None; unit: str; labels: [y_label, compare_label] | None; spans: [[x0, x1]] | None; span_label: str | None
class Bars:      type: "bars"; title: str; labels: list[str]; values: list[float]; highlight: list[bool]; unit: str
class Scatter:   type: "scatter"; title: str; points: [[x, y, label]]; x_label: str; y_label: str
class Cells:     type: "cells"; title: str; cells: [[lat, lon, value, clear]]; cell_size: [dlat, dlon]; unit: str; warm_up: bool; scale: "change" | "level"
class Intervals: type: "intervals"; title: str; rows: [[label, value, lo, hi, highlight]]; unit: str
```

A `cells` chart with `scale: "level"` holds counts, not changes. `cells()` and the map shade it on the warm colour alone, by the square root of the value over the largest, and the legend and map key say "darker means more" of its unit. `Line.labels` names the `y` and `compare` series in the legend. `Line.spans` shades x-ranges behind the series, in the units of `x` and inclusive, so each band reaches half a step past both ends and covers whole years or whole months; bands clip at the plot edges. `Line.span_label` names the shading in the legend, and the legend shows no key without it. The yearly bars of Chat's first depth keep the shading. A change grid starts each square at a quarter of its colour, as the map does, so a square near zero still shows; a level grid draws zero as white. A `bars` chart sizes its label gutter to its longest label, up to half the width.

Charts use plain SVG with axes and a unit label, drawn at the card's width like the prototype's. The title is the chart's accessible name, and **Show the statistics** lists its values as a table.

## Map

- MapLibre GL, vendored. The background is the NASA GIBS `BlueMarble_ShadedRelief_Bathymetry` raster layer, and the map shows the GIBS acknowledgement (`docs/16-data-sources.md`). No other tile source is used.
- `countries.geojson` is one fill layer. Each country is drawn as its 1° cells, so the map shows exactly the area that the numbers average.
- Idle: countries are coloured by `summary.json` for the selected variable (heat by default). Countries without a clear trend after the false-discovery check are grey. The legend says so.
- With a result: fly to the region. Draw a place's bbox or a point's marker. A `Cells` chart draws its squares on the map.
- Clicking a country opens a card with `TrendQ(country, selected variable)`.

## Analyze

The second screen. The top bar holds two tab groups: **Chat | Dashboard** switches the screen, and **Public | Scientific** sets the audience. Below 560 px the bar keeps two rows: the menu, the brand, the screen switch and the language button, then the audience tabs and the place button, which shrinks and cuts the place name with an ellipsis. On screen the switch reads Chat and Dashboard (`screen.ask`, `screen.analyze` in `web/i18n.js`). In code and on the wire the screens are `"ask"` and `"analyze"`.

```js
S.screen = "ask" | "analyze";
S.panel = kind;                 // the open panel, a kind whose catalog screen is "analyze"
S.panels = { [kind]: Entry };   // one entry per panel, kept outside S.thread, with auto: true
const SCREENS = { ask: viewThread, analyze: viewAnalyze };
```

- **Panels come from the catalog.** The panel tabs are the kinds in `GET /api/catalog` whose `screen` is `analyze`, in catalog order. Each select lists the field's `choices`. A new panel kind needs a backend entry and `kind.*`, `field.*` and `card.opt.*` strings, and nothing else in `web/`. No view names a kind.
- **The panel bar** is the by-hand card with the kind select replaced by a tab strip of panels, then one fieldset per field from `EDITORS`. It has no Run button. Each control change posts one `POST /api/run` with the panel's question, and a late answer to an older change is dropped. A click on the open panel's tab resets it to the kind's defaults. A rejected question shows the card's error and keeps the last result until the next change. Above 900 px the bar stays under the top bar, compact: the tabs and fields share rows where they fit, each field label sits inline, and the bar is about 100 px tall. Anything scrolled into view inside the panel stops below the bar.
- **The result is the investigation card at full depth.** The Dashboard draws every chart in `result.charts`, one after another, each with its own label, legend and values table. The first `cells` chart takes the shared map, and any later one draws as an SVG grid with its own legend. There is no depth switch. The summary rows and the method start open. A result with no `PANELS` entry shows `detail.rows` as its summary numbers, and one with no `INSIGHTS` entry shows the trend insight cards when its `detail` carries `fit`, `size` and `sure`. Five or more tiles go three to a row above 900 px.
- **Summary rows.** `detail.rows` arrive as `[label, value]` pairs in reading order, already worded. They read as a sheet of label and value in two columns where the card is wide enough. Neighbouring rows whose labels open with the same phrase (up to a space, a comma or a colon) become one group under that phrase, and each row shows the rest of its label. The heading is the server's own words, so the grouping works in English and Khmer and `web/` adds no text. Chat keeps its tab strip and its three depths.
- **The Dashboard takes the whole window.** `render()` writes the screen to `body[data-screen]`. On `analyze`, CSS hides the side list, the question bubble and the speaker label, drops the 900 px column limit and, from 1200 px, lays the charts out two to a row. The brand moves into the top bar. **Public | Scientific** is hidden there, and a panel always explains for the public audience.
- **Every chart answers the pointer.** On both screens, each mark in `charts.js` carries `data-tip`: a heading line, then one line per value. One delegated handler in `app.js` shows it in `#hover-tip`. A line gets one full-height column per x, so the pointer reads it anywhere above or below the point, and the column and its points light up. Bars and interval rows light up as a row. The map shows the same text for a cell through MapLibre's layer events. A tap shows the same tip on a touch screen.
- **Chat stays as it was.** On the Dashboard the composer and the region button are hidden, not removed. Any new thread entry returns to Chat: a follow-up chip, a side topic, a case step, an audit claim and a map click. **New analysis** also returns to Chat.
- **Link.** A panel writes the same `#q=` link as any answer. A link whose kind has `screen: "analyze"` opens on the Dashboard with the same controls. Switching screens rewrites the hash to the screen's newest answer.

## Share link

`#q=<base64url of JSON {question, revision}>`. On load, the app sends the decoded JSON to `POST /api/run`. The server passes it through `guard` with `via: "link"` before it parses the `Question`. A link that fails opens the ask view with a "This link could not be read" note.

## Acceptance

- Each of the five demo sentences runs end to end.
- Editing a claim after its result and running it again shows the second-look note.
- A copied share link opened in a new tab shows the same result.
- At 375 px wide the page has no horizontal scroll, and the map sits below the panel.
- Keyboard only: the ask box, the card controls, and the result tabs are all reachable, with visible focus.

## Reference

Screens of the Earth Buddy analyst prototype are in `docs/screenshots/README.md`.

`~/earth-buddy/js/caseview.js` (ask, card, board, scan), `~/earth-buddy/js/charts.js`, and `~/earth-buddy/earth-buddy-analyst/web/app.js` and `web/charts.js`.
