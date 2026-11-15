# Architecture

How the code in `earthbuddy/` and `web/` is laid out, and why. `SPEC.md` is the contract. This file names every place the code departs from it, in "Deviations from SPEC".

Short version: the code is synchronous. A question kind is one record in `ANALYSES`. A field name is the unit of reuse on both sides of the wire. Every sentence the server writes comes from one table keyed by verdict key. A keyword reader reads the sentence, and a language model can only rewrite the explanation from `facts`. One module, `net.py`, opens every connection, and its data door accepts NASA hosts only. Every source is one entry of `data/sources.json`.

## Data flow

One question, from the sentence to the screen. Each line names the real function and file.

```
sentence
  │   web/app.js ask() ─► POST /api/read {text, lang}
  ▼
reader      reader.read ─► read_keywords (regex cues, catalog names) ─► guard(raw, quote, via) ─► Draft
  │         geocode.search places a name the catalog lacks, from data/gazetteer.json
  ▼
Question    reader._parse checks Draft.fields against the pydantic Question union (types.py)
  │         incomplete ─► the card (app.js viewCard, EDITORS) ─► POST /api/read {draft} ─► reader.reread
  │         complete   ─► POST /api/run {question, revision, lang} ─► reader.question_from ─► analyses.run
  ▼
analysis    ANALYSES[question.kind].fn(q, Words(lang))                    analyses/<kind>.py
  │
  ├─ series   series.get_series | get_many | get_grid                     series.py
  │             Country, Place ─► catalog.regional_values ─► data/v/<variable>.json
  │             Point          ─► power.point | power.grid ─► net.get_json ─► cache.py | NASA POWER
  ├─ stats    stats.trend_test, stats.bh, ...; numbers become strings in stats.fmt, fmt_level, fmt_pair, fmt_p
  ▼
Finding     verdict, facts, tiles, charts, method, sources, detail. It has no headline.
  │         analyses.run adds Words.headline(verdict key, facts), the notes, and investigate()
  ▼
Result      the JSON body of /api/run
  │         web/app.js explain() ─► POST /api/explain {result, audience, lang}
  ▼
explainer   explainer.explain ─► Words.template, or net.ask_model checked by numbers_ok
  │         voice.voiced adds a signed /api/say link when speech is on
  ▼
screen      app.js showResult ─► viewResult; investigation.js investigationCard;
            charts.js CHARTS; map.js mapShow
```

A share link, a case step and an audit claim skip the reader and post a `Question` straight to `/api/run`. The Telegram bot runs the same chain on the server: `telegram.answer` calls `reader.read`, `analyses.run` and `explainer.explain`.

## System overview

```
                                            +--> NASA POWER                 (net.get_json)
                                            |    only *.nasa.gov and nasa-power.s3.amazonaws.com pass
Browser ---HTTPS---> Vercel function -------+--> language model             (net.ask_model)
(web/)               main.py                |    Amazon Bedrock, or EB_LLM_BASE_URL/chat/completions
   |                 earthbuddy.server:app  +--> KiriTTS, api.kiritts.com   (net.post, net.post_stream; voice.py)
   |                 (FastAPI)              +--> Telegram, api.telegram.org (net.post, net.get; telegram.py)
   |                     ^
   |                     +---- Telegram webhook, POST /api/telegram
   |
   +----HTTPS----> gibs.earthdata.nasa.gov   (map tiles, fetched by the browser itself)
```

Earth Buddy is one Python app and a folder of static files. `main.py` imports `app` from `earthbuddy/server.py`. That one FastAPI app serves the `/api/*` routes and the files in `web/`.

- **Data.** A country or a named place reads a precomputed series from `data/v/`. A coordinate point asks NASA POWER through `net.get_json`. No other data call exists.
- **Language model.** Only `explainer.explain` calls `net.ask_model`, and only when its `ai` argument is true. `/api/explain` passes the request's `ai`, and the Telegram bot passes `net.ai_available()`. The default provider is Claude on Amazon Bedrock (`anthropic.AnthropicBedrock`). `EB_LLM=selfhosted` posts to `EB_LLM_BASE_URL/chat/completions` instead. Nothing in `earthbuddy/` or `web/` names `api.anthropic.com`.
- **Speech.** `voice.py` sends a recorded clip to KiriTTS for the transcript and streams the spoken answer back. KiriTTS carries speech only and supplies no number, place or source.
- **Telegram.** `telegram.py` answers a webhook update with one `sendMessage` reply. It calls Telegram only to show "typing…" and to fetch a voice message's file.

`net.get_json` checks the host and the source id in code. `net.post`, `net.get` and `net.post_stream` have no host check. A test keeps their hosts in two files (see "Invariants").

## Shape

### Data structures

1. **`Analysis`** (`analyses/base.py`) holds `question` (the pydantic model), `fn` and `verdicts`. The card's fields come from `question.model_fields`.
2. **`Finding`** (`analyses/base.py`) is what one analysis decides: `verdict, facts, tiles, charts, method, sources, detail, notes, signals, tested, focus`. It has no headline. `signals`, `tested` and `focus` feed the investigation.
3. **`Result`** (`types.py`) is built in one place, `analyses.run`. It writes the headline from `words[<verdict key>.headline]` and `facts`, adds the second-look and synthetic-data notes, removes duplicate sources by `id`, checks that the verdict key was declared, and attaches the investigation.
4. **`Fact = StrictStr | StrictInt | StrictBool | None`.** There is no `float`. A measured number enters `facts` as a string made by `stats.fmt`, `fmt_level`, `fmt_pair` or `fmt_p`. `explainer.numbers_ok` splits fact values and model text with the same tokenizer (`words.number_tokens`), so it compares like with like.
5. **Per-kind detail models** (`ClaimDetail`, `TrendDetail`, and so on) live in the kind's own module. `run()` dumps them into `Result.detail: dict`.
6. **`Investigation`** (`types.py`, built by `analyses/investigate.py`) is the labelled reading of one result: `scope, why, impact, validation, limits, datasets, next, guidance`. It is built from the question's field names, the finding and `data/context.json`. It has no `if kind ==` branch. Its follow-up table (`_next`) writes new questions of seven kinds by name. See `docs/19-investigation.md`.
7. **`words.EN` and `words.KM`** form one flat table of every sentence the server writes. A Khmer key that is missing falls back to English (`Words._text`).
8. **`Source`** is one entry of `data/sources.json`: `id, name, short_name, version, agency, center, doi, url, citation, via, accessed, cached`. `Series.sources` holds at least one. Only `cached` changes at run time.
9. **`reader.FILL`** (Python) and **`EDITORS`** (`web/app.js`) are both keyed by field name. Thirteen field names cover all eight kinds.

### The registry

`earthbuddy/analyses/__init__.py` holds the one list of kinds. All eight kinds in `types.Kind` have an entry.

```python
ANALYSES: dict[str, Analysis] = {
    "claim": Analysis(ClaimQ, claim.claim, claim.VERDICTS),
    "trend": Analysis(TrendQ, trend.trend, trend.VERDICTS),
    "scan": Analysis(ScanQ, scan.scan, scan.VERDICTS),
    "where": Analysis(WhereQ, where.where, where.VERDICTS),
    "rank": Analysis(RankQ, rank.rank, rank.VERDICTS),
    "baseline": Analysis(BaselineQ, baseline.baseline, baseline.VERDICTS),
    "extremes": Analysis(ExtremesQ, extremes.extremes, extremes.VERDICTS),
    "relate": Analysis(RelateQ, relate.relate, relate.VERDICTS),
}
```

