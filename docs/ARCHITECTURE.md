# Architecture

How the code in `earthbuddy/` and `web/` is laid out, and why. `SPEC.md` is still the contract. This file names every place the code departs from it, in "Deviations from SPEC".

Short version: the code is synchronous. A question kind is one record in `ANALYSES`. A field name is the unit of reuse on both sides of the wire. Every sentence the server writes comes from one table keyed by verdict key. Exactly one module can reach the network, and it reaches only NASA hosts and the Anthropic API. Every source is one entry of `data/sources.json`.

## Problem

Eight question kinds, two languages, AI on or off, about 17 hours of work for P0. The SPEC's hard rules are all "one list" rules, and the naive layout breaks each of them:

- **"A new kind adds one `ANALYSES` entry."** A bare `dict[Kind, fn]` has no room for what else a kind owns. That is its verdict keys (which the explainer must cover), its reader cues, and its card fields. Without a home, those turn into hand-synced lists in `reader.py`, `explainer.py`, and `web/app.js`.
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
    "where": Analysis(WhereQ, where.where, where.VERDICTS, cue_rank=5, cues={"en": (r"\bwhere\b",), "km": (...)}),
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

1. **`Analysis` record** (`analyses/base.py`) holds `question` (the pydantic model), `fn`, `verdicts`, `cues` and `cue_rank`. Everything another module needs to know about a kind is a field here. The card's fields come from `question.model_fields`.
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
   - `net.get_json` owns the httpx client, the retry policy, the 3-request `BoundedSemaphore`, and the cache read and write. `net.ask_model` owns the Anthropic call.
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
| No code or page points at a host outside `*.nasa.gov`, `nasa-power.s3.amazonaws.com`, `api.anthropic.com` | `test_no_url_outside_allowed_hosts` greps `earthbuddy/` and `web/` |
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
| `net.py` | the only network door (NASA hosts and the Anthropic API only), the offline swap, test stubs | `get_json`, `ask_model`, `ai_available`, `model_id`, `OFFLINE`, `stub` | `catalog`, `power`, `series`, `analyses`, `reader`, `explainer`, `server` |
| `catalog.py` | `data/catalog.json`, `data/v/*.json`, `audit.json`, `sources.json`; names, aliases and centres | `load`, `sources`, `ALLOWED_AGENCIES`, `variable`, `variables`, `name`, `centre`, `cells`, `find_region`, `group`, `years`, `regional_values`, `audit`, `raw` | `net`, `power`, `series`, `stats`, `analyses`, `reader` |
| `power.py` | POWER URLs and payload parsing | `point`, `grid`, `last_complete_year`, `Monthly` | `catalog`, `series`, `stats`, `analyses` |
| `geocode.py` | free text to `Point`, offline: coordinates, the catalog, then the local NASA SEDAC gazetteer `data/gazetteer.json` | `search` | `net`, `power`, `series`, `stats`, `analyses`, `reader` |
| `series.py` | the only way an analysis gets data | `get_series`, `get_many`, `get_grid`, `annualise` | `analyses`, `reader`, `net` (it goes through `power`) |
| `analyses/base.py` | `Analysis`, `Finding`, shared chart and fact helpers | `Analysis`, `Finding`, `fit_or_none`, `per_decade`, `line_chart` | `reader`, `explainer`, `server`, `net`, `power` |
| `analyses/<kind>.py` | one kind: its detail model, `VERDICTS`, its function | `<kind>`, `VERDICTS`, `<Kind>Detail` | other kind modules, `net`, `power`, `reader` |
| `analyses/__init__.py` | the registry, and the only `Result` constructor | `ANALYSES`, `run`, `kinds_meta` | `reader`, `explainer`, `server` |
| `reader.py` | sentence or raw dict to `Draft` and `Question` | `read`, `reread`, `question_from`, `guard`, `read_keywords`, `FILL` | `series`, `power`, `explainer`, `server` |
| `explainer.py` | the explanation and the number check | `explain`, `numbers_ok` | `series`, `power`, `reader`, `server` |
| `server.py` | routes, error mapping, static files, the `.env` loader | `app` | — |
| `tools/build_catalog.py` | one-time data adaptation (`--adapt`), `summary.json`, `--check` | CLI | not imported by the app |

`web/` holds `index.html`, `app.js` (state, views, `EDITORS`, `PANELS`), `charts.js` (`CHARTS`), `map.js`, `i18n.js` (`EN`, `KM`, `t`), `styles.css` and `vendor/`.

## Keeping lists in sync

| List | Home | Other copies | How they stay equal |
|---|---|---|---|
| kinds | `ANALYSES` (built kinds) | `Kind` literal, `Question` union | `test_registry`: `ANALYSES` keys ⊆ `Kind` == union members |
| card fields per kind | `Question` models | none (`/api/catalog.kinds`) | derived. There is no JS `FIELDS` table |
| field names | `Question` models | `reader.FILL`, JS `EDITORS`, i18n `field.*` | `test_registry` and `test_web_sync` |
| kind panels | JS `PANELS` (optional) | `ANALYSES` | `test_web_sync`: keys ⊆ kinds |
| chart types | `Chart` union | JS `CHARTS` | `test_web_sync`: the sets are equal |
| verdict keys | `Analysis.verdicts` | `words.EN` | `test_words`. `run()` also asserts membership |
| reader cues | `Analysis.cues` | none | single source. The AI schema's kind enum is `list(ANALYSES)` |
| thresholds | `stats.T` | none | grep test |
| server strings | `words.EN` | `words.KM` | `test_words`: KM keys ⊆ EN keys, with the same placeholders |
| UI strings | `i18n.js EN` | `KM`, the `t("...")` calls | `test_web_sync`, per `docs/15` |

`test_web_sync.py` reads JS tables with regexes over `const NAME = {` … `};`, one key per line. No Node and no build step are needed. Each JS table carries a comment stating this layout.

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
| `ANALYSES: dict[Kind, Analysis]`, called through `analyses.run` | verdict keys, cues and fields need a home on the one entry |
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
2. Do numpy, scipy and statsmodels together fit Vercel's function size limit? Deploy the full requirements in hour one to find out.
3. Is the extended API acceptable: `lang` on run, `kinds` on catalog, `draft` on read?
4. If Hamed-Rao fails the AR(1) check at n = 24, `trend_test` switches to the claim desk's variance table, and the audit verdicts move (`docs/12`).
5. The proposed `level` for each claim verdict: supported, opposed and step are `clear`; mixed is `likely`; unsupported is `unclear`; nothing is `too_short`.

## Next implementation step

Row 3: write `tools/build_catalog.py --adapt` and `catalog.py`, then make `tests/test_catalog.py` pass (27, 43, at least 200 and 4, plus the year lengths).
