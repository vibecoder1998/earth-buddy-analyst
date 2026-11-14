# Catalog and region data

The catalog is the closed list of what the app can measure and where. The reader's schema, the card's dropdowns, and every analysis read from it. Priority P0. Estimate 1 hour if the data files are reused, 4 hours if rebuilt.

## Files

`data/catalog.json`:

```json
{ "years": [2001, 2024],
  "variables": [Variable],
  "places": [Place],
  "countries": { "KHM": { "name": {"en": "Cambodia", "km": "កម្ពុជា"}, "aliases": {"en": [], "km": []}, "cells": 16, "lat": 12.688, "lon": 105.125 } },
  "groups": [Group],
  "topics": [ { "id": "heat", "label": {"en": "Heat", "km": "..."} } ] }
```

```python
L10n = {"en": str, "km": str}

class Variable:
    id: str                    # "heat"
    label: L10n; what: L10n; definition: L10n
    unit: str                  # unit of a yearly value: "°C", "mm", "%"
    decimals: int
    rel: bool                  # True: trend shown as % of the mean per decade (rain, fire)
    aggregate: "mean" | "sum"  # how months combine into a year and cells into a region
    warm_up: bool              # True: a rise gets the warm colour
    topics: list[str]          # "heat" | "water" | "air" | "ice" | "fire" | "land"
    keywords: {"en": list[str], "km": list[str]}   # lower-case words that point at this variable
    up: {...}; down: {...}                         # words meaning rises ("hotter") or falls ("cooler")
    source: {param, kind, resolution, ids: list[str]}   # ids are data/sources.json entries: dataset, method paper, "power"
    caveats: {"en": list[str], "km": list[str]}
    doubt: "up" | "down" | None    # a trend this way is physically doubtful
    regional: bool             # True: data/v/<id>.json has country and place series
    point_param: str | None    # NASA POWER monthly point parameter; None: no live point data
    point_scale: float         # multiplies point values: 100 for GWETROOT, GWETTOP and FRSEAICE, which POWER serves as fractions
    first_year: int            # first year of the point record (1981 for most MERRA-2 values)

class Place:
    id: str                    # "p.mekong-delta"
    name: L10n; aliases: {"en": list[str], "km": list[str]}
    kind: "city" | "desert" | "rainforest" | "estuary" | "basin" | "mountains" | "polar" | "farmland" | "region"
    bbox: [south, west, north, east]; lat: float; lon: float; cells: int

class Group:                   # for rank
    id: "southeast_asia_capitals" | "cambodia_provinces" | "countries" | "places"
    name: L10n
    members: list[Region]      # "countries" and "places" list catalog regions; the others list gazetteer Points
    member_aliases: dict[str, list[str]]   # Point name -> other lower-case spellings: the SEDAC name, common forms
    note: L10n                 # "Each province is the grid cell at its NASA SEDAC centre point."
```

`data/v/<id>.json`, one file per regional variable:

```json
{ "id": "tmin", "years": [2001, 2024], "regions": { "KHM": [22.31, null], "p.mekong-delta": [] }, "cells": { "KHM": 16 } }
```

Each list has one value per year. `null` marks a missing year. A region with no usable cells is left out.

`data/summary.json` is per variable and per country: `{trend_per_decade, p, q, direction}`. The map reads it (`docs/14-web-ui.md`). `tools/build_catalog.py` computes it with `stats.trend_test` and Benjamini-Hochberg across countries.

`data/audit.json` holds the frozen claims (`docs/12-scan-and-audit.md`).

`data/countries.geojson` holds one feature per country, `{id: ISO3, name}`. Each feature is the union of the country's 1° cells, so the map shows exactly the area the series averages. The build makes it from the NASA SEDAC GPWv4.11 National Identifier Grid (`gpw-natid`).

`data/gazetteer.json` holds `[{name, alt_names, iso3, level, lat, lon}]` for every admin unit at levels 0 to 2. The build makes it from the NASA SEDAC GPWv4.11 Administrative Unit Center Points (`gpw-adm-points`). Each entry is the land-area-weighted centre of the centre points of its smallest units. An entry with `composed: true` is a unit that the SEDAC data predates, built from SEDAC districts (see "Build the data").

`data/sources.json` is the reference registry (`docs/16-data-sources.md`).

## The 27 variables

