# Earth Buddy: build spec

Earth Buddy answers one question about how the Earth is changing at a place, from NASA data. A person types a sentence: a claim ("Cambodia is getting hotter and drier") or a question ("Which Southeast Asian capital is warming fastest?"). The app turns the sentence into a typed `Question`. Code fetches the series and runs the statistics. The screen shows a verdict, the numbers, a chart, the method, and the sources.

The app merges two prototypes:

- **Claim desk** (`~/earth-buddy`, branch `claim-desk`). It tests claims against 27 NASA variables over 242 countries and 43 named places, 2001 to 2024.
- **Earth Buddy analyst** (`~/earth-buddy/earth-buddy-analyst`). It answers questions from live NASA POWER data at any point: trend, where, baseline, rank, extremes, and relate.

This file is the contract. Each feature has its own spec in `docs/`. Where a feature doc and this file differ, this file wins.

## Context

- Event: NASA Space Apps Challenge 2026, Phnom Penh. Challenge "Be An Earth System Trend Detective".
- Deadline: submission by 23:59 on 15 Nov 2026, Phnom Penh time. Pitch at 16:00 the same day.
- Users: Cambodian students, teachers, journalists, and local officers. Judges are the first real users.
- Pitch targets: Best Use of Science and Best Use of Data.

## The one rule

**Code makes every number and every verdict. The language model never does.**

- The model may read the sentence into a typed `Question` (`docs/04-reader.md`). It runs before any data loads.
- The model may write a plain-language explanation from a result's `facts` (`docs/13-explainer.md`). Code checks that every number in that text appears in `facts`. If one does not, the app shows the template text instead.
- With AI switched off, the app still answers every question. A keyword reader and templates replace the model. The verdict, tiles, and charts stay identical, and a test proves it.

## The data rule

**Every piece of data comes from NASA or a NASA partner agency, and every source is cited.** That covers measurements, country borders, place names, and map imagery. Each data file and each live call names a source id from `data/sources.json`. Tests fail on a source that is not in the registry, or not from an allowed agency. The full rule, the reference list with DOIs, and the checks are in `docs/16-data-sources.md`.

## Architecture

```
sentence ─► reader (keywords | AI) ─► Draft ─► card (person edits) ─► Question
                                                                         │
                      series source: region file | NASA POWER point ◄────┤
                                                                         ▼
                                     analysis registry[kind] ─► stats ─► Result
                                                                         │
                                     explainer (template | AI, checked) ◄┘
```

- **Backend:** Python 3.12, FastAPI, uvicorn. One package, `earthbuddy/`.
- **Frontend:** vanilla JS and CSS in `web/`, with no build step. Vendored MapLibre GL for the map. Hand-written SVG charts.
- **Storage:** one SQLite file. It holds the NASA response cache only.
- **Deploy:** Vercel Python function (`main.py` exports `app`, `maxDuration` 300 s). Local: `python run.py` serves on http://127.0.0.1:8000.

## Repository layout

```
earthbuddy/
  types.py        every shared type below (pydantic v2)
  catalog.py      loads data/catalog.json; variables, regions, groups
  series.py       get_series(region, variable, window) -> Series
  power.py        NASA POWER client (point + regional), retries, cache
  geocode.py      place name -> Point, from the local NASA SEDAC gazetteer
  cache.py        SQLite response cache
  stats.py        every statistical function; no I/O
  analyses.py     ANALYSES: dict[kind, fn(Question) -> Result]
  reader.py       keyword reader, AI reader, draft -> Question
  explainer.py    templates, AI writer, number check
  server.py       FastAPI routes
  voice.py        KiriTTS speech in and out; only server.py and telegram.py import it
data/
  catalog.json  v/<variable>.json  audit.json  countries.geojson  summary.json
  sources.json  gazetteer.json
tools/
  build_catalog.py   builds data/ from NASA POWER Zarr stores and NASA SEDAC grids
  check_refs.py      resolves every DOI in data/sources.json; writes the README reference list
web/
  index.html  app.js  charts.js  map.js  i18n.js  voice.js  styles.css  vendor/
tests/
main.py  run.py  requirements.txt  vercel.json
```

## Core types

Every module imports these from `earthbuddy/types.py`. Pydantic parses data from outside (the request body, the model reply, the share link) at the boundary. Inside, code trusts the types.

