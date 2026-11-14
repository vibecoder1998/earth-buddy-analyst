# Architecture

How the code in `earthbuddy/` and `web/` is laid out, and why. `SPEC.md` is still the contract. This file names every place the code departs from it, in "Deviations from SPEC".

Short version: the code is synchronous. A question kind is one record in `ANALYSES`. A field name is the unit of reuse on both sides of the wire. Every sentence the server writes comes from one table keyed by verdict key. Exactly one module can reach the network, and it reaches only NASA hosts and Claude on Amazon Bedrock. Every source is one entry of `data/sources.json`.

## System overview

```
                                         +--> NASA data hosts            (net.get_json)
                                         |    *.nasa.gov, nasa-power.s3.amazonaws.com
Browser ----HTTPS----> Vercel function --+
(web/)                 main.py           |
   |                   earthbuddy.server +--> Amazon Bedrock runtime      (net.ask_model)
   |                   (FastAPI app)          anthropic.AnthropicBedrock, region EB_AWS_REGION
   |
   +----HTTPS----> gibs.earthdata.nasa.gov   (map tiles, fetched by the browser itself)
```

Earth Buddy is one Python app and a folder of static files. In production the app runs as a Vercel serverless function. `main.py` imports `app` from `earthbuddy/server.py`, and that one FastAPI app serves both the `/api/*` routes and the files in `web/`. The browser loads the page from the app, then calls `/api/*` for every question.

For a country or a named place, the app reads a precomputed series from `data/v/`. For a coordinate point, it asks NASA POWER through `net.get_json`. When the person switches AI on, the app calls Claude on Amazon Bedrock through `net.ask_model`, which uses `anthropic.AnthropicBedrock` against `bedrock-runtime` in the region `EB_AWS_REGION` (default `ap-southeast-2`) with the model `EB_MODEL` (default `au.anthropic.claude-haiku-4-5-20251001-v1:0`).

Nothing in the code calls `api.anthropic.com`, and no code, data or page file contains that string. No proxy and no AWS server of our own sits between the function and Bedrock. The browser makes one request that skips the function, the map tile request to NASA GIBS.

Read the sections in this order to change the app. "Backend runtime" and "Client" describe what runs. "Configuration" lists every environment variable. "Build and deploy" and "Local development and tests" say how it ships and how you run it.

## Problem

Eight question kinds, two languages, AI on or off, about 17 hours of work for P0. The SPEC's hard rules are all "one list" rules, and the naive layout breaks each of them:

- **"A new kind adds one `ANALYSES` entry."** A bare `dict[Kind, fn]` has no room for what else a kind owns. That is its verdict keys (which the explainer must cover) and its card fields. Without a home, those turn into hand-synced lists in `reader.py`, `explainer.py`, and `web/app.js`.
- **"Code makes every number."** This holds only if the facts, the headline, and the number check share one number format and one source.
- **"Every outside input goes through one guard."** The readers emit a flat shape (`region_id`, `window_from`). The card and the share link emit a partial `Question`.
- **Language.** `docs/15` puts headlines on the server, but `POST /api/run` has no language parameter.
- **Testing.** Tests must prove "no network call" on many paths, and offline mode must run the same code as live mode.
- **Data.** The claim-desk data files do not match the spec's catalog schema. They use camelCase, have no `groups`, `point_param`, `first_year` or `regional`, and store country names as plain strings.

## Usage (caller's view)

**A route.** Routes are synchronous and a few lines long. Errors are raised, never returned.

```python
@app.post("/api/run")
def api_run(body: dict = Body(...)) -> Result:
    question, revision = reader.question_from(body)          # guard(via="link"|"form"); QuestionError -> 400
    return analyses.run(question, revision=revision, lang=body.get("lang", "en"))
```

**An analysis.** It asks for data, calls stats, and states facts. It never writes a headline, never formats a number by hand, and never sees `quote`, `via`, or an HTTP client.

```python
def trend(q: TrendQ, w: Words) -> Finding:
    v = catalog.variable(q.variable)
    s = series.get_series(q.region, q.variable, q.window)
    fit = stats.trend_test(s.years, s.values, rel=v.rel)       # TooShort -> 400 {field: "window"}
    facts = {"place": catalog.name(q.region, w.lang), "change_per_decade": fmt(fit.slope_per_decade), ...}
    return Finding(verdict=Verdict(key=f"trend.{fit.level}", level=fit.level), facts=facts, tiles=[...], ...)
```

**The registry.** This is the one list of kinds.

```python
ANALYSES: dict[Kind, Analysis] = {
    "claim": Analysis(ClaimQ, claim.claim, claim.VERDICTS),
    "trend": Analysis(TrendQ, trend.trend, trend.VERDICTS),
    "where": Analysis(WhereQ, where.where, where.VERDICTS),
}
```

**A test.** An autouse fixture seals the network and the model in every test. A test that expects traffic asks for a counting stub.

```python
def test_ai_and_keywords_give_one_result(power, model):
    model.reply = {"kind": "claim", "region_id": "KHM", "tests": [{"variable": "heat", "direction": "up"},
                   {"variable": "rain", "direction": "down"}], **NULLS}
    a = reader.read("Cambodia is getting hotter and drier", "en", ai=True)
    k = reader.read("Cambodia is getting hotter and drier", "en", ai=False)
    assert analyses.run(a.question) == analyses.run(k.question)   # Result has no quote or via to strip
    assert power.calls == 0                                       # a country reads data/v, never POWER
```

**The screen.** The card and the result never name a kind.

```js
const viewCard = () => S.kinds[S.question.kind].fields.map(f => EDITORS[f.name](S.question[f.name], v => edit(f.name, v), f));
const kindPanel = r => PANELS[r.kind]?.(r.detail) ?? "";
```

## Shape

### Data structures

1. **`Analysis` record** (`analyses/base.py`) holds `question` (the pydantic model), `fn` and `verdicts`. Everything another module needs to know about a kind is a field here. The card's fields come from `question.model_fields`.
2. **`Finding`** is what one analysis decides: `verdict, facts, tiles, charts, method, sources, notes, detail`. It has no `headline`. `analyses.run()` is the only code that builds a `Result`. It writes the headline from `words[<verdict key>.headline]` and `facts`, adds the second-look and synthetic-data notes, removes duplicate sources, and checks that the verdict key was declared. "The headline comes from the verdict level, never from the model" is therefore true by construction.
3. **`Fact = str | int | bool | None`.** There is no `float`. A number can only enter `facts` through `stats.fmt` or `stats.fmt_p`. The number check splits fact values and model text with the same tokenizer, so it compares like with like.
4. **Per-kind detail models** (`ClaimDetail`, `TrendDetail`) live in the kind's own module and are dumped into `Result.detail: dict`. On the wire, `detail` stays a `dict`, as SPEC says.
5. **`words.EN` and `words.KM`** form one flat table of every sentence the server writes. The keys are `<verdict>.headline`, `<verdict>.<audience>.short|more`, `tile.<id>.label|note`, `step.<id>.title|did|why`, `note.*`, `word.*`.
6. **`Source`** is one entry of `data/sources.json`, the reference registry in `docs/16-data-sources.md`: `id, name, short_name, version, agency, center, doi, url, citation, via, accessed, cached`. `catalog.sources()` parses the file. `Series.sources` lists the dataset, its method paper, and `power` when the values came through NASA POWER. A series always has at least one. `analyses.run()` removes duplicate sources by `id`. Only `cached` changes at run time.
7. **`reader.FILL`** (in Python) and **`EDITORS`** (in `app.js`) are both keyed by field name. Thirteen field names cover all eight kinds. A new kind that reuses existing field names needs no reader code and no card code.