An analysis has the signature `fn(q, w: Words) -> Finding`. It asks `series` for data, calls `stats`, and states facts. It never writes a headline and never sees `quote`, `via`, `revision`, `ai` or an HTTP client. A route stays a few lines long:

```python
@app.post("/api/run")
def api_run(body: dict = Body(...)) -> Result:
    question, revision = reader.question_from(body)
    lang = body.get("lang", "en")
    if lang not in get_args(Lang):
        raise QuestionError("lang")
    return analyses.run(question, revision=revision, lang=lang)
```

A new kind adds one module, one entry here and one doc. If it reuses existing field names, it needs no reader code and no card code.

### Load-bearing decisions

1. **A kind is a record, and a field name is the unit of reuse.** A bare `dict[Kind, fn]` has no room for a kind's verdict keys and card fields. Without a home they become hand-synced lists in the reader, the explainer and the page.
2. **One sentence table and one `Result` constructor.** Wording is a pure function of the verdict key and `facts`. "The headline never comes from the model" is then true by construction. The cost is that every headline variant is its own verdict key (`rank.clear_leader`, `rank.tied`, `rank.none`).
3. **Synchronous code with one network door.** Routes are plain `def`, so FastAPI runs them on its thread pool. `net.get_json` owns the httpx client, the retries, a 3-slot `BoundedSemaphore` and the cache read and write. Fan-out is one function, `series.get_many`, on a pool of 8 threads. Claim, rank, relate and scan use it. This avoids `await` on every signature and keeps tests plain pytest.
4. **Offline mode and tests swap the transport, nothing else.** `net._transport` is the one offline branch. Every layer above it (the 422 retry, fill values, the cache, monthly-to-annual) runs the same code in live mode, offline mode and tests.
5. **One guard for every outside dict.** `reader.guard(raw, quote, via)` never raises and drops what it does not know. Each `FILL[name]` accepts both the reader's flat shape (`region_id`, `window_from`) and the `Question` shape. `FILL["point"]` turns a country or place into its centre point. That depends on the field name, not on the kind.
6. **The server writes all prose.** `/api/run` takes `lang`, so headlines, tiles, method steps and templates come from `words.py`. The explainer needs prose on the server anyway. A second template engine in the browser would have to match placeholders across the wire.
7. **Analyses never see `revision`.** `run()` adds the second-look note for any kind.
8. **Errors are raised, never returned.** `QuestionError(field)` is a 400. `TooShort` is a `QuestionError("window")`. `DataSourceError` is a 502. `VoiceFailed` is a 503. `AIFailed` never reaches a route, because `explainer.explain` falls back to the template.
9. **`detail` stays a `dict` on the wire.** Each kind dumps its own pydantic model. This avoids a second discriminated union. Tests for claim, trend, baseline, extremes and relate parse the dict back through the model.
10. **Data is adapted at build time.** `tools/build_catalog.py` writes `data/` once and the output is committed. `catalog.py` parses strictly (`extra="forbid"`) and holds no compatibility code.
11. **`statsmodels` is imported inside `stats.stl()`.** A deploy without it loses only the seasonal decomposition.
12. **Speech and chat are transports, not data.** `voice.py` and `telegram.py` call out only through `net`. Only `server.py` and `telegram.py` import `voice`.

### Invariants and where they live

| Invariant | Enforced by |
|---|---|
| `quote` and `via` never change a number | `Question` models have no such fields and forbid extra keys. `fn(q, w)` cannot see them |
| A float is never a fact | `types.Fact` has no `float` |
| The headline comes from the verdict key and `facts` | `Finding` has no headline, and only `analyses.run` builds a `Result` |
| An analysis returns only declared verdict keys | `run()` raises `RuntimeError` otherwise. `tests/test_words.py` checks a headline and three audiences for each declared key |
| A bad question is a 400 with `kind: "request"` and a `field` | `QuestionError(field)` and the `RequestValidationError` handler in `server.py`. For a malformed body, `field` can be `""` |
| No test reaches the network or a model unless it asks to | the autouse `sealed` fixture in `tests/conftest.py` installs a transport and a model stub that both raise |
| Synthetic data never enters the real cache | `cache._path()` returns `:memory:` when `EB_OFFLINE=1` |
| The thresholds `0.05`, `0.10` and `1.96` appear only in `stats.py` | `test_thresholds_live_only_in_stats` in `tests/test_layers.py` |
| Every source is registered, from an agency in `catalog.ALLOWED_AGENCIES`, and cited by a DOI or the provider's acknowledgement text | `tests/test_sources.py`. `tools/check_refs.py` resolves every DOI |
| A data fetch names a registered source | `net.get_json` raises `ValueError` on an unknown `source` id |
| `net.get_json` fetches only from `*.nasa.gov` and `nasa-power.s3.amazonaws.com` | `net.is_data_host`. `net.get_json` raises `ValueError` on any other host |
| No file in `earthbuddy/` or `web/` names a host outside the data hosts and `doi.org`. `voice.py` may also name `api.kiritts.com`, and `telegram.py` may name `api.telegram.org` | `test_no_url_outside_allowed_hosts` scans for `http`, `ws` and scheme-relative URLs, ignoring case. It skips vendored MapLibre and the two font licences |
| A transport host is named only in its owner file | `test_a_transport_host_is_never_data_and_named_only_in_its_owner` searches `earthbuddy/`, `web/` and `tools/` |
| No code, data or page names Natural Earth, Nominatim, Open-Meteo or OpenStreetMap | `test_no_removed_provider_in_code_data_or_web` searches `earthbuddy/`, `web/`, `data/` and `tools/` |
| Only `server.py` and `telegram.py` import `voice`, and `voice.py` does not name `httpx` | `test_only_server_and_telegram_import_voice`, `test_voice_does_not_touch_httpx` |
| A spoken-answer link cannot be forged or edited | `voice.say` checks an HMAC of the text before any network call (`QuestionError("sig")`) |
| Layers stay layered | `tests/test_layers.py` walks each module's `ast` imports against the "Never imports" column below |

### What it does not do

- No async code and no injected `Context`.
- No session state on the server. `/api/explain` takes the `Result` back.
- No load-time adaptation of data files.
- No plugin loading. The registry is a literal dict.
- No validation in JS beyond "a required field is empty".

## Module map

`tests/test_layers.py` enforces the last column for every row it lists. It does not list `telegram.py`, so nothing checks that module's imports except the `voice` rule.