```python
VariableId = str                      # catalog id: "heat", "tmin", "aerosol"
Direction  = Literal["up", "down", "any"]
Window     = tuple[int, int] | None   # inclusive years; None = the variable's full record

class Country(BaseModel): kind: Literal["country"]; iso3: str             # "KHM"
class Place(BaseModel):   kind: Literal["place"];   id: str               # "p.mekong-delta"
class Point(BaseModel):   kind: Literal["point"];   lat: float; lon: float; name: str
Region = Annotated[Country | Place | Point, Field(discriminator="kind")]

class Test(BaseModel): variable: VariableId; direction: Direction

class ClaimQ(BaseModel):    kind: Literal["claim"];    region: Region; tests: list[Test]; window: Window = None   # 1..8 tests, unique variables
class TrendQ(BaseModel):    kind: Literal["trend"];    region: Region; variable: VariableId; window: Window = None
class WhereQ(BaseModel):    kind: Literal["where"];    point: Point;   variable: VariableId; window: Window = None
class BaselineQ(BaseModel): kind: Literal["baseline"]; point: Point;   variable: VariableId; baseline: tuple[int, int] = (1981, 2010)
class RankQ(BaseModel):     kind: Literal["rank"];     variable: VariableId; among: GroupId | list[Region]; metric: Literal["change", "level"] = "change"; order: Literal["highest", "lowest"] = "highest"; top_n: int = 10; window: Window = None
class ExtremesQ(BaseModel): kind: Literal["extremes"]; region: Region; variable: VariableId; year: int | None = None; window: Window = None
class RelateQ(BaseModel):   kind: Literal["relate"];   region: Region; x: VariableId; y: VariableId; window: Window = None
class ScanQ(BaseModel):     kind: Literal["scan"];     region: Country | Place
Question = Annotated[ClaimQ | TrendQ | WhereQ | BaselineQ | RankQ | ExtremesQ | RelateQ | ScanQ, Field(discriminator="kind")]
Kind = Literal["claim", "trend", "where", "baseline", "rank", "extremes", "relate", "scan"]

class Draft(BaseModel):          # what a reader produces and the card edits
    fields: dict                 # a partial Question; may fail to parse
    quote: str                   # what the person typed; shown, never parsed again
    via: Literal["ai", "keywords", "form", "audit", "link"]
    leads: list[str]             # things worth checking that the catalog cannot measure; no digits
    unmapped: list[str]          # parts of the sentence that matched nothing; no digits
    revision: int = 0            # +1 for every edit after a result was shown; capped at 99

class Series(BaseModel):
    region: Region; variable: VariableId
    years: list[int]; values: list[float | None]          # annual, one value per year
    monthly: list[tuple[int, int, float]] | None          # (year, month, value); POWER points only
    cells: int | None                                     # grid cells averaged; None for a point
    sources: list[Source]                                 # the dataset, its method paper, and POWER when read through it

class Source(BaseModel):         # one entry of data/sources.json; full fields in docs/16-data-sources.md
    id: str; name: str; agency: str; doi: str | None; url: str; citation: str
    via: str | None; accessed: str | None; cached: bool

class Seg(BaseModel):  t: str; hl: bool = False          # headline segment; hl = highlighted words
class Tile(BaseModel): id: str; label: str; value: str; note: str
class Step(BaseModel): title: str; did: str; why: str
Fact = str | int | float | bool | None

class Result(BaseModel):
    kind: Kind
    question: Question
    headline: list[Seg]          # built by code from the verdict level, never by the model
    verdict: Verdict             # see docs/03-stats.md
    tiles: list[Tile]            # 2 to 4
    facts: dict[str, Fact]       # the only numbers an explanation may use
    charts: list[Chart]          # see docs/14-web-ui.md
    method: list[Step]
    sources: list[Source]
    notes: list[str]             # caveats, "second look" warning, shared-grid-cell warnings
    detail: dict                 # kind-specific payload, defined in each feature doc
```

`analyses.py` holds one registry. A new question kind adds one entry and one doc. No route or screen grows an `if kind ==` chain.

```python
ANALYSES: dict[Kind, Callable[[Question], Result]] = {"claim": claim, "trend": trend, ...}
```

## HTTP API

| Method and path | Body or query | Returns |
|---|---|---|
| `POST /api/read` | `{text, lang: "en" \| "km", ai: bool}` | `{draft: Draft, question: Question \| None, missing: list[str], ai_failed: bool}` |
| `POST /api/run` | `{question: Question, revision: int}` | `Result` |
| `POST /api/explain` | `{result: Result, audience, lang, ai: bool}` | `{short, more, via: "ai" \| "template", audio: str \| None}` |
| `POST /api/hear` | `{audio: base64, mime, lang}` | `{text}`, the transcript of a spoken question |
| `GET /api/say` | `t, lang, sig`, taken whole from `Explanation.audio` | the spoken short answer, as audio |
| `POST /api/telegram` | a Telegram `Update`, header `X-Telegram-Bot-Api-Secret-Token` | `{method: "sendMessage", chat_id, text}`, or `{}`. 404 without `TELEGRAM_WEBHOOK_SECRET`, 403 on a wrong secret |
| `GET /api/catalog` | | `data/catalog.json` |
| `GET /api/sources` | | `data/sources.json`, for the **About the data** page |
| `GET /api/geocode` | `q` | `{results: list[Point]}` |
| `GET /api/audit` | | `data/audit.json` with each claim's live verdict |
| `GET /api/status` | | `{ai_available, model, last_complete_year, cache: {entries, bytes}, voice: {available, clip_s, mimes}}` |

Errors: a NASA source failure returns 502 `{error, kind: "data_source", url}`. A bad question returns 400 `{error, kind: "request", field}`. A KiriTTS failure returns 503 `{error, kind: "voice", reason: "off" | "limit" | "down"}`, and the text answer stays on screen. `ai_failed: true` means the AI reader failed and the keyword reader answered instead.