### Flow

```
text ─► read_keywords | read_ai ─► raw (flat) ─┐
card kind switch (partial Question) ───────────┼─► guard(raw, quote, via) ─► Draft ─► Question.validate
share link / Run ({question, revision}) ───────┘        FILL[name] for each field of ANALYSES[kind]
Question ─► analyses.run(q, revision, lang) ─► ANALYSES[kind].fn(q, Words(lang)) ─► Finding ─► Result
   fn ─► series.get_series / get_many ─► data/v file | power ─► net.get_json ─► cache | httpx
Result ─► explainer.explain ─► words template | net.ask_model + numbers_ok
```

The longest call chain is route → `analyses.run` → the kind's `fn` → `series` → `power` → `net`.

### Load-bearing decisions

1. **A kind is a record, and a field name is the unit of reuse** (per encode-lessons-in-structure).
2. **One sentence table and one `Result` constructor.** Wording is a pure function of the verdict key and `facts`.
3. **Synchronous code with one network door** (per boundary-discipline and laziness-protocol).
   - `net.get_json` owns the httpx client, the retry policy, the 3-request `BoundedSemaphore`, and the cache read and write. `net.ask_model` owns the Bedrock call.
   - Offline mode and the tests both swap the httpx *transport*. Every layer above it (the 422 retry, fill values, the cache, monthly-to-annual) runs the same code in all three modes.
   - Fan-out is one function, `series.get_many`, on a thread pool. The semaphore caps real requests to POWER at 3, and cache hits skip it.

### Invariants and where they live

| Invariant | Enforced by |
|---|---|
| `quote` and `via` never change a number | `Question` has no such fields, and `fn(q, w)` cannot see them |
| Every number in `facts` is formatted exactly once | `Fact` has no `float` |
| The headline comes from the verdict key and `facts` | `Finding` has no headline, and only `run()` builds a `Result` |
| An analysis returns only declared verdict keys | `run()` checks membership, and `test_words` enumerates the same tuple |
| A 400 always names a field | `QuestionError(field)` is the only 400 path. `TooShort` is a `QuestionError("window")`. A bare `ValueError` is a 500 |
| No test reaches the network unless it asks to | the autouse `sealed` fixture installs a transport and a model stub that both refuse |
| Synthetic data never enters the real cache | `EB_OFFLINE=1` forces the cache to `:memory:` |
| Statistical constants appear once | `stats.T`, plus a grep test for literal thresholds outside `stats.py` |
| Every source is registered, from an agency in `catalog.ALLOWED_AGENCIES`, and cited by a DOI or the provider's acknowledgement text | `tests/test_sources.py`; `tools/check_refs.py` resolves every DOI |
| A network call names a registered source | `net.get_json` raises `ValueError` on an unknown `source` id |
| `net.get_json` fetches only from `*.nasa.gov` and `nasa-power.s3.amazonaws.com` | `net.get_json` raises `ValueError` on any other host |
| No code or page points at a host outside those two and `doi.org` for citation links. The SDK builds the Bedrock URL from the AWS region | `test_no_url_outside_allowed_hosts` scans every text file in `earthbuddy/` and `web/`, ignoring case, for `http`, `ws` and scheme-relative URLs |
| No code, data or page names Natural Earth, Nominatim, Open-Meteo or OpenStreetMap | `test_no_removed_provider_in_code_data_or_web` searches `earthbuddy/`, `web/`, `data/` and `tools/` |
| Layers stay layered | `tests/test_layers.py` walks each module's `ast` imports against the table below |

### Interface depth

- `analyses.run(q, revision, lang) -> Result` is the whole analysis surface. Data access, statistics, all prose, the notes and the invariant checks sit behind it.
- `series.get_series / get_many / get_grid` hide file versus live source, window clipping, monthly-to-annual rules, seasonal sums, concurrency, the cache and retries.
- `net.get_json / ask_model` hide the transport choice, retries, backoff, the semaphore, the cache, the SDK, timeouts and refusals.
- `reader.read / reread / question_from` hide two readers, the guard, geocoding, and the mapping from errors to field names.
- `explainer.explain` hides templates, the model call, the number check and the fallback.

### What it does not do

- No async code and no injected `Context`.
- No session state on the server (`/api/explain` takes the `Result` back).
- No load-time adaptation of the prototype data.
- No plugin loading: the registry is a literal dict.
- No validation in JS beyond "a required field is empty".

## Module map