| File | Owns | Public surface | Never imports |
|---|---|---|---|
| `types.py` | every wire type and every error | regions, the 8 `*Q` models, `Question`, `Kind`, `Draft`, `ReadResult`, `Case`, `Series`, `Source`, `Fit`, `Verdict`, the `Chart` union, `Tile`, `Step`, `Fact`, `Investigation`, `Result`, `Explanation`, `Clip`, `Heard`, `QuestionError`, `TooShort`, `DataSourceError`, `AIFailed`, `VoiceFailed` | any `earthbuddy` module |
| `stats.py` | `T`, the formatters, every p-value, slope and verdict level. No I/O | `T`, `fmt`, `fmt_level`, `fmt_pair`, `fmt_p`, `trend_test`, `pettitt`, `is_step`, `bh`, `field_test`, `test_claim`, `claim_p`, `claim_verdict`, `stl`, `seasonal_cycle`, `relation`, and the helpers each kind calls | anything except `types` |
| `words.py` | every server sentence (`en` and `km`), digit handling | `Words`, `EN`, `KM`, `ascii_digits`, `mostly_khmer`, `number_tokens`, `HAS_DIGIT` | anything except `types` |
| `cache.py` | the SQLite table | `get`, `put`, `stats`, `reset` | any `earthbuddy` module |
| `fixtures.py` | synthetic POWER-shaped responses | `handler(request)` | any `earthbuddy` module |
| `net.py` | the only network door, the offline swap, the model providers, test stubs | `get_json`, `post`, `get`, `post_stream`, `ask_model`, `ai_available`, `model_id`, `model_writes`, `is_data_host`, `OFFLINE`, `PROVIDERS`, `stub`, `refuse_offline_on_vercel` | `catalog`, `power`, `series`, `analyses`, `reader`, `explainer`, `server` |
| `catalog.py` | `data/catalog.json`, `data/v/*.json`, `sources.json`, `context.json`, `summary.json`, `audit.json`, `cases.json`; names, aliases and centres | `load`, `sources`, `ALLOWED_AGENCIES`, `variable`, `variables`, `name`, `centre`, `cells`, `find_region`, `find_regions`, `group`, `years`, `regional_values`, `context`, `summary`, `audit`, `cases`, `raw` | `net`, `power`, `series`, `stats`, `analyses`, `reader` |
| `power.py` | POWER URLs and payload parsing, the 422 retry | `point`, `grid`, `last_complete_year`, `Monthly` | `catalog`, `series`, `stats`, `analyses` |
| `geocode.py` | free text to `Point`, with no network: coordinates, then the catalog, then `data/gazetteer.json` | `search` | `net`, `power`, `series`, `stats`, `analyses`, `reader` |
| `series.py` | the only way an analysis gets data | `get_series`, `get_many`, `get_grid`, `annualise` | `analyses`, `reader`, `net` (it goes through `power`) |
| `analyses/base.py` | `Analysis`, `Finding`, shared chart and fact helpers | `Analysis`, `Finding`, `fit_or_none`, `signal`, `per_decade`, `line_chart`, `monthly_totals` | `reader`, `explainer`, `server`, `power` |
| `analyses/<kind>.py` | one kind: its detail model, `VERDICTS`, its function | `<kind>`, `VERDICTS`, `<Kind>Detail` | `reader`, `explainer`, `server`, `power`. Today each imports only `catalog`, `series`, `stats`, `types`, `words` and `base` |
| `analyses/investigate.py` | the investigation block of a `Result` | `investigate` | `reader`, `explainer`, `server`, `power` |
| `analyses/__init__.py` | the registry, and the only `Result` constructor. It reads `net.OFFLINE` for the synthetic-data note | `ANALYSES`, `run`, `kinds_meta` | `reader`, `explainer`, `server`, `power` |
| `reader.py` | sentence or raw dict to `Draft` and `Question` | `read`, `reread`, `question_from`, `guard`, `read_keywords`, `FILL`, `CUES` | `series`, `power`, `explainer`, `server` |
| `explainer.py` | the explanation, what each audience reads, and the reply checks | `explain`, `numbers_ok`, `BRIEFS`, `BOLD_MAX` | `series`, `power`, `reader`, `server` |
| `voice.py` | KiriTTS speech in and out, the signed audio link | `status`, `hear`, `voiced`, `say`, `spoken` | everything except `types`, `net`, `catalog` |
| `telegram.py` | a Telegram update to one reply | `answer` | not checked |
| `__init__.py` | `ROOT`, `SOURCES`, and the `.env` loader that runs on import | `ROOT`, `SOURCES` | none |
| `server.py` | routes, error mapping, static files | `app` | none |

The longest call chain is route → `analyses.run` → the kind's `fn` → `series` → `power` → `net`.

## Keeping lists in sync

| List | Home | Other copies | How they stay equal |
|---|---|---|---|
| kinds | `ANALYSES` | `Kind` literal, `Question` union | `tests/test_registry.py`: `ANALYSES` keys ⊆ `Kind` == union members |
| card fields per kind | `Question` models | none. `GET /api/catalog` serves them as `kinds` | derived by `analyses.kinds_meta()`. There is no JS `FIELDS` table |
| field names | `Question` models | `reader.FILL`, JS `EDITORS`, i18n `field.*` | `test_registry` and `tests/test_web_sync.py` |
| kind panels | JS `PANELS` (optional) | `ANALYSES` | `test_web_sync`: keys ⊆ kinds |
| chart types | `Chart` union | JS `CHARTS` | `test_web_sync`: the sets are equal |
| verdict keys | `Analysis.verdicts` | `words.EN` | `tests/test_words.py`. `run()` also checks membership |
| reader cues | `reader.CUES` | none | single source |
| thresholds | `stats.T` | none | the grep test in `test_layers.py` |
| server strings | `words.EN` | `words.KM` | `tests/test_i18n.py`: KM keys ⊆ EN keys, with the same placeholders |
| UI strings | `i18n.js EN` | `KM`, the `t("...")` calls | `test_i18n`: `KM` and `EN` have the same keys and placeholders. `test_web_sync`: every `t()` key exists and no `EN` key is unused |

`test_web_sync.py` reads JS tables with a regex over `const NAME = {` … `};`, one key per line. No Node and no build step are needed. Each JS table carries a comment stating this layout.

## Backend runtime

### Entry points

| File | Used by | What it does |
|---|---|---|
| `main.py` | Vercel | One line, `from earthbuddy.server import app`. |
| `run.py` | You, locally | Calls `net.refuse_offline_on_vercel()`, then starts `uvicorn` on `earthbuddy.server:app` with `reload=True`. `EB_HOST` (default `127.0.0.1`) and `EB_PORT` (default `8000`) set the address. |

Importing the `earthbuddy` package loads `.env`. Importing `earthbuddy/server.py` calls `net.refuse_offline_on_vercel()` and builds the `app`. The server keeps no session state. The only state is the SQLite cache and the parsed `data/` files, which `catalog.py` caches in memory with `functools.cache`.

### Routes

`earthbuddy/server.py` registers these routes, in this order. Every route is a plain `def`. FastAPI also serves its default `/docs`, `/redoc` and `/openapi.json`.