| id | Point param | Source |
|---|---|---|
| heat | T2M | MERRA-2 |
| rain | PRECTOTCORR | MERRA-2 |
| soil | GWETROOT | MERRA-2 |
| fire | none | MODIS MCD14ML fire counts |
| tmax | T2M_MAX | MERRA-2 (regional file uses T2M_MAX_AVG) |
| tmin | T2M_MIN | MERRA-2 (regional file uses T2M_MIN_AVG) |
| hottest | T2M_MAX | MERRA-2, the year's maximum |
| trange | T2M_RANGE | MERRA-2 |
| skin | TS | MERRA-2 |
| humid | RH2M | MERRA-2 |
| vapor | QV2M | MERRA-2 |
| topsoil | GWETTOP | MERRA-2, land only |
| evap | EVLAND | MERRA-2 |
| wind | WS10M | MERRA-2 |
| colvapor | TQV | MERRA-2 |
| ozone | TO3 | MERRA-2 |
| snow | SNODP | MERRA-2 |
| frost | FROST_DAYS | MERRA-2, monthly counts |
| seaice | FRSEAICE | MERRA-2 |
| sun | ALLSKY_SFC_SW_DWN | CERES SYN1deg |
| cloud | CLOUD_AMT | CERES SYN1deg |
| aerosol | AOD_55_ADJ | CERES SYN1deg |
| albedo | ALLSKY_SRF_ALB | CERES SYN1deg |
| uv | ALLSKY_SFC_UV_INDEX | CERES SYN1deg |
| rain_sat | none | GPM IMERG |
| rain_dry | PRECTOTCORR, Nov to Apr | MERRA-2 |
| rain_wet | PRECTOTCORR, May to Oct | MERRA-2 |

`doubt` is `"down"` for heat, fire, tmax, tmin, and skin. Confirm each point parameter against the NASA POWER parameter list during the build. Set `point_param` to `None` for any parameter that the monthly point API does not serve.

## Build the data

Reuse is the fast path. Copy the files `SPEC.md` lists. Then write a small script that does four things: rebuild the country series with the SEDAC country grid, build the gazetteer, add the new fields (`point_param`, `first_year`, `regional`, `groups`, `source.ids`, `countries[*].name.km`), and write `summary.json`.

The full rebuild ports `~/earth-buddy/tools/catalog_build.py`:

- It reads raw chunks from four open NASA POWER Zarr stores on `nasa-power.s3.amazonaws.com`: MERRA-2 annual, MERRA-2 monthly, CERES SYN1deg annual, and IMERG annual. No Earthdata login is needed.
- Fire has no POWER store. Its country series reuse the claim desk's 1° grid of MODIS MCD14ML fire counts (`fire_years.f32` in the snapshot, read at build time and not copied) with the ownership rule below.
- It bins native cells into 1° cells with a NaN-aware mean.
- A country's cells come from the NASA SEDAC GPWv4.11 National Identifier Grid, a 30 arc-second grid of country codes. A 1° cell belongs to the country that owns the pixel at its centre, so a cell centred on water belongs to no country. This is the claim desk's cell-centre rule with NASA borders. A country that owns no cell this way gets the cell holding most of its pixels. The rule that gives a cell to the country owning most of its land pixels was measured and rejected. With it, Cambodia's heat series differs from the claim desk's by up to 0.73 °C in a year, against 0.19 °C with the cell-centre rule and the 0.2 °C acceptance below.
- Group members for `southeast_asia_capitals` and `cambodia_provinces` are gazetteer names listed in `tools/catalog.src.json`. The build fails on a name that matches no gazetteer entry.
- A composed unit is a unit newer than the SEDAC boundaries. `tools/catalog.src.json` lists its parent and its SEDAC districts. Its centre is the centre of those districts, and the build removes them from the parent's centre. The one composed unit is Tbong Khmum, split from Kampong Cham in 2013. Its districts are Dambae, Krouch Chhmar, Memot, Ou Reang Ov, Ponhea Kraek, Suong, and Tboung Khmum. Before the removal, Kampong Cham's centre was 12.025, 105.600 over 9,250 km², in the same POWER cell as Tbong Khmum. After it, Kampong Cham is 12.128, 105.273 over about 4,369 km², and Tbong Khmum is 11.933, 105.892. The build fails on a listed district that the gazetteer does not have.
- A place's cells are the whole-degree cells in its bbox.
- A region series is the cos(latitude)-weighted mean of its cells (a sum for counts). A cell with any missing year is dropped.
- `rain_dry` sums November through April. November and December count toward the next year's dry season.
- Run: `uv run --python 3.12 --with numpy --with numcodecs --with shapely python tools/build_catalog.py`. Add `--check` to validate.

## Rules

- Variable ids, region ids, and group ids are the reader's enums. Changing one is a schema change.
- Every user-facing word in the catalog is an `L10n` pair. English is required. Khmer falls back to English.
- A point analysis uses the variable's `first_year`. A country or place analysis uses `catalog.years` (2001 to 2024).

## Acceptance

- `catalog.load()` returns 27 variables, 43 places, at least 200 countries, and 4 groups. The SEDAC grid sets the exact country count. Record it in the README.
- Every variable's `source.ids` exist in `data/sources.json`.
- Every `data/v` file has the same `years` as the catalog, and every list has that many values.
- `--check` confirms that the new Cambodia heat series matches the claim desk's `KHM` heat series to within 0.2 °C every year. The two border sources differ slightly, so the series may too.
- Cambodia has a gazetteer entry for each of its 25 provinces.
- `summary.json` has an entry for every regional variable and every country with a series.

## Reference

`~/earth-buddy/docs/CLAIM-DESK.md` "Types" and "Data files". `~/earth-buddy/tools/catalog_build.py`. `~/earth-buddy/earth-buddy-analyst/earthbuddy/brain/catalog.json` has the point parameters and first years.