| File | Owns | Public surface | Never imports |
|---|---|---|---|
| `types.py` | every wire type and every error | regions, the 8 `*Q` models, `Question`, `Kind`, `Draft`, `ReadResult`, `Series`, `Source`, `Fit`, `Verdict`, `Chart` union, `Seg`, `Tile`, `Step`, `Fact`, `Result`, `Explanation`, `QuestionError`, `TooShort`, `DataSourceError`, `AIFailed` | any `earthbuddy` module |
| `stats.py` | `T`, `fmt`, every p-value, slope and verdict. No I/O | `T`, `fmt`, `fmt_p`, `trend_test`, `pettitt`, `is_step`, `bh`, `test_claim`, `claim_verdict`, `sen_at`, `size`, `coin`, `stl`, `seasonal_cycle` | anything except `types` |
| `words.py` | every server sentence (`en` and `km`), digit handling | `Words`, `EN`, `KM`, `ascii_digits`, `number_tokens`, `HAS_DIGIT` | anything except `types` |
| `cache.py` | the SQLite table | `get`, `put`, `stats`, `reset` | any `earthbuddy` module |
| `fixtures.py` | synthetic POWER-shaped responses | `handler(request)` | any `earthbuddy` module |
| `net.py` | the only network door (NASA hosts and Claude on Amazon Bedrock only), the offline swap, test stubs | `get_json`, `ask_model`, `ai_available`, `model_id`, `OFFLINE`, `stub` | `catalog`, `power`, `series`, `analyses`, `reader`, `explainer`, `server` |
| `catalog.py` | `data/catalog.json`, `data/v/*.json`, `audit.json`, `sources.json`; names, aliases and centres | `load`, `sources`, `ALLOWED_AGENCIES`, `variable`, `variables`, `name`, `centre`, `cells`, `find_region`, `group`, `years`, `regional_values`, `audit`, `raw` | `net`, `power`, `series`, `stats`, `analyses`, `reader` |
| `power.py` | POWER URLs and payload parsing | `point`, `grid`, `last_complete_year`, `Monthly` | `catalog`, `series`, `stats`, `analyses` |
| `geocode.py` | free text to `Point`, offline: coordinates, the catalog, then the local NASA SEDAC gazetteer `data/gazetteer.json` | `search` | `net`, `power`, `series`, `stats`, `analyses`, `reader` |
| `series.py` | the only way an analysis gets data | `get_series`, `get_many`, `get_grid`, `annualise` | `analyses`, `reader`, `net` (it goes through `power`) |
| `analyses/base.py` | `Analysis`, `Finding`, shared chart and fact helpers | `Analysis`, `Finding`, `fit_or_none`, `per_decade`, `line_chart` | `reader`, `explainer`, `server`, `net`, `power` |
| `analyses/<kind>.py` | one kind: its detail model, `VERDICTS`, its function | `<kind>`, `VERDICTS`, `<Kind>Detail` | other kind modules, `net`, `power`, `reader` |
| `analyses/__init__.py` | the registry, and the only `Result` constructor | `ANALYSES`, `run`, `kinds_meta` | `reader`, `explainer`, `server` |
| `reader.py` | sentence or raw dict to `Draft` and `Question` | `read`, `reread`, `question_from`, `guard`, `read_keywords`, `FILL` | `series`, `power`, `explainer`, `server` |
| `explainer.py` | the explanation and the number check | `explain`, `numbers_ok` | `series`, `power`, `reader`, `server` |
| `__init__.py` | `ROOT`, `SOURCES`, and the `.env` loader that runs on import | `ROOT`, `SOURCES` | — |
| `server.py` | routes, error mapping, static files | `app` | — |
| `tools/build_catalog.py` | one-time data adaptation (`--adapt`), `summary.json`, `--check` | CLI | not imported by the app |

`web/` holds `index.html`, `app.js` (state, views, `EDITORS`, `PANELS`), `charts.js` (`CHARTS`), `map.js`, `i18n.js` (`EN`, `KM`, `t`), `styles.css` and `vendor/`. See "Client" for how they load and what each owns.

## Keeping lists in sync

| List | Home | Other copies | How they stay equal |
|---|---|---|---|
| kinds | `ANALYSES` (built kinds) | `Kind` literal, `Question` union | `test_registry`: `ANALYSES` keys ⊆ `Kind` == union members |
| card fields per kind | `Question` models | none (`/api/catalog.kinds`) | derived. There is no JS `FIELDS` table |
| field names | `Question` models | `reader.FILL`, JS `EDITORS`, i18n `field.*` | `test_registry` and `test_web_sync` |
| kind panels | JS `PANELS` (optional) | `ANALYSES` | `test_web_sync`: keys ⊆ kinds |
| chart types | `Chart` union | JS `CHARTS` | `test_web_sync`: the sets are equal |
| verdict keys | `Analysis.verdicts` | `words.EN` | `test_words`. `run()` also asserts membership |
| reader cues | `reader.CUES` | none | single source, covering every kind in `docs/04`, built or not. The AI schema's kind enum is every `Question` kind |
| thresholds | `stats.T` | none | grep test |
| server strings | `words.EN` | `words.KM` | `test_words`: KM keys ⊆ EN keys, with the same placeholders |
| UI strings | `i18n.js EN` | `KM`, the `t("...")` calls | `test_web_sync`, per `docs/15` |

`test_web_sync.py` reads JS tables with regexes over `const NAME = {` … `};`, one key per line. No Node and no build step are needed. Each JS table carries a comment stating this layout.

## Backend runtime

### Entry points

| File | Used by | What it does |
|---|---|---|
| `main.py` | Vercel | One line, `from earthbuddy.server import app`. Vercel imports `app` from it. |
| `run.py` | You, locally | Calls `net.refuse_offline_on_vercel()`, then starts `uvicorn` on `earthbuddy.server:app` with `reload=True`. `EB_HOST` (default `127.0.0.1`) and `EB_PORT` (default `8000`) set the address. |

Importing the `earthbuddy` package loads `.env` (see "The `.env` loader"). Importing `earthbuddy/server.py` calls `net.refuse_offline_on_vercel()` and builds the `app`. Nothing else runs at import time. The server keeps no session state. The only state is the SQLite cache and the parsed `data/` files, which `catalog.py` caches in memory with `functools.cache`.

### Routes

`earthbuddy/server.py` registers these routes, in this order. Every route is a plain `def`, so FastAPI runs it on a worker thread. Every error body is JSON.

| Method and path | Body or query | Returns | Errors |
|---|---|---|---|
| `GET /api/status` | none | `{ai_available, model, offline, last_complete_year, cache: {entries, bytes}}` | none |
| `GET /api/catalog` | none | the contents of `data/catalog.json`, plus `kinds`, the fields of each built kind | none |
| `GET /api/sources` | none | the list in `data/sources.json` | none |
| `POST /api/read` | `{text?, draft?, lang: "en" \| "km" = "en", ai: bool = false}` | `{draft, question \| null, missing, ai_failed}`. With `draft`, it re-reads the card and never calls the model. Otherwise it reads `text`. | 400 for empty text or text over 600 characters (`field: "text"`), a bad `lang`, or a malformed body |
| `POST /api/run` | `{question, revision?, lang? = "en", via?}`. `via` counts only when it is `form`, `link` or `audit`. Any other value becomes `link`. | `Result` | 400 for a bad question (`field` names the first bad or missing field), a `lang` other than `en` or `km`, or a body that is not an object. 502 when a NASA source fails. |
| `POST /api/explain` | `{result, audience: "student" \| "policymaker" \| "researcher" = "student", lang = "en", ai = false}` | `{short, more, via: "ai" \| "template"}` | 400 for a malformed body. A model failure is not an error. The route returns the template text. |
| `GET /api/geocode` | `q`, 1 to 600 characters | `{results: [Point]}` | 400 for a missing or oversized `q` |
| `GET /api/audit` | `lang = "en"` | the frozen audit, with a live `question`, `verdict` and `verdict_word` added to each claim | 400 for a bad `lang`. The 502 handler also covers it. |
| `GET /data/countries.geojson` | none | `data/countries.geojson`, as `application/geo+json` | none |
| `GET /data/summary.json` | none | `data/summary.json` with a boolean `clear` added to every row (`row["q"] < T.fdr_q`) | none |
| `GET /` and `GET /index.html` | none | `web/index.html` with `Cache-Control: no-store` | none |
| `GET /<path>` | none | the file at `web/<path>`, served by `StaticFiles` | 404 |

`POST /api/run` never accepts `via: "ai"`. A client cannot claim that the model wrote a question. A body without `revision` runs as revision 0.