| Method and path | Body or query | Returns | Errors |
|---|---|---|---|
| `GET /api/status` | none | `{ai_available, model, offline, last_complete_year, cache: {entries, bytes}, voice: {available, clip_s, mimes}}` | none |
| `GET /api/catalog` | none | the contents of `data/catalog.json`, plus `kinds`, the fields of each kind | none |
| `GET /api/sources` | none | the list in `data/sources.json` | none |
| `POST /api/read` | `{text?, draft?, lang: "en" \| "km" = "en"}` | `{draft, question \| null, missing}`. With `draft`, it re-reads the card. Otherwise it reads `text` with the keyword reader. It never calls a model. | 400 for empty text or text over 600 characters (`field: "text"`), a bad `lang`, or a malformed body |
| `POST /api/run` | `{question, revision?, lang? = "en", via?}`. `via` counts only when it is `form`, `link` or `audit`. Any other value becomes `link`. A missing `revision` is 0. | `Result` | 400 for a bad question (`field` names the first bad or missing field), a bad `lang`, or a body that is not an object. 502 when NASA POWER fails. |
| `POST /api/explain` | `{result, audience: "student" \| "policymaker" \| "researcher" = "student", lang = "en", ai = false}` | `{short, more, via: "ai" \| "template", audio}`. `audio` is a signed `/api/say` link, or `null` when speech is off. | 400 for a malformed body. A model failure is not an error. The route returns the template text. |
| `POST /api/hear` | `{audio: base64, mime, lang}`. `mime` is one of `audio/webm`, `audio/mp4`, `audio/ogg`, `audio/wav`. | `{text}`, the transcript. `""` when nothing was heard. | 400 for a malformed clip (`field` names the bad part) or one over 3,000,000 bytes (`field: "audio"`). 503 when KiriTTS is off, out of credit or down. |
| `GET /api/say` | `t` (1 to 4096 characters), `lang`, `sig` | the spoken text as a WAV stream, cached for a year | 400 for a wrong `sig` (`field: "sig"`). 503 as above. |
| `POST /api/telegram` | a Telegram `Update`, header `X-Telegram-Bot-Api-Secret-Token` | a `sendMessage` reply, or `{}` for an update with no text or voice message | 404 when `TELEGRAM_WEBHOOK_SECRET` is unset. 403 for a wrong secret. |
| `GET /api/geocode` | `q`, 1 to 600 characters | `{results: [Point]}`, at most 5 | 400 for a missing or oversized `q` |
| `GET /api/audit` | `lang = "en"` | the frozen audit, with a live `question`, `verdict` and `verdict_word` added to each claim. Each claim runs from `data/v/`, with no network call. | 400 for a bad `lang` |
| `GET /api/cases` | none | `{cases}` from `data/cases.json`. Each step's `question` is read the way a share link is, and nothing runs. | none |
| `GET /data/countries.geojson` | none | `data/countries.geojson`, as `application/geo+json` | none |
| `GET /data/summary.json` | none | `data/summary.json` with a boolean `clear` added to every row (`row["q"] < T.fdr_q`) | none |
| `GET /` and `GET /index.html` | none | `web/index.html` with `Cache-Control: no-store` | none |
| `GET /<path>` | none | the file at `web/<path>`, served by `StaticFiles` | 404 |

A wrong method does not return the same status everywhere. `GET /api/read` returns 404, because the static mount at `/` matches the path. `POST /api/status` returns 405.

### Static files

`app.mount("/", StaticFiles(directory=WEB))` is registered last, so every route above wins. `index.html` has its own route so the page is never cached. Other static files carry no `Cache-Control` header.

The server never mounts `data/`. Two explicit routes expose the two files the map needs. A request for `/data/catalog.json` or `/data/cache.sqlite` returns 404, and so do `/main.py`, `/SPEC.md` and `/earthbuddy/server.py`.

### Error mapping

Four handlers in `server.py` map every error. Anything else is a bug and surfaces as a 500.

| Status | Raised as | Body |
|---|---|---|
| 400 | `QuestionError(field)`, which includes `TooShort` | `{error, kind: "request", field}` |
| 400 | FastAPI `RequestValidationError` | `{error: "bad request", kind: "request", field}`. `field` is the first part of the error location that is not `body` or `query`, or `""`. |
| 502 | `DataSourceError(message, status, url)` | `{error, kind: "data_source", url}` |
| 503 | `VoiceFailed(reason)` | `{error, kind: "voice", reason: "off" \| "limit" \| "down"}` |

`/api/telegram` builds its own 404 and 403 bodies. `telegram.answer` catches every error from a question and replies with a plain message, because a 500 makes Telegram send the same update again.

### The `.env` loader

`earthbuddy/__init__.py` reads `<repo>/.env` when the package is first imported. It reads one `KEY=value` per line, skips lines that start with `#`, and strips whitespace and quotes from the value. It does not handle `export`, inline comments or multi-line values. It calls `os.environ.setdefault`, so the order of precedence is the real environment, then `.env`, then the default in the code. `.env` is in `.gitignore` and `.vercelignore`.

### The cache

`earthbuddy/cache.py` holds NASA POWER responses in one SQLite table, `cache(key, payload, source, fetched_at)`. Only `net.get_json` writes to it, and only `power.py` calls `net.get_json`. The key is the full request URL. The payload is zlib-compressed JSON. `power.TTL_DAYS` is 30. One connection and one lock serve all threads.

`cache._path()` picks the file in this order.

1. `:memory:` when `EB_OFFLINE=1`.
2. `EB_DB`, when set.
3. `/tmp/eb/cache.sqlite`, when `VERCEL` is set. The deployed bundle is read-only.
4. `data/cache.sqlite` under the repository root.

The code creates the parent directory and the table on first use. It has no fallback when the file cannot be opened or written. That error would surface as a 500.

### Offline mode

`EB_OFFLINE=1` swaps the HTTP transport in `net.py` for `httpx.MockTransport(fixtures.handler)`. Every layer above the transport still runs. Five things change.

- POWER calls return synthetic POWER-shaped data from `earthbuddy/fixtures.py`. Country and place series still come from the real files in `data/v/`.
- The cache is in memory, so synthetic data never lands under a real NASA URL.
- `net.ai_available()` returns false.
- `voice._key()` returns `""`, so speech is off.
- `GET /api/status` reports `offline: true`, and `analyses.run` adds the `note.synthetic` note to `Result.notes`.

`net.refuse_offline_on_vercel()` exits the process when both `EB_OFFLINE=1` and `VERCEL` are set. It runs when `server.py` is imported and when `run.py` starts.

### Voice

`voice.py` is on when `KIRITTS_API_KEY` is set and `EB_OFFLINE` is not `1`. `docs/17-voice.md` is its spec.

- **Hear.** `voice.hear(clip)` posts the clip to `audio/transcriptions` (model `kiristt`). The prompt lists the catalog's place names, so the transcript spells them the way the reader finds them. The page then sends the transcript to `/api/read` like typed text.
- **Say.** `voice.voiced` runs inside `/api/explain`. It builds the spoken text from the short answer and the tiles (`voice.spoken`) and returns the link `/api/say?t=…&lang=…&sig=…`. `sig` is an HMAC-SHA256 of the language, the voice and the text, keyed by the API key. `voice.say` refuses a link whose `sig` does not match, so `/api/say` cannot be used to speak other text. It then streams WAV from `audio/speech` (model `kiritts`) and averages it down to 16 kHz (`_downsampled`).
- **Failures.** A KiriTTS 401 or 403 gives the reason `off`, a 429 gives `limit`, and anything else gives `down`. The text answer does not depend on speech.

### Telegram

`telegram.py` is on when `TELEGRAM_WEBHOOK_SECRET` is set. `docs/18-telegram.md` is its spec. `telegram.answer(update, base_url)` returns the reply as the webhook's response body, so a text question needs no call to Telegram.

- `/start`, `/help` and the two language buttons return a menu without running anything.
- A text message runs `reader.read`, `analyses.run` and `explainer.explain` for the `student` audience. The language is Khmer when the text holds a Khmer letter. The explainer uses the model when `net.ai_available()` is true.
- The reply holds the headline, the short text, the tiles, the source names, and a button that opens the same question on the web page through a `#q=` share link.
- A voice message needs `TELEGRAM_BOT_TOKEN` and KiriTTS. `_download` fetches the file, `voice.hear` transcribes it, and the transcript is answered like typed text.
- With `TELEGRAM_BOT_TOKEN` set, a background thread posts `sendChatAction` every 4 seconds while the answer is computed.
- Telegram URLs hold the bot token, so the module logs only the status or the error type.

### Timeouts and concurrency

