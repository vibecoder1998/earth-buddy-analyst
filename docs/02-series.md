# Series sources and cache

`series.get_series(region, variable, window)` is the only way an analysis gets data. A country or place reads its precomputed annual series. A point fetches NASA POWER live and caches the response. Priority P0. Estimate 1.5 hours.

## Behaviour

```python
def get_series(region: Region, variable: VariableId, window: Window) -> Series
def get_grid(box: tuple[float, float, float, float], variable: VariableId, window: Window) -> list[Series]   # where map
```

| Region | Source | Years | Monthly |
|---|---|---|---|
| Country, Place | `data/v/<variable>.json` | 2001 to 2024 | no |
| Point | POWER monthly point API | `first_year` to the last complete year | yes |

- The window clips the series. A window outside the available years raises `ValueError("window")`, and the API returns a 400 error.
- A regional series asked for a variable with `regional: false` raises `ValueError("not-regional")`. The card offers a point instead.
- A point asked for a variable with `point_param: None` raises `ValueError("no-point-data")`.

## NASA POWER client (`power.py`)

- Point: `GET https://power.larc.nasa.gov/api/temporal/monthly/point?parameters=<P>&community=AG&longitude=<lon>&latitude=<lat>&start=<YYYY>&end=<YYYY>&format=JSON`. Values are at `properties.parameter[P]["YYYYMM"]`. Month `13` is the annual value. Drop it.
- Regional (where map only): `GET .../api/temporal/monthly/regional?parameters=<P>&community=AG&latitude-min&latitude-max&longitude-min&longitude-max&start&end&format=JSON`. It takes one parameter per request. Each side must be 2° to 4.5°.
- A value that equals `header.fill_value` or is at most −990 becomes missing.
- A 422 on the latest year means that year is not published yet. Retry once with `end − 1`.
- Retry up to 4 attempts on 429, 5xx, or a network error, with a backoff of 1.5 × 2ⁿ seconds. Allow 3 requests at once. Time out after 120 s, with 20 s to connect.
- Raise `DataSourceError(message, status, url)` on failure. The API returns it as a 502 error.
- `last_complete_year` is the current year minus 1.

## Monthly to annual

- Keep a year only when all 12 months are present.
- `aggregate: "mean"`: the year is the mean of its months.
- `aggregate: "sum"` for a rate (POWER rain is mm/day): multiply each month by its number of days, then sum. Counts such as `FROST_DAYS` are already monthly totals. Sum them as they are.
- `rain_dry` and `rain_wet` are seasonal sums of PRECTOTCORR (`docs/01-catalog-and-data.md`).

## Cache (`cache.py`)

- One SQLite table: `cache(key TEXT PRIMARY KEY, payload BLOB, source TEXT, fetched_at REAL)`. The key is the full request URL. The payload is zlib-compressed JSON.
- The cache holds data for 30 days. A cache hit sets `Source.cached = True`, and the result's sources say so.
- One connection guarded by a lock is enough.
- On Vercel the disk is temporary, so the cache starts empty on each new instance. That is acceptable.

## Offline mode

`EB_OFFLINE=1` replaces the POWER client with a fixture that returns POWER-shaped responses. The values are deterministic: seed a random generator from a crc32 of the request, then add a per-variable mean, a seasonal cycle, a trend, and noise. Every result shows a banner: "Synthetic data, not NASA". Use it for tests and for work without a network.

## Geocoding (`geocode.py`)

- `"11.55, 104.92"` parses straight to a `Point`.
- Otherwise call Open-Meteo: `https://geocoding-api.open-meteo.com/v1/search?name=<q>&count=5&language=en&format=json`. If it fails, call Nominatim: `https://nominatim.openstreetmap.org/search?q=<q>&format=jsonv2&limit=5`.
- Cache answers for 365 days. Send a generic `User-Agent` such as `earth-buddy/1.0`.
- Before calling out, match catalog place names and aliases. "Phnom Penh" resolves to `p.phnom-penh` with no network call.

## Acceptance

- `get_series(Country("KHM"), "heat", None)` returns 24 values with no network call.
- With `EB_OFFLINE=1`, `get_series(Point(11.55, 104.92, "Phnom Penh"), "heat", None)` returns annual values from `first_year` and keeps the monthly values.
- A second identical point call reads from the cache. A test counts the HTTP calls.
- Rain at a point converts mm/day to a yearly total: a constant 1 mm/day gives 365 or 366 mm.
- A stubbed 503 from POWER retries, then raises `DataSourceError` carrying the URL.

## Reference

`~/earth-buddy/earth-buddy-analyst/earthbuddy/connectors/{power,geocode,fixtures}.py` and `earthbuddy/brain/store.py`.