**Check against SPEC.** The API table in `SPEC.md` lists `POST /api/hear` and `GET /api/say`, and a `voice` object in `/api/status`. They belong to row 14a. `earthbuddy/voice.py` does not exist, neither route is registered, and `GET /api/hear` returns 404. `/api/status` returns `offline` and no `voice`. The routes in the table above that `SPEC.md` does not list are `/data/countries.geojson` and `/data/summary.json`. The "Deviations from SPEC" table records the other differences, which are the `lang`, `via` and `draft` fields. SPEC's 503 `voice` error does not exist yet.

A wrong method on an API path does not return the same status everywhere. `GET /api/read` returns 404, because the static mount at `/` matches the path first. `POST /api/status` returns 405.

### Static files

`app.mount("/", StaticFiles(directory=web))` is registered last, so every `/api/*` and `/data/*` route above wins. `index.html` has its own route so the page is never cached. Other static files carry no `Cache-Control` header.

The server never mounts `data/`. Two explicit routes expose the two files the map needs. A request for `/data/catalog.json` or `/data/cache.sqlite` returns 404, and so do `/main.py`, `/SPEC.md` and `/earthbuddy/server.py`.

### Error mapping

Three handlers in `server.py` map every error. Anything else is a bug and surfaces as a 500.

| Status | Raised as | Body |
|---|---|---|
| 400 | `QuestionError(field)`, which includes `TooShort` | `{error, kind: "request", field}` |
| 400 | FastAPI `RequestValidationError` | `{error: "bad request", kind: "request", field}`. `field` is the first part of the error location that is not `body` or `query`, or `""`. |
| 502 | `DataSourceError(message, status, url)` | `{error, kind: "data_source", url}` |
| 500 | any other exception | Starlette's default 500 response. No test or check run here raises one. |

`AIFailed` never reaches a client. `reader.read` turns it into `ai_failed: true` and answers with the keyword reader. `explainer.explain` turns it into the template text.

### The `.env` loader

`earthbuddy/__init__.py` reads `<repo>/.env` when the package is first imported. It reads one `KEY=value` per line, skips lines that start with `#`, and strips whitespace and one pair of quotes from the value. It does not handle `export`, inline comments or multi-line values. It calls `os.environ.setdefault`, so the order of precedence is the real environment, then `.env`, then the default in the code. `.env` is in `.gitignore` and `.vercelignore`. Copy `.env.example` to `.env` to start.

### The cache

`earthbuddy/cache.py` holds NASA POWER responses in one SQLite table, `cache(key, payload, source, fetched_at)`. The key is the full request URL. The payload is zlib-compressed JSON. `power.TTL_DAYS` is 30. One connection and one lock serve all threads.

`cache._path()` picks the file in this order.

1. `:memory:` when `EB_OFFLINE=1`.
2. `EB_DB`, when set.
3. `/tmp/eb/cache.sqlite`, when `VERCEL` is set.
4. `data/cache.sqlite` under the repository root.

The code creates the parent directory and the table on first use, and `GET /api/status` is enough to trigger that. On Vercel the deployed bundle is read-only, so the default there is `/tmp`, and the code never writes into the bundle. A call to production `/api/status` on 2026-11-14 returned `cache: {entries: 0, bytes: 0}`, which shows that the function could open `/tmp/eb/cache.sqlite`.

The code has no fallback when the cache file cannot be opened or written. The error would surface as a 500. Each function instance has its own `/tmp`, so instances do not share cache entries. That second point follows from how serverless instances work and was not measured here. A cold instance starts with an empty cache and fetches from NASA again.

### Offline mode

`EB_OFFLINE=1` swaps the HTTP transport in `net.py` for `httpx.MockTransport(fixtures.handler)`. Every layer above the transport still runs, so retries, the 422 retry, fill values and monthly-to-annual rules behave as in live mode. Four things change.

- POWER calls return synthetic POWER-shaped data from `earthbuddy/fixtures.py`. Country and place series still come from the real files in `data/v/`.
- The cache is in memory, so synthetic data never lands under a real NASA URL.
- `ai_available()` returns false, so AI is off.
- `GET /api/status` reports `offline: true`, and `analyses.run` puts the `note.synthetic` note first in `Result.notes`.

`net.refuse_offline_on_vercel()` exits the process when both `EB_OFFLINE=1` and `VERCEL` are set. It runs when `server.py` is imported and when `run.py` starts.

### Timeouts and concurrency

| Limit | Value | Where |
|---|---|---|
| Function duration on Vercel | 300 s | `vercel.json`, `maxDuration` |
| NASA request timeout | 120 s, with a 20 s connect timeout | `net._http()` |
| NASA request attempts | 4. Retries follow a transport error, a 429 or a 5xx. Another 4xx fails at once. | `net.ATTEMPTS`, `net.get_json` |
| Wait before attempts 2, 3 and 4 | 1.5 s, 3 s, 6 s | `net.BACKOFF_S` |
| NASA requests in flight, per process | 3. A cache hit does not use a slot. | `net.MAX_INFLIGHT` |
| Fan-out threads for `series.get_many` | 8 | `series.py` |
| Model call timeout | 10 s, one attempt (`max_retries=0`) | `net.MODEL_TIMEOUT_S`, `net._anthropic()` |

A check run on 2026-11-14 pointed `HTTPS_PROXY` at a closed port and posted a point question to `/api/run`. The route returned 502 with `kind: "data_source"` after 10.6 s, which matches the three waits of 1.5, 3 and 6 s.

The limits above allow one request to run longer than 300 s. Four attempts that each wait out the 120 s timeout take 480 s. That case was not exercised.

## Client

### Files and loading

The client is plain files that the browser runs as written. `index.html` names each file directly, and the repository has no `package.json`, bundler config or `node_modules`. The tests read the JS tables with regexes, so CI needs no Node either.

`index.html` loads five classic scripts with `defer`, in this order. They share one global scope. They are not ES modules.

1. `i18n.js` defines `esc`, `EN`, `KM` and `t`.
2. `charts.js` defines the SVG helpers and `CHARTS`.
3. `vendor/maplibre-gl/maplibre-gl.js` defines `maplibregl`.
4. `map.js` defines `M`, `mapInit`, `mapShow` and the map layers. It reads `S`, `byId`, `opt` and `varName` from `app.js` at run time.
5. `app.js` defines the state `S` and the views, then calls `boot()`.

| File | Owns |
|---|---|
| `web/index.html` | The shell, with the sidebar, top bar, thread, composer, the `#picker` dialog and the parked map. A `<noscript>` line says the app needs JavaScript. |
| `web/app.js` | State `S`, the render loop, every view, `EDITORS`, `PANELS`, the `ACTIONS` table, the API calls, the share link and `boot()`. |
| `web/charts.js` | The five chart renderers and the `CHARTS` table. They return SVG strings. |
| `web/map.js` | The MapLibre map, its layers, the legend and the click handler. |
| `web/i18n.js` | `esc`, the string tables `EN` and `KM`, and `t()`. |
| `web/styles.css` | All styles. It defines colours and sizes as custom properties on `:root`, sets `color-scheme: light`, and has breakpoints at 900 px and 560 px. `html:lang(km)` switches the font stack to Noto Sans Khmer first. |
| `web/vendor/` | MapLibre GL and the fonts. |