| Limit | Value | Where |
|---|---|---|
| Function duration on Vercel | 300 s | `vercel.json`, `maxDuration` |
| NASA request timeout | 120 s, with a 20 s connect timeout | `net._http()` |
| NASA request attempts | 4. Retries follow a transport error, a 429 or a 5xx. Another 4xx fails at once. | `net.ATTEMPTS`, `net.get_json` |
| Wait before attempts 2, 3 and 4 | 1.5 s, 3 s, 6 s | `net.BACKOFF_S` |
| NASA requests in flight, per process | 3. A cache hit does not use a slot. | `net.MAX_INFLIGHT` |
| Fan-out threads for `series.get_many` | 8 | `series.py` |
| Bedrock call timeout | 10 s, one attempt (`max_retries=0`) | `net.MODEL_TIMEOUT_S`, `net._anthropic()` |
| Self-hosted model call timeout | `EB_LLM_TIMEOUT_S`, default 10 s | `net._selfhosted_ask` |
| `net.post`, `net.get`, `net.post_stream` | 30 s by default, 2 attempts. The retry follows a transport error or a 5xx, so a call can take twice its timeout. | `net._send` |
| Telegram "typing…" call | 2 s | `telegram._typing` |

These limits allow one request to outlast the function. Four NASA attempts that each wait out the 120 s timeout take 480 s, which is more than 300 s.

## Client

### Files and loading

The client is plain files that the browser runs as written. The repository has no `package.json`, bundler config or `node_modules`.

`index.html` loads seven classic scripts with `defer`, in this order. They share one global scope. They are not ES modules.

| File | Owns |
|---|---|
| `web/i18n.js` | `esc`, the string tables `EN` and `KM`, and `t()`. |
| `web/charts.js` | The SVG helpers and the `CHARTS` table. Each renderer returns an SVG string and the same numbers as table rows. |
| `web/vendor/maplibre-gl/maplibre-gl.js` | `maplibregl`. |
| `web/map.js` | The MapLibre map `M`, its layers, the legend and the click handler. |
| `web/voice.js` | `Voice`: one `MediaRecorder` and one `Audio` element. |
| `web/investigation.js` | `MODES`, `SECTIONS`, the investigation components, the depth switch and the evidence downloads (`docs/19-investigation.md`). |
| `web/app.js` | State `S`, the render loop, every view, `EDITORS`, `PANELS`, the `ACTIONS` table, the API calls, the share link and `boot()`. |

`web/index.html` is the shell: the sidebar, top bar, thread, composer, the `#picker` dialog and the parked map. `web/styles.css` holds all styles. It sets `color-scheme: light`, has breakpoints at 900 px and 560 px, and puts Noto Sans Khmer first in the font stack under `html:lang(km)`.

**Vendored libraries.** `web/vendor/maplibre-gl/` holds MapLibre GL JS 5.24.0 (BSD 3-clause) with its CSS and `LICENSE.txt`. `web/vendor/fonts/` holds Inter and Noto Sans Khmer as woff2 files, `fonts.css` and two OFL licence files.

Views pass server and URL text through `esc()`. `t()` escapes its variables unless the caller passes another `wrap`.

### State and the render loop

`S` holds all app state: `lang`, `mode`, `region` and `clickedCountry` (the area picked in the top bar), `thread` (one entry per question), `editing` (the id of the one entry whose card is open), `mapFor` (the id of the entry that holds the map), `linkFailed`, `pick` (the region dialog), `mic`, and the loaded `catalog`, `status`, `sources`, `audit` and `cases`. An entry holds one question's life, from its `text` and `read` to its `question`, `revision`, `result` and `explanation`, plus its own `audience`, depth `level`, open tab and fallback results.

`render()` rebuilds the whole thread.

1. It remembers the id of the focused element and parks the map in `#map-park`.
2. It sets `#thread.innerHTML` from `viewThread()`, or from a loading line until the catalog arrives.
3. It rebuilds the `#picker` dialog when the dialog is open.
4. `placeMap()` moves the one map element into the first `[data-map-slot]`, in the dialog if it is open, else in the thread.
5. It redraws the mic button, shows the mapped result on the map when that result changed, and puts focus back.

The sidebar, top bar and composer are drawn by `renderSide()`, `renderTop()` and `renderComposer()`, not by `render()`.

`call(h, busy, path, body)` makes the read, run, hear and geocode calls. `h` is an entry, `S.pick` or `S.mic`. The call takes the next number from `h.seq` and applies its answer only if that number is still the latest and `h` is still live. A stale answer is dropped. A failed call stores the server's error body, or `{kind: "network"}` when the body has no `kind`. `explain` and the fallback runs use their own `fetch`.

Events use delegation on `document.body`. A click on any `[data-act]` element runs `ACTIONS[act](el, entry)`. The `change`, `input`, `toggle` and `keydown` handlers cover the card fields, the region search, the Escape key, Enter in the composer and the arrow keys on chart tabs.

### Views

There is no router and no separate page.

| View | Function | Shows |
|---|---|---|
| Start | `viewStart` | Six example chips and a "by hand" chip. Shown while the thread is empty. |
| Entry | `viewEntry` | One per thread entry: the question bubble, then the card, the result, a status line, or an "unfinished" prompt. |
| Card | `viewCard` | The kind select, one editor per field of the kind, the leads and unmapped notes, **Run** and **Back**. Shown when `S.editing` is this entry. |
| Result | `viewResult`, `viewActions` | The verdict badge, the headline, an "asked" line after an edit, the explanation with a speaker button when it has audio, **Edit** and **Share**. The newest result opens its investigation. An older one keeps it behind a button. |
| Investigation | `investigationCard` | The depth switch and sections 2 to 9 of `docs/19-investigation.md`, in the order of `SECTIONS`. A section that throws shows a short note and the rest still render. |
| Region picker | `viewPicker` | A place search and the map, in the `#picker` dialog. |
| Sidebar | `renderSide` | **New analysis**, the topics list, **Data sources**, the case files and the audit list. Below 900 px it is a drawer behind **Menu**. |
| Top bar | `renderTop` | **Menu**, the mode switch, the language button and the region button. |
| Composer | `renderComposer` | A textarea limited to 600 characters, the mic button when speech is available, and send. Enter sends. Shift+Enter starts a new line. |

**Modes and depth.** The top bar has two modes (`MODES` in `investigation.js`). `public` sets the explainer audience to `student` and opens a result at depth 0. `science` sets the audience to `researcher` and depth 2. The three depths are `discover`, `explore` and `investigate`. Each entry can change its own depth.

**Language.** The language button switches between `en` and `km`. `setLang` redraws the page, loads the audit again, and runs every shown result again with the new `lang` (`relang`), because the server writes the prose.

The flow of one question is this. `ask(text)` posts to `/api/read`. `proceed(e)` then decides. If the reading lacks a `region` or `point` and a region is picked, it fills the field and reads again. If the question is complete, it runs. A kind that needs a point but names a variable with no `point_param` in the catalog is blocked, so the card opens with a reason. Any other incomplete reading opens the card. At boot the picked region is Phnom Penh (`HOME` in `app.js`) unless a saved one loads.

### Tables

These tables hold what varies by kind or field. The first three are one `const NAME = {` block with one key per line, because `tests/test_web_sync.py` reads them with a regex.