## Scope and build order

The estimates assume one coding agent with a person reviewing. Build in this order. Each row ends in a passing check before the next starts.

| # | Feature | Doc | Priority | Estimate |
|---|---|---|---|---|
| 1 | Skeleton, types, test harness, deploy | `docs/00-foundation.md` | P0 | 1 h |
| 2 | Data sources and references | `docs/16-data-sources.md` | P0 | 1 h |
| 3 | Catalog and region data | `docs/01-catalog-and-data.md` | P0 | 2 h with reuse, 4 h rebuilt |
| 4 | Series sources and cache | `docs/02-series.md` | P0 | 1.5 h |
| 5 | Statistics engine | `docs/03-stats.md` | P0 | 3 h |
| 6 | Reader: keywords and AI | `docs/04-reader.md` | P0 | 2.5 h |
| 7 | Claim check | `docs/05-claim-check.md` | P0 | 2 h |
| 8 | Trend at a place | `docs/06-trend.md` | P0 | 2 h |
| 9 | Web UI: ask, card, result, share link | `docs/14-web-ui.md` | P0 | 4 h |
| 10 | Explainer | `docs/13-explainer.md` | P1 | 1.5 h |
| 11 | Scan and audit strip | `docs/12-scan-and-audit.md` | P1 | 1.5 h |
| 12 | Where map | `docs/07-where-map.md` | P1 | 2 h |
| 13 | Rank | `docs/09-rank.md` | P1 | 2 h |
| 14 | Khmer | `docs/15-i18n.md` | P1 | 2 h, plus a native reader |
| 14a | Voice: ask aloud, hear the answer | `docs/17-voice.md` | P1 | 2.5 h, plus a 15-minute probe |
| 14b | Telegram bot: ask in a chat, get the answer and a link | `docs/18-telegram.md` | P1 | 1 h |
| 15 | Baseline compare | `docs/08-baseline.md` | P2 | 1.5 h |
| 16 | Extremes | `docs/10-extremes.md` | P2 | 2 h |
| 17 | Relate | `docs/11-relate.md` | P2 | 1.5 h |

P0 is the demo: about 19 hours. Finish P0 by Saturday night. Add P1 on Sunday morning. Add P2 only with time to spare.

## Not building

Each cut names the reason, so nobody re-adds it by accident.

- **Future projections.** The NASA POWER projection service returned fill values for Cambodia in November 2026 (comment in the analyst's `analyses.py`). Before re-adding it, run the projection call for Phnom Penh and confirm real values come back.
- **An agent tool loop.** The analyst let the model pick tools across up to 7 turns. A typed `Question` does the same job in one call. It is faster, cheaper, testable, and works with AI off.
- **Earthdata MCP, CMR dataset search, Claude subscription mode, AG-UI streaming, the graph view of the "second brain".** None of these change an answer. The cache stays.
- **The 1° global grids, timelapse, GIF export, swipe compare, air and weather cards, tour, mystery games, service worker.** The claim desk carried these from the earlier globe app. The map paints countries instead (`docs/14-web-ui.md`).
- **MODIS products through ORNL** (NPP, tree cover, burned area). A first request takes about a minute.
- **Data from outside NASA and its partners.** Natural Earth borders, the Open-Meteo and OpenStreetMap geocoders, and OpenStreetMap map tiles are gone. NASA SEDAC and NASA GIBS replace them (`docs/16-data-sources.md`).
- **Causal claims, forecasts, accounts, analytics.**

## Reuse from the prototypes

The prototypes are reference code. Port the logic. Do not copy their structure: both use patterns this spec replaces.

These files are data, and a team may copy them if the event rules allow work from before the event:

- `~/earth-buddy/data/catalog.json` and `data/audit.json`. These are the 27 variables, the 43 places, and the frozen claims.
- The place series in `~/earth-buddy/data/v/*.json`, the entries whose ids start with `p.`. The country series are not reusable, because Natural Earth borders built them. Rebuild the country series from the NASA SEDAC grid.
- `~/earth-buddy/tools/catalog_build.py`, `tools/catalog.src.json`, and `tools/catalog.text.json`. These rebuild the data above.
- `~/earth-buddy/vendor/maplibre-gl/` and `vendor/fonts/`. This is software, not data.

Do not reuse `data/countries.geojson` or the analyst's `places.json`. Neither comes from NASA.

Whether the rules allow pre-event work is not settled. Ask the local organizers before copying anything.

## Definition of done

- `pytest` passes, including the AI-off equality test and the statistics checks in `docs/03-stats.md`.
- `python run.py`, then each of the five demo sentences in `docs/14-web-ui.md`, produces a result with AI on and with AI off.
- The Vercel deploy answers the same five sentences.
- `python tools/check_refs.py` resolves every DOI, and `tests/test_sources.py` passes.
- `README.md` states how AI was used (required by Space Apps), cites every dataset with its DOI, and lists the known limits.