**Vendored libraries.** `web/vendor/maplibre-gl/` holds MapLibre GL JS 5.24.0 (the version in the license URL in the header of `maplibre-gl.js`, BSD 3-clause), with its CSS and `LICENSE.txt`. `web/vendor/fonts/` holds Geist, Geist Mono and Noto Sans Khmer as woff2 files, plus `fonts.css` and two OFL license files. `fonts.css` says these are self-hosted copies of the Google Fonts files. The files give no font version, so none is stated here. `web/` is 1.4 MB in total, and `maplibre-gl.js` is 1,056,837 bytes of that.

Every interpolated value goes through `esc()` or `t()`. Nothing from the server or the URL reaches `innerHTML` unescaped.

### State and the render loop

`S` holds all app state. The fields are `lang`, `ai`, `region` (the region picked in the top bar), `thread` (one entry per question), `editing` (the id of the one entry whose card is open), `mapFor` (the id of the entry that holds the map), `linkFailed`, `pick` (the region dialog's own state), and the loaded `catalog`, `status`, `sources` and `audit`. An entry holds one question's life, from its `text` and `read` to its `question`, `revision`, `result` and `explanation`.

`render()` rebuilds the whole thread.

1. It remembers the id of the focused element.
2. It sets `#thread.innerHTML` from `viewThread()`, or from a loading line until the catalog arrives.
3. It rebuilds the `#picker` dialog when the dialog is open.
4. `placeMap()` moves the one map element into the first `[data-map-slot]`, in the dialog if it is open, else in the thread. With no slot it parks the map in `#map-park`.
5. It puts focus back on the element with the remembered id.

The sidebar, top bar and composer are not part of `render()`. `boot()` draws them once. `renderTop()` runs again when the region changes.

`call(h, busy, path, body)` makes every API call except `explain`. `h` is an entry or `S.pick`. The call takes the next number from `h.seq` and applies its answer only if that number is still the latest and `h` is still live. A stale answer is dropped. A failed call stores the server's error body, or `{kind: "network"}` when the body has no `kind`. `explain` has its own counter, `explainSeq`.

Events use delegation on `document.body`. A click on any `[data-act]` element runs `ACTIONS[act](el, entry)`. The `change`, `input`, `toggle` and `keydown` handlers cover the AI switch, the card fields, the audience radios, the region search, the Escape key, Enter in the composer and the arrow keys on chart tabs.

### Views

There is no router and no separate page. The page shows these views.

| View | Function | Shown when |
|---|---|---|
| Start | `viewStart` | the thread is empty. It shows the five demo sentences as chips, a "Build it by hand" link, and the audit strip once `/api/audit` has answered. |
| Entry | `viewEntry` | one per thread entry. It shows the question bubble, then the card, the result, a status line, or an "unfinished" prompt. |
| Card | `viewCard` | `S.editing` is this entry. It shows the kind select, one editor per field of the kind, the leads and unmapped notes, **Run** and **Back**. |
| Result | `viewResult` | the entry has a result. It shows the verdict badge, the headline, an "asked" line after an edit, the explanation, and the buttons **Show charts**, **Edit** and **Share**. |
| Charts block | `viewCharts` | the person opened **Show charts**. It shows the tiles, the chart tabs, the map slot, the kind panel, the method steps and the sources. |
| Region picker | `viewPicker` | the `#picker` dialog is open. It has a place search and the map. |
| Sidebar | `renderSide` | always. It has **New analysis**, the topics list, **Data sources**, and the AI switch. Below 900 px it is a drawer behind **Menu**. |
| Top bar | `renderTop` | always. It has the **Menu** button and the region button. |
| Composer | `renderComposer` | always. A textarea limited to 600 characters. Enter sends. Shift+Enter starts a new line. |

The "About the data" text is the **Data sources** group in the sidebar. The link under the composer opens it.

The flow of one question is this. `ask(text)` posts to `/api/read`. `proceed(e)` then decides. If the reading lacks a `region` or `point` and the person picked a region, it fills the field and reads again. If the question is complete, it runs. A kind that needs a point but names a variable with no `point_param` in the catalog is blocked, so the card opens with a reason. Any other incomplete reading opens the card.

### Tables

Four tables hold what varies by kind or field. Each is one `const NAME = {` block with one key per line, because `tests/test_web_sync.py` reads them with a regex.

| Table | File | Keys | Purpose |
|---|---|---|---|
| `EDITORS` | `app.js` | the 13 field names `region`, `point`, `tests`, `variable`, `x`, `y`, `window`, `baseline`, `among`, `metric`, `order`, `top_n`, `year` | Each value has `view`, `change` and `text`. The card draws `S.catalog.kinds[kind].fields` through it. A kind that reuses these field names needs no card code. |
| `PANELS` | `app.js` | `claim`, `trend`, `scan`, `where` | The panel under the charts. Optional. A kind with no panel renders without one. |
| `CHARTS` | `charts.js` | `line`, `bars`, `scatter`, `cells`, `intervals` | One renderer per `Chart` type. Each draws a 640-wide SVG, and a table of the same numbers for screen readers. |
| `EN` and `KM` | `i18n.js` | every UI string | Two JSON objects between `/*json*/` and `/*end*/`. |

`t(key, vars, wrap = esc)` looks the key up in `KM` when `S.lang` is `"km"`, then in `EN`, then falls back to the key. It replaces each `{name}` with `wrap(vars[name])`. Pass `String` as `wrap` for text that is already safe.

**Khmer is not built.** `KM` is `{}`, and so is `words.KM` on the server. `S.lang` starts as `"en"` and no control changes it, so the app is English only. The client still sends `lang` on every call, so the server side is ready.

### How the client calls the API

| When | Request |
|---|---|
| Boot | `GET /api/catalog`, `GET /api/status` and `GET /api/sources` in parallel. If any fails, the page shows a network error. Then `GET /api/audit?lang=` without blocking. |
| Ask | `POST /api/read {text, lang, ai}`. `ai` is true only when the switch is on and `status.ai_available` is true. |
| Card edit, region fill, topic click | `POST /api/read {draft: {fields, quote, leads, unmapped, revision}, lang}`. This never uses AI. |
| Run | `POST /api/run {question, revision, lang}`. An audit claim adds `via: "audit"`. |
| Explain | `POST /api/explain {result, audience, lang, ai}`. With AI on, the client sends two calls. The first has `ai: false` and shows at once. The second has `ai: true` and replaces the first only when its `via` is `"ai"`. |
| Place search | The client matches a catalog name first. If none matches, it calls `GET /api/geocode?q=`. |
| Map | `GET /data/countries.geojson`, `GET /data/summary.json` and `GET /api/sources`. |

An error body with `kind: "request"` shows the field name through the `field.<name>` string in `EN`. `kind: "data_source"` shows the NASA error. Any other failure shows the network error.

### The AI switch

The switch is the `#ai` checkbox with `role="switch"` in the sidebar. Its label is "AI reader". Its note is "Sends your sentence to Claude on Amazon Bedrock (AWS) to read it. Numbers always come from NASA data and our code." The switch starts off. It shows as checked only when `S.ai` is true and `status.ai_available` is true.

When the server reports `ai_available: false`, the switch is disabled and the note adds "This server has no AWS credentials for the AI, so the keyword reader is used." The footer under the composer and the **Data sources** group repeat the AI statement. `test_ai_switch_note_is_the_label_in_the_spec` keeps the note equal to the one in `docs/14-web-ui.md`.

### The share link

A link is `<origin><path>#q=<code>`. `<code>` is the base64url encoding, without padding, of the UTF-8 JSON `{"question": <the result's question>, "revision": <the revision it ran at>}`. The link carries the question and not the result, so opening it runs the question again on current data. It carries no language and no AI choice.

`showResult` writes the hash with `history.replaceState` after each result, so the address bar always holds a valid link and the back button gains no entries. **Share** copies the link with `navigator.clipboard`. When copying fails, it shows the link in a read-only box.

`route()` runs at boot and on `hashchange`. For a `#q=` hash it decodes the code, clears the thread, and posts `{question, revision, lang}` to `/api/run`. The server reads it with `via: "link"`. A code that does not decode, or a question the server rejects, shows the "link" error and clears the hash.

### Browser storage

The client stores one value. `localStorage["eb-ai"]` holds `"1"` or `"0"`, the state of the AI switch. Both reads and writes sit in `try` blocks, so a browser that blocks storage still works with AI off. The client uses no cookies, `sessionStorage` or IndexedDB.

### The map

`map.js` draws one MapLibre map with these layers, bottom to top.

| Layer | Source | Draws |
|---|---|---|
| `gibs` | NASA GIBS raster tiles | the background |
| `countries` | `/data/countries.geojson` | country fills. A country is coloured only when its `clear` flag in `/data/summary.json` is true for the chosen variable. The colour is warm or cool by the sign of `trend_per_decade`, and stronger as the trend grows. Every other country is grey (`#8a918d`). |
| `borders` | the same GeoJSON | white outlines |
| `cells` and `outline` | the `result` source | the grid cells of a `where` result, or the outline of the question's region |
| `point` | the `result` source | a circle for a coordinate point |

The tile source is the one `docs/16-data-sources.md` allows, NASA GIBS. The URL is `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg`, with `tileSize` 256 and `maxzoom` 8. The attribution is the `citation` of the `gibs-bluemarble` source from `/api/sources`. `test_no_url_outside_allowed_hosts` scans `web/` for any other host.

The map starts at longitude 104.9, latitude 12.6, zoom 3, with a maximum zoom of 9. A click turns the position into a point with two decimals and the name `"<lat>, <lon>"`. If the click lands on a catalog country, `mapPicked` also gets that country. It then does one of three things. In the region dialog it sets the region. With a card open that has a `point` or `region` field, it edits that field. Otherwise it asks how the map's variable is changing at the click. A select in the legend changes the variable.

`mapShow(result)` loads the overlay and fits the view to it. If MapLibre does not load, or the two data fetches fail, `loadMap()` returns false and `mapShow` does nothing, so the rest of the page still works.

## Configuration

Every environment variable the code reads is below. The real environment wins over `.env`, and `.env` wins over the default.

| Name | Read in | Default | Effect |
|---|---|---|---|
| `EB_HOST` | `run.py` | `127.0.0.1` | The address the local server binds to. |
| `EB_PORT` | `run.py` | `8000` | The port the local server listens on. |
| `EB_DB` | `cache.py` | unset | Path of the SQLite cache file. `:memory:` is allowed. It overrides the Vercel default. `EB_OFFLINE=1` overrides it. |
| `EB_OFFLINE` | `net.py`, `cache.py` | unset | Exactly `1` serves synthetic POWER data, keeps the cache in memory and turns AI off. The process refuses to start if `VERCEL` is also set. |
| `EB_MODEL` | `net.py` | `au.anthropic.claude-haiku-4-5-20251001-v1:0` | The Bedrock model ID for every model call. `/api/status` reports it. The code reads it on each call. |
| `EB_AWS_REGION` | `net.py` | `ap-southeast-2` | The AWS region of the Bedrock client. The code reads it once, on the first model call, so a change needs a restart. |
| `AWS_BEARER_TOKEN_BEDROCK` | `net.py`, the SDK | unset | A Bedrock API key. Setting it makes `ai_available()` true. |
| `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` | `net.py`, the SDK | unset | An IAM access key pair. Both must be set for `ai_available()` to be true. |
| `VERCEL` | `cache.py`, `net.py` | set by Vercel | Moves the default cache to `/tmp/eb/cache.sqlite`, and blocks `EB_OFFLINE=1`. |
| `POWER_COMMUNITY` | none | none | Listed in `.env.example` and `docs/00-foundation.md`. No code reads it. `power.py` sends `community=AG` as a literal. |

`ai_available()` is true only when `EB_OFFLINE` is not `1` and either `AWS_BEARER_TOKEN_BEDROCK` or both access key variables are set. With none of them set, `/api/status` reports `ai_available: false`, the AI switch is disabled, and `ask_model` raises `AIFailed("no AWS credentials")`. A client that sends `ai: true` anyway gets the keyword reader with `ai_failed: true`. Other variables that the AWS credential chain might read, such as a profile name or a session token, are not verified here.

## Build and deploy

### What Vercel builds

There is no build step in the repository. Vercel installs `requirements.txt` and bundles the function from `main.py`.

`vercel.json` is the whole Vercel configuration.

```json
{
	"functions": { "main.py": { "maxDuration": 300, "includeFiles": "{data,web}/**" } }
}
```

- `maxDuration` is 300 seconds for the function.
- `includeFiles` adds `data/` and `web/` to the bundle. The app reads both at run time. `data/` is 6.3 MB and `web/` is 1.4 MB.
- The file sets no `regions`. The function runs in the project's default region, and the repository does not pin one. The region in the Vercel dashboard was not checked.
- It has no `rewrites`, and `tests/test_deploy.py` asserts that none exists. The Vercel FastAPI preset sends every path to `app`, and a rewrite breaks the paths.

`.vercelignore` keeps `.env`, `.env.*`, `data/cache.sqlite`, `.venv/`, `.claude/`, `__pycache__/`, `.pytest_cache/` and `tools/cache/` out of the upload. Secrets, the local cache and the virtual environment never leave your machine. The file does not list `tests/`, `docs/` or `tools/`. Which of those end up in the function bundle was not checked.

`requirements.txt` lists ten packages, `fastapi`, `uvicorn`, `httpx`, `pydantic>=2`, `numpy`, `scipy`, `statsmodels`, `pymannkendall`, `anthropic[bedrock]` and `pytest`. Only `pydantic` has a bound, so each build resolves the newest versions. `anthropic[bedrock]` pulls in botocore, which signs the Bedrock requests. The repository sets no Python version for Vercel. The local `.venv` runs Python 3.12.12, and the Python version Vercel used was not verified. On 2026-11-14 the local `.venv` held `fastapi` 0.162.7, `uvicorn` 0.54.0, `httpx` 0.28.1, `pydantic` 2.14.3, `numpy` 2.5.4, `scipy` 1.18.1, `statsmodels` 0.15.0, `anthropic` 2.8.0 and `botocore` 1.44.3. Production resolved its own versions.

### How a change reaches production

This is how the Vercel project behaved on 2026-11-14. The Git integration lives in the Vercel project, not in this repository.

- Every pull request gets a preview deployment. It shows up as the "Vercel" check on the PR.
- A merge to `main` deploys production at https://earth-buddy-analyst.vercel.app.
- Preview and per-deployment URLs sit behind Vercel Authentication. You need a Vercel login to open them.

To ship a change, open a PR, wait for the "Vercel" check, open the preview and try it, then merge. To deploy by hand, `docs/00-foundation.md` names `vercel --prod`. `vercel link` creates the git-ignored `.vercel/` folder and `.env.local`.

### Production environment variables

These are set in the Vercel project for Production. Their values and the IAM policy are not visible from the repository, so this table is the operator's account of them.

| Variable | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | the key of IAM user `earthbuddy-vercel` |
| `AWS_SECRET_ACCESS_KEY` | the secret of the same user |
| `EB_AWS_REGION` | `ap-southeast-2` |
| `EB_MODEL` | the `au.` Haiku 4.5 inference profile ID |

The IAM user can do one thing. It may call `bedrock:InvokeModel` on the `au.` Haiku 4.5 inference profile and on its foundation model in the `ap-southeast-*` regions. A deployment keeps the values it was built with, so a change to any variable takes effect only after a redeploy.

### Check a deployment

Call `GET /api/status`. A healthy production answer has `ai_available: true` and `offline: false`. A call to production on 2026-11-14 returned exactly that, with `model` set to `au.anthropic.claude-haiku-4-5-20251001-v1:0`. In the same session, the five demo sentences in `docs/14-web-ui.md` all returned `via: "ai"` and `ai_failed: false` on production, in 2.0 to 2.9 seconds each.

## Local development and tests

### Run the app

1. Create the environment. `uv` manages it, and it has no `pip`.

   ```
   uv venv --python 3.12 .venv
   uv pip install --python .venv -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in only what you need. With no AWS credentials, AI is off and everything else works.
3. Start the server.

   ```
   .venv/bin/python run.py
   ```

4. Open http://127.0.0.1:8000, or call `curl -s localhost:8000/api/status`.

`run.py` starts `uvicorn` with `reload=True`, so it runs a reloader process and a worker. Stop both by stopping the process that you started. Set `EB_PORT` to run several copies side by side. Set `EB_OFFLINE=1` to work without NASA POWER. The result then carries the synthetic-data note.

### Run the tests

```
.venv/bin/python -m pytest -q
```

At this commit, 208 tests pass in about 27 seconds. `pytest.ini` sets `testpaths = tests`. The tests need no network and no AWS credentials.

`tests/conftest.py` holds one autouse fixture, `sealed`. For every test it sets `EB_DB` to `:memory:` and resets the cache, replaces `net.sleep` with a no-op so retries do not wait, and installs an `httpx.MockTransport` and a model stub that both raise `AssertionError`. A test that expects traffic calls `net.stub(transport=..., model=...)` to allow it.

### Tools

| Command | What it does | Needs |
|---|---|---|
| `python tools/check_refs.py` | Resolves every DOI in `data/sources.json` through doi.org. It exits 1 if one fails. `--markdown` prints the README reference list instead. | network |
| `python tools/build_catalog.py --summary` | Rebuilds `data/summary.json` from `data/v/`. | nothing else |
| `python tools/build_catalog.py --check` | Checks `data/catalog.json` against `data/v/` and `data/sources.json`. It expects 27 variables, 43 places, at least 200 countries and 4 groups. | nothing else |
| `python tools/build_catalog.py --adapt [SNAPSHOT]` | Rebuilds `data/` from the claim-desk snapshot (default `~/earth-buddy-claimdesk-snapshot`) and NASA SEDAC files cached in `tools/cache/`. | `tools/requirements-build.txt`, network, an Earthdata login for SEDAC |

The app never imports `tools/`. Its output is committed, so you run `--adapt` only to rebuild the data.

## Resolved tensions

1. **Sync vs async: sync.** `def` routes run on FastAPI's thread pool. POWER is capped at 3 requests in flight by a global `BoundedSemaphore` in `net`. `series.get_many` has one `ThreadPoolExecutor(8)` and is used by claim, rank, relate and scan.
2. **One list of kinds.** The registry entry is a record. Everything else is derived from it or checked against it (see the table above).
3. **Typing `detail`.** Each kind module defines a pydantic model, and `run()` dumps it to a `dict`. A test round-trips the dict back through the model.
4. **`fmt` and `facts`.** `fmt` and `fmt_p` live in `stats.py`. Each analysis builds its own `facts`. `Fact` has no `float`.
5. **Resolving regions.** `catalog` owns names and centres. `geocode.search` turns free text into a `Point`. It checks the catalog first, then the local gazetteer, and never reaches the network. `reader.FILL["point"]` turns a country or place into its centre point. That conversion depends on the field name, not on the kind.
6. **Offline mode and stubs.** There is one branch, in `net._transport()`. Tests call `net.stub(transport=..., model=...)`.
7. **Data adapter.** `tools/build_catalog.py --adapt` runs once, and its output is committed. `catalog.py` parses strictly and contains no compatibility code.
8. **Errors.** `QuestionError` returns 400, `DataSourceError` returns 502, and anything else is a loud 500. All error mapping lives in three handlers in `server.py`.
9. **Language.** `/api/run` takes an optional `lang`, so all server prose comes from `words`.
10. **Revision.** Analyses never see the revision. `run()` adds the second-look note for any kind.

## Deviations from SPEC

| Deviation | Why |
|---|---|
| `ANALYSES: dict[Kind, Analysis]`, called through `analyses.run` | verdict keys and fields need a home on the one entry |
| reader cues live in `reader.CUES`, not on `Analysis` | a sentence must read into a kind before that kind's analysis exists, and `docs/04` already lists the cues for all eight kinds |
| `/api/read` returns `question: null` for a kind with no `ANALYSES` entry | the card shows the draft, but `/api/run` cannot answer it yet |
| `analyses/` is a package, one module per kind | one doc maps to one file. A single `analyses.py` passes 1,000 lines by row 16 |
| new modules `net.py`, `words.py`, `fixtures.py` | one network door, one sentence table, and synthetic data kept out of `power.py` |
| templates live in `words.py`, not in `explainer.py` | headlines and templates share one key space and one coverage test |
| `Fact` drops `float` | turns the `fmt` rule into a type error |
| `POST /api/run` accepts `lang` | SPEC gives the server the headline but not the language |
| `GET /api/catalog` adds `kinds` | replaces a hand-written JS `FIELDS` table |
| `POST /api/read` accepts `{draft, lang}` | a kind switch on the card goes through `guard`, as `docs/04` requires of card edits |
| `claim_verdict` returns `Scored(verdict, survives, final)` | computing `final` is statistics |
| `detail.second_look` removed; the note applies to all kinds | analyses do not see `revision` |
| catalog `Variable` gains `season`, `per_day`; `aggregate` allows `"max"` | `rain_dry`, `rain_wet`, mm/day rain and `hottest` need data, not `if variable ==` |
| `Source` takes the full registry shape from `docs/16`, not SPEC's short list, and `short_name` and `version` may be null | a method paper has neither |
| `Source.accessed` is `datetime.date \| None`, not SPEC's `str \| None` | pydantic parses and checks the `YYYY-MM-DD` string, and it serializes back to the same text |
| `web/` and server code may link to `https://doi.org/` | `docs/16` wants a DOI link per source on screen. `doi.org` is a citation link only, never a data host for `net.get_json` |
| `/api/status` adds `offline`; `run()` adds the synthetic-data note from `net.OFFLINE` | the banner needs no per-source flag |
| `data/` is never mounted as static files; two explicit routes serve the map files | `data/cache.sqlite` would otherwise be downloadable |
| `cache.py` and `fixtures.py` read `EB_OFFLINE` from the environment directly | keeps them free of package imports |

## Synthesis decision

Three runners (Opus, Fable and Sonnet) each wrote a design independently. All three arrived at the same core: synchronous code with one HTTP seam and a swappable transport; an `analyses/` package with one file per kind; card fields derived on the server; `facts` without floats; a one-time data adapter; and the second-look note for every kind. That agreement is strong evidence for the core.

**Base: candidate B (Fable).** It is the only design where headline wording is structural: a `Finding` has no headline, and `run()` is the only `Result` constructor. It is also the only one where one table-driven `guard` (`FILL`, keyed by field name) accepts both the reader's flat shape and the card's Question shape. That table also absorbs region-to-point coercion.

Grafts:

- **From A (Opus).** `TooShort` subclasses `QuestionError("window")`. `claim_verdict` returns `final` per test, so the outcome rule stays in `stats`. Each JS table holds one key per line so pytest can read it. The test fixture names follow A.
- **From C (Sonnet).** A `Series` validator checks that years and values line up. The JS `panelGeneric` idea: a kind without a panel still renders.
- **From B's own risk list.** `statsmodels` is imported lazily inside `stats.stl()`. The full `requirements.txt` is deployed in hour one to test Vercel's 250 MB function limit early.

Rejected:

- C's per-kind `WORDS`. It leaves Khmer headlines English-only, and Khmer users are the core audience.
- A's verdict keys that include the direction (`trend.clear_up`). They double the keys, and a `{direction}` word fact covers the same need.
- A's `fetch.py` that also holds the cache. B's `cache.py` plus `net.py` keeps the SPEC module name.

No cross-judge ran. The judge pool in `pstack-models` lists only Claude models, the same family as the parent session.

## Tradeoffs accepted

- We accept threads and a semaphore in exchange for no `await` anywhere and plain pytest. The ceiling is one process's thread pool.
- We accept `detail: dict` on the wire in exchange for no second discriminated union.
- We accept `lang` on `/api/run`, so switching language re-runs the question (a cache hit), in exchange for all prose coming from one server table.
- We accept that `/api/explain` trusts the `Result` the client posts. A forged `facts` changes only the forger's own screen.
- We accept that layer rules are a test, not a language feature.
- We accept that every headline variant must be its own verdict key (for example `rank.clear_leader`, `rank.tied`, `rank.none`).
- We accept a rigid layout for the JS tables in exchange for no Node in CI.
- We accept one POWER request per parameter. `# ponytail:` batch the parameters per point if point claims feel slow.

## Alternatives considered

- **The SPEC's flat layout.** One `analyses.py` with `dict[Kind, fn]`, a `FIELDS` literal in JS, and templates in `explainer.py`. A kind's facts would live in four files and two languages, and every analysis would repeat `Result` assembly. Rejected because of the hand-synced lists.
- **Async with an injected `Context`** (the analyst prototype). This puts `await` and `ctx` on every signature to serve two fan-out call sites, and it needs a test plugin. Rejected.
- **A language-neutral `Result` rendered in the browser.** The explainer needs prose on the server, which means two template engines whose placeholders must match the facts across the wire. Rejected.
- **A staged pipeline per kind** (fetch, then compute, then present). This is temporal decomposition: three signatures per kind repeating one shape. `Finding` keeps the one useful split, deciding versus phrasing.
- **Kinds as self-registering plugins.** Pydantic's union, the AI schema and the share-link parser all need a static `Question`. Registering at import time adds magic for no gain.

## Open questions and risks

1. Do the event rules allow copying the prototype data? If not, the adapter becomes a 4-hour rebuild from Zarr, and P0 slips.
2. Answered. Production deploys with numpy, scipy, statsmodels and `anthropic[bedrock]` (see "Build and deploy"). The bundle size against Vercel's limit was not measured.
3. Is the extended API acceptable: `lang` on run, `kinds` on catalog, `draft` on read?
4. If Hamed-Rao fails the AR(1) check at n = 24, `trend_test` switches to the claim desk's variance table, and the audit verdicts move (`docs/12`).
5. The proposed `level` for each claim verdict: supported, opposed and step are `clear`; mixed is `likely`; unsupported is `unclear`; nothing is `too_short`.

## Build status

`SPEC.md` holds the build order. Its table, not this file, says what comes next. At this commit `ANALYSES` holds `claim`, `trend`, `scan` and `where`. The code for rows 1 to 12 exists. The next row in the table is 13, Rank.

These parts of `SPEC.md` are not built yet.

- The kinds `baseline`, `rank`, `extremes` and `relate`. `POST /api/read` returns `question: null` for them.
- Khmer. `words.KM` and the `KM` table in `web/i18n.js` are empty, and the UI has no language switch.
- Voice. There is no `earthbuddy/voice.py`, no `web/voice.js`, and no `/api/hear` or `/api/say` route.