| Table | File | Keys | Purpose |
|---|---|---|---|
| `EDITORS` | `app.js` | the 13 field names `region`, `point`, `tests`, `variable`, `x`, `y`, `window`, `baseline`, `among`, `metric`, `order`, `top_n`, `year` | Each value has `view`, `change` and `text`. The card draws `S.catalog.kinds[kind].fields` through it. |
| `PANELS` | `app.js` | the eight kinds | The kind's panel of numbers. Optional. A kind with no panel renders without one. |
| `CHARTS` | `charts.js` | `line`, `bars`, `scatter`, `cells`, `intervals` | One renderer per `Chart` type. |
| `PICTURES`, `INSIGHTS`, `FALLBACKS` | `app.js` | `trend`; `trend`; `monthly`, `where` | Optional extras. `PICTURES` names a kind's chart tabs. `INSIGHTS` adds the size and certainty cards. `FALLBACKS` builds a second question when a tab or the map needs data the result lacks. |
| `SECTIONS`, `MODES` | `investigation.js` | eight section ids; `public`, `science` | The investigation order and the two modes. |
| `EN` and `KM` | `i18n.js` | 337 UI strings each | Two JSON objects between `/*json*/` and `/*end*/`. |

`t(key, vars, wrap = esc)` looks the key up in `KM` when `S.lang` is `"km"`, then in `EN`, then falls back to the key. It replaces each `{name}` with `wrap(vars[name])`.

No view or route branches on a kind name. The client writes a kind name only where it builds a new question: `askAbout` (a `trend`), `FALLBACKS` (a `trend` and a `where`) and the `try` action (a `claim`).

### How the client calls the API

| When | Request |
|---|---|
| Boot | `GET /api/catalog`, `GET /api/status` and `GET /api/sources` in parallel. If any fails, the page shows a network error. Then `GET /api/cases` and `GET /api/audit?lang=` without blocking. |
| Ask | `POST /api/read {text, lang}`. |
| Speak a question | `POST /api/hear {audio, mime, lang}`, then the transcript goes through Ask. The answer to a spoken question plays its audio by itself. |
| Card edit, region fill, topic click | `POST /api/read {draft: {fields, quote, leads, unmapped, revision}, lang}`. |
| Run | `POST /api/run {question, revision, lang}`. An audit claim adds `via: "audit"`. A case step and a follow-up send `via: "link"`. |
| Explain | `POST /api/explain {result, audience, lang}`, with the entry's audience. The page never sends `ai`. |
| Extra chart or map | `POST /api/run` with a `FALLBACKS` question: a trend at the region's centre point for the seasonal and residual tabs, or a `where` question for the map. |
| Place search | The client matches a catalog name first. If none matches, it calls `GET /api/geocode?q=`. |
| Map | `GET /data/countries.geojson`, `GET /data/summary.json` and `GET /api/sources`. |

An error body with `kind: "request"` shows the field name through the `field.<name>` string. `kind: "data_source"` shows the NASA error. Any other failure shows the network error.

**No AI on the page.** The page has no AI switch. It reads every sentence with the keyword reader and shows template text, so a sentence never leaves the server. `/api/explain` still accepts `ai: true` for other clients, and the Telegram bot uses it.

### The share link

A link is `<origin><path>#q=<code>`. `<code>` is the base64url encoding, without padding, of the UTF-8 JSON `{"question": <the result's question>, "revision": <the revision it ran at>}`. The link carries the question and not the result, so opening it runs the question again on current data. It carries no language.

`showResult` writes the hash with `history.replaceState` after each result. **Share** copies the link with `navigator.clipboard`. When copying fails, it shows the link in a read-only box.

`route()` runs at boot and on `hashchange`. For a `#q=` hash that no shown entry matches, it decodes the code, clears the thread, and posts `{question, revision, lang}` to `/api/run`. The server reads it with `via: "link"`. A code that does not decode, or a question the server rejects, shows the "link" error and clears the hash.

At depth `investigate`, the investigation offers two downloads made in the browser (`downloadEvidence`): the question and the whole `Result` as JSON, and the chart's values as CSV.

### Browser storage

The client stores two `localStorage` values: `eb-lang` and `eb-region` (the chosen region and the clicked country as JSON). Reads and writes sit in `try` blocks, so a browser that blocks storage still works. The client uses no cookies, `sessionStorage` or IndexedDB.

### The map

`map.js` draws one MapLibre map with these layers, bottom to top.

| Layer | Source | Draws |
|---|---|---|
| `gibs` | NASA GIBS raster tiles | the background |
| `countries` | `/data/countries.geojson` | country fills. A country is coloured only when its `clear` flag in `/data/summary.json` is true for the chosen variable. The colour is warm or cool by the sign of `trend_per_decade` and the variable's `warm_up`, and stronger as the trend grows. Every other country is grey. |
| `borders` | the same GeoJSON | white outlines |
| `cells` and `outline` | the `result` source | the grid cells of a `where` result, or the outline of the question's region |
| `point` | the `result` source | a circle for a coordinate point |

The tile source is the one `docs/16-data-sources.md` allows, NASA GIBS (`GIBS` in `map.js`), with `tileSize` 256 and `maxzoom` 8. The attribution is the `citation` of the `gibs-bluemarble` source from `/api/sources`.

A click turns the position into a point with two decimals. If the click lands on a catalog country, `mapPicked` also gets that country. It then does one of three things. In the region dialog it sets the region. With a card open that has a `point` or `region` field, it fills that field. Otherwise it asks how the map's variable is changing there. A select in the legend changes the variable.

If MapLibre does not load, or the data fetches fail, `loadMap()` returns false and `mapShow` does nothing, so the rest of the page still works.

## Data and tools

### Files in `data/`

| File | Holds | Read by |
|---|---|---|
| `catalog.json` | years 2001 to 2024, 44 variables, 43 places, 248 countries, 4 groups, 6 topics | `catalog.load`, `GET /api/catalog` |
| `v/<variable>.json` | one file per variable (44): an annual series per country and place, and the cell count of each | `catalog.regional_values` |
| `sources.json` | the reference registry, 32 entries, agencies `NASA` and `NASA/JAXA` | `catalog.sources`, `net.get_json`, `GET /api/sources` |
| `summary.json` | per variable and country: `trend_per_decade`, `p`, `q`, `direction` | `GET /data/summary.json`, for the map |
| `countries.geojson` | country shapes built from the NASA SEDAC national identifier grid | `GET /data/countries.geojson` |
| `gazetteer.json` | 49,273 place entries from NASA SEDAC | `geocode.search` |
| `context.json` | background text per topic and variable: why it matters, drivers, guidance, related variables | `catalog.context`, for the investigation |
| `audit.json` | 8 claims frozen on 2026-11-10 | `GET /api/audit` |
| `cases.json` | prepared question sequences. Today one case, `fire-watch-cambodia`, with 4 steps | `GET /api/cases` |
| `giovanni/` | 8 NASA Giovanni area-average CSV files and `index.json` | `tests/test_giovanni.py` only, which compares the Cambodia series with them |
| `cache.sqlite` | the local POWER cache. Git-ignored and not deployed | `cache.py` |

All 44 variables have a regional series. 30 have a `point_param`, so they also work at a coordinate point through NASA POWER. The other 14 have no live point source. For them `series._param` raises `QuestionError("variable", "no-point-data")`, and the card blocks a kind that needs a point.

### Tools

The app never imports `tools/`. Its output is committed, so you run these only to rebuild the data.

