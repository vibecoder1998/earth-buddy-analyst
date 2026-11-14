# Web UI

One page with three states: ask, card, result. A map sits beside them. Vanilla JS with no build step. Priority P0 for ask, card, result, and the share link. P1 for the map. Estimate 4 hours.

## Files

- `web/index.html` holds the shell: header, ask box, panel, map container, and a footer with the AI-use statement and an **About the data** link. That page lists every entry from `GET /api/sources` with its citation and DOI.
- `web/app.js` holds state, the three views, and routing.
- `web/charts.js` holds the SVG chart helpers.
- `web/map.js` holds the MapLibre setup and layers.
- `web/i18n.js` holds the string tables and `t(key, vars)`.
- `web/styles.css` holds the styles.
- `web/vendor/` holds MapLibre GL and the fonts (Geist, Noto Sans Khmer).

Every interpolated value goes through `esc()` or `t()`. Nothing from the server or the URL goes into `innerHTML` unescaped.

## State

```js
const S = {
  view: "ask" | "card" | "result",
  lang: "en" | "km",
  ai: false,               // localStorage "eb-ai"
  audience: "student",
  text: "",
  read: null,              // ReadResult from /api/read
  question: null,          // the card's current Question
  revision: 0,
  shown: false,            // a result was shown for this question
  result: null,
  explanation: null,
  busy: null,              // "read" | "run" | "explain"
  error: null,
};
```

`render()` rebuilds the panel from `S`. Each async call carries a sequence number, and only the newest answer is applied.

## Ask view

- A textarea, at most 600 characters. Ctrl+Enter or Cmd+Enter submits.
- An **AI reader** switch, off by default. Its label says: "Sends your sentence to Anthropic's Claude to read it. Numbers always come from NASA data and our code."
- Example chips. These are the five demo sentences:
  1. "Cambodia is getting hotter and drier"
  2. "How is rain changing in Siem Reap?"
  3. "Where around Phnom Penh is it warming?"
  4. "Which Southeast Asian capital is warming fastest?"
  5. "What is changing in the Mekong Delta?"
- The audit strip (`docs/12-scan-and-audit.md`).
- A **Build it by hand** link, which opens an empty card.

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

All panels read from `Result`. The view computes nothing.

- **Verdict card.** The headline segments with `hl` in bold, and the verdict colour.
- **Tiles.** 2 to 4.
- **Explanation.** The short answer, then a **More** toggle and the audience switch.
- **Charts.** Tabs when there is more than one chart.
- **Kind panel.** The claim's evidence rows, the rank table, the scan rows, and so on. Each kind has one render function in a `PANELS` table.
- **How we know.** The `method` steps.
- **Sources.** One row per source: the citation, a DOI link, "via NASA POWER" where it applies, the access date, and a "from cache" mark.
- **Notes.** The second-look warning, the caveats, the shared-grid-cell notes.
- **Edit** goes back to the card. **Share** copies the link.

## Charts

`Chart` is a tagged union. `charts.js` has one function per type.

```python
Chart = Annotated[Line | Bars | Scatter | Cells | Intervals, Field(discriminator="type")]
class Line:      type: "line"; title: str; x: list[int]; y: list[float | None]; trend: [[x0, y0], [x1, y1]] | None; band: [[x, lo, hi]] | None; mark_year: int | None; unit: str
class Bars:      type: "bars"; title: str; labels: list[str]; values: list[float]; highlight: list[bool]; unit: str
class Scatter:   type: "scatter"; title: str; points: [[x, y, label]]; x_label: str; y_label: str
class Cells:     type: "cells"; title: str; cells: [[lat, lon, value, clear]]; cell_size: [dlat, dlon]; unit: str; warm_up: bool
class Intervals: type: "intervals"; title: str; rows: [[label, value, lo, hi, highlight]]; unit: str
```

Charts use plain SVG with axes, a unit label, and a title. Each chart has a text alternative listing its values.

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

Screens of both prototypes are in `docs/screenshots/README.md`.

`~/earth-buddy/js/caseview.js` (ask, card, board, scan), `~/earth-buddy/js/charts.js`, and `~/earth-buddy/earth-buddy-analyst/web/app.js` and `web/charts.js`.