| Command | What it does | Needs |
|---|---|---|
| `python tools/check_refs.py` | Resolves every DOI in `data/sources.json` through doi.org. It exits 1 if one fails. `--markdown` prints the README reference list instead. | network |
| `python tools/build_catalog.py --adapt [SNAPSHOT]` | Rebuilds `data/` from the claim-desk snapshot (default `~/earth-buddy-claimdesk-snapshot`), the NASA POWER Zarr stores and the NASA SEDAC files in `tools/cache/`. Then it runs `--extend`. | `tools/requirements-build.txt`, network, an Earthdata login for SEDAC |
| `python tools/build_catalog.py --extend` | Adds each `tools/catalog.src.json` variable the catalog lacks, with its `data/v/` file, then rebuilds `summary.json`. | `tools/requirements-build.txt`, the SEDAC files, the grids in `tools/cache/grids/` |
| `python tools/grids/<family>.py` | Downloads one family of NASA files and writes yearly 1° grids to `tools/cache/grids/`. The families are `fire`, `gldas`, `grace`, `merra2`, `ndvi`, `omi` and `sst`. They supply 12 of the 44 variables. `--check` tests the grids. | network |
| `python tools/grids/merge.py <family> ...` | Merges `tools/grids/<family>.json` into `tools/catalog.src.json`, `data/sources.json` and `docs/16-data-sources.md`. | the family's grids |
| `python tools/build_catalog.py --summary` | Rebuilds `data/summary.json` from `data/v/`. | nothing else |
| `python tools/build_catalog.py --points` | Sets city points in `data/catalog.json` from `data/gazetteer.json`. | nothing else |
| `python tools/build_catalog.py --check` | Checks `data/catalog.json` against `data/v/`, `data/sources.json` and `tools/catalog.src.json`. It expects one variable per source entry, 43 places, at least 200 countries, 4 groups, and Cambodia's heat series within 0.2 °C of the snapshot. | the claim-desk snapshot |
| `python tools/parity/parity.py` | Screenshots the analyst prototype and this app in the same states and diffs them. | `tools/parity/requirements.txt`, a running server |

## Configuration

Every environment variable the code reads is below. The real environment wins over `.env`, and `.env` wins over the default.

| Name | Read in | Default | Effect |
|---|---|---|---|
| `EB_HOST` | `run.py` | `127.0.0.1` | The address the local server binds to. |
| `EB_PORT` | `run.py` | `8000` | The port the local server listens on. |
| `EB_DB` | `cache.py` | unset | Path of the SQLite cache file. `:memory:` is allowed. It overrides the Vercel default. `EB_OFFLINE=1` overrides it. |
| `EB_OFFLINE` | `net.py`, `cache.py` | unset | Exactly `1` serves synthetic POWER data, keeps the cache in memory, and turns AI and speech off. The process refuses to start if `VERCEL` is also set. |
| `EB_LLM` | `net.py` | `bedrock` | The language model: `bedrock` or `selfhosted`. Any other value makes `ai_available()` false and `ask_model` raise `AIFailed`. Read on each call. |
| `EB_MODEL` | `net.py` | `au.anthropic.claude-haiku-4-5-20251001-v1:0` | The Bedrock model ID. Read on each call. |
| `EB_AWS_REGION` | `net.py` | `ap-southeast-2` | The AWS region of the Bedrock client. Read once, on the first model call, so a change needs a restart. |
| `AWS_BEARER_TOKEN_BEDROCK` | `net.py`, the SDK | unset | A Bedrock API key. Setting it makes `ai_available()` true. |
| `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` | `net.py`, the SDK | unset | An IAM access key pair. Both must be set for `ai_available()` to be true. |
| `EB_LLM_BASE_URL` | `net.py` | unset | The self-hosted server's base URL. The code appends `/chat/completions`. |
| `EB_LLM_API_KEY` | `net.py` | unset | The self-hosted server's bearer key. |
| `EB_LLM_MODEL` | `net.py` | `qwen3-4b` | The model name sent to the self-hosted server. Separate from `EB_MODEL`, so switching provider is one change to `EB_LLM`. |
| `EB_LLM_TIMEOUT_S` | `net.py` | `10` | Seconds to wait for the self-hosted server. |
| `EB_LLM_LANGS` | `net.py` | `en` | Languages the self-hosted model writes, comma separated. `net.model_writes(lang)` reads it on each call. For any other language `explain` shows the template and calls no model. Bedrock always writes `en` and `km`. |
| `KIRITTS_API_KEY` | `voice.py` | unset | Turns speech on. It also keys the signature of `/api/say` links. |
| `TELEGRAM_WEBHOOK_SECRET` | `server.py` | unset | Turns `/api/telegram` on. Unset means the route returns 404. |
| `TELEGRAM_BOT_TOKEN` | `telegram.py` | unset | Lets the bot fetch voice messages and show "typing…". Text questions work without it. |
| `VERCEL` | `cache.py`, `net.py` | set by Vercel | Moves the default cache to `/tmp/eb/cache.sqlite`, and blocks `EB_OFFLINE=1`. |

`.env.example` also lists `POWER_COMMUNITY`. No code reads it. `power.py` sends `community=AG` as a literal.

`ai_available()` is true only when `EB_OFFLINE` is not `1` and the provider that `EB_LLM` names has its credentials. For `bedrock`, that is `AWS_BEARER_TOKEN_BEDROCK` or both access key variables. For `selfhosted`, it is `EB_LLM_BASE_URL` and `EB_LLM_API_KEY`. `/api/status` reports `model` as the chosen provider's model, or `unknown EB_LLM '<value>'`. Without credentials, `ask_model` raises `AIFailed`, and a client that sends `ai: true` gets the template text with `via: "template"`.

## Build and deploy

There is no build step in the repository. Vercel installs `requirements.txt` and bundles the function from `main.py`. `vercel.json` is the whole Vercel configuration.

```json
{
  "regions": ["sin1"],
  "functions": { "main.py": { "maxDuration": 300, "includeFiles": "{data,web}/**" } }
}
```

- `regions` pins the function to `sin1`.
- `maxDuration` is 300 seconds.
- `includeFiles` adds `data/` and `web/` to the bundle. The app reads both at run time.
- It has no `rewrites`, and `tests/test_deploy.py` asserts that none exists. The Vercel FastAPI preset sends every path to `app`, and a rewrite breaks the paths.

`.vercelignore` keeps `.env`, `.env.*`, `data/cache.sqlite`, `.venv/`, `.claude/`, `__pycache__/`, `.pytest_cache/` and `tools/cache/` out of the upload.

`requirements.txt` lists ten packages: `fastapi`, `uvicorn`, `httpx`, `pydantic>=2`, `numpy`, `scipy`, `statsmodels`, `pymannkendall`, `anthropic[bedrock]` and `pytest`. Only `pydantic` has a bound, so each build resolves the newest versions. The repository sets no Python version for Vercel.

The repository holds no CI configuration. How a commit reaches production, and the production environment variables, are set in the Vercel project and are not visible here. `docs/00-foundation.md` names `vercel --prod` for a deploy by hand.

**Check a deployment.** Call `GET /api/status`. `model` names the model in use: the `EB_MODEL` ID on Bedrock, the default, or the `EB_LLM_MODEL` name when `EB_LLM=selfhosted`. `ai_available` and `voice.available` show whether the credentials reached that environment. On 2026-11-15 a `POST /api/telegram` to production without the secret header returned 403, so the webhook secret is set there.

## Local development and tests

1. Create the environment. `uv` manages it, and it has no `pip`.

   ```
   uv venv --python 3.12 .venv
   uv pip install --python .venv -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in only what you need. With no model credentials, no KiriTTS key and no Telegram secret, those three features are off and everything else works.
3. Start the server with `.venv/bin/python run.py`, then open http://127.0.0.1:8000.

`run.py` starts `uvicorn` with `reload=True`, so it runs a reloader process and a worker. Set `EB_PORT` to run several copies side by side. Set `EB_OFFLINE=1` to work without NASA POWER. The result then carries the synthetic-data note.

Run the tests with `.venv/bin/python -m pytest -q`. `pytest.ini` sets `testpaths = tests`, and 473 tests are collected. They need no network and no credentials.

`tests/conftest.py` holds one autouse fixture, `sealed`. For every test it sets `EB_DB` to `:memory:`, unsets `EB_LLM`, resets the cache, replaces `net.sleep` with a no-op so retries do not wait, and installs an `httpx.MockTransport` and a model stub that both raise `AssertionError`. A test that expects traffic calls `net.stub(transport=..., model=...)`. Most point tests pass `httpx.MockTransport(fixtures.handler)`, the same synthetic source that offline mode uses.

## Deviations from SPEC

**Layout and types**

| Deviation | Why |
|---|---|
| `analyses/` is a package with one module per kind, not one `analyses.py` | one doc maps to one file |
| `ANALYSES` is `dict[str, Analysis]` and is called through `analyses.run`. An analysis is `fn(q, Words) -> Finding`, not `fn(Question) -> Result` | verdict keys and fields need a home on the one entry, and one place builds every `Result` |
| Modules the SPEC layout does not list: `net.py`, `words.py`, `fixtures.py`, `telegram.py`, `analyses/base.py`, `analyses/investigate.py`, `web/investigation.js` | one network door, one sentence table, synthetic data kept out of `power.py`. SPEC describes the bot and the investigation but names no file for them |
| Retries and the cache call live in `net.py`, not in `power.py` | one door for every request |
| Templates live in `words.py`, not in `explainer.py` | headlines and templates share one key space and one coverage test |
| `Fact` drops `float` | turns the `fmt` rule into a type error |
| `Result` has a required `investigation` field that SPEC's `Result` does not show | `docs/19-investigation.md` adds it |
| `Source` takes the full registry shape from `docs/16`. `short_name` and `version` may be null. `accessed` is `datetime.date \| None`, not `str \| None` | a method paper has no short name or version. Pydantic checks the `YYYY-MM-DD` text and writes the same text back |
| `claim_verdict` returns `Scored(verdict, survives, final)` | computing `final` is statistics |
| `detail.second_look`, which `docs/05-claim-check.md` lists, does not exist. The note applies to all kinds | analyses do not see `revision` |
| The catalog `Variable` gains `season` and `per_day`, and `aggregate` allows `"max"` | `rain_dry`, mm/day rain and `hottest` need data, not `if variable ==` |
| `cache.py` reads `EB_OFFLINE` from the environment itself | keeps it free of package imports |

**API**

| Deviation | Why |
|---|---|
| `POST /api/run` accepts `lang` and `via` | SPEC gives the server the headline but not the language. `via` marks an audit run |
| `POST /api/read` accepts `{draft, lang}` | a card edit goes through `guard`, as `docs/04` requires |
| `GET /api/catalog` adds `kinds` | replaces a hand-written JS `FIELDS` table |
| `GET /api/audit` accepts `lang` | the verdict word is server prose |
| `/api/status` adds `offline`, and `run()` adds the synthetic-data note from `net.OFFLINE` | the page needs no per-source flag |
| `GET /data/countries.geojson` and `GET /data/summary.json` exist, and `data/` is never mounted | the map needs two files, and `data/cache.sqlite` must not be downloadable |
| FastAPI's `/docs`, `/redoc` and `/openapi.json` are served | the app keeps the FastAPI defaults |
| The Telegram reply carries `parse_mode`, `link_preview_options` and `reply_markup` beside the three keys SPEC lists | `docs/18-telegram.md` specifies the full reply |
| No response carries `ai_failed`, which SPEC's error paragraph names | it described an AI reader, and no model reads the sentence |

**Behaviour**

| Deviation | Why |
|---|---|
| The web page never sends `ai: true`, so it always shows template text. SPEC's definition of done asks for the demo sentences "with the AI writer on and with it off" | the page promises that a sentence never leaves the server. The writer is reachable through `/api/explain` and the Telegram bot |
| `web/` and server code may link to `https://doi.org/` | `docs/16` wants a DOI link per source on screen. `doi.org` is a citation link only, never a data host |
| `tools/build_catalog.py` also reads the claim-desk snapshot, and `tools/grids/*.py` read other NASA archives. SPEC names only the POWER Zarr stores and the SEDAC grids, and speaks of 27 variables. The catalog has 44 | 12 variables come from NASA products that POWER does not carry. Every one is registered in `data/sources.json` |

## Tradeoffs accepted

- We accept threads and a semaphore in exchange for no `await` anywhere and plain pytest. The ceiling is one process's thread pool.
- We accept `detail: dict` on the wire in exchange for no second discriminated union.
- We accept `lang` on `/api/run`, so switching language runs each shown question again, in exchange for all prose coming from one server table.
- We accept that `/api/explain` trusts the `Result` the client posts. A forged `facts` changes only the forger's own screen and audio.
- We accept that layer rules are a test, not a language feature.
- We accept that every headline variant must be its own verdict key.
- We accept a rigid layout for the JS tables in exchange for no Node in CI.
- We accept one POWER request per parameter.
- We accept that `net.post`, `net.get` and `net.post_stream` take any URL. Tests on the source text, not code on the call path, keep their hosts to KiriTTS, Telegram and `EB_LLM_BASE_URL`.

## Alternatives considered

- **The SPEC's flat layout.** One `analyses.py` with `dict[Kind, fn]`, a `FIELDS` literal in JS, and templates in `explainer.py`. A kind's facts would live in four files and two languages, and every analysis would repeat `Result` assembly. Rejected because of the hand-synced lists.
- **Async with an injected `Context`** (the analyst prototype). This puts `await` and `ctx` on every signature to serve one fan-out function, and it needs a test plugin. Rejected.
- **A language-neutral `Result` rendered in the browser.** The explainer needs prose on the server, which means two template engines whose placeholders must match the facts across the wire. Rejected.
- **A staged pipeline per kind** (fetch, then compute, then present). Three signatures per kind repeating one shape. `Finding` keeps the one useful split, deciding versus phrasing.
- **Kinds as self-registering plugins.** Pydantic's union and the share-link parser both need a static `Question`. Registering at import time adds magic for no gain.
- **Verdict keys that include the direction** (`trend.clear_up`). They double the keys, and a direction word in `facts` covers the same need.
- **Per-kind word tables.** One table gives one coverage test for both languages.

## Partly built

`SPEC.md` holds the build order. Code exists for every row of its table. These parts are present but not complete.

- **Khmer.** The page has a language switch, and all 337 UI strings have a Khmer entry. `words.KM` holds 535 of the 595 server keys, and a missing key falls back to English. The `researcher` template exists in Khmer for 3 of 28 verdict keys, and the others fall back to the Khmer `student` text. In Khmer the composer shows the `foot.km_draft` line, which says a native reader has not reviewed the text.
- **The AI writer.** `explainer.explain` and both providers are tested, but the web page never asks for AI text.
- **The `policymaker` audience.** Templates exist and `/api/explain` accepts it. The page's two modes use only `student` and `researcher`.
- **Case files.** `data/cases.json` holds one case.
- **Unbuilt-kind handling.** `reader._finish` and the card still handle a kind with no `ANALYSES` entry (`question: null`, the "not built" label). All eight kinds are built, so that path does not run today.
- **Layer rules for `telegram.py`.** `tests/test_layers.py` does not list the module.
