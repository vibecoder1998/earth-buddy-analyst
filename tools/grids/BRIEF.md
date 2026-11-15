# Grid fetcher brief (one family per agent)

Repo: /Users/lonwolf/earth-buddy-analyst. Read `CLAUDE.md`, `docs/16-data-sources.md`, and `tools/build_catalog.py` (`bin1`, `yearly`, `area_series`, `extend`) first.

## Goal
For each variable in your family, write a yearly 1° grid that `tools/build_catalog.py --extend` reads through a `{"grid": "<vid>.f32"}` store.

## Output, exactly
1. `tools/grids/<family>.py`: runnable as `.venv/bin/python tools/grids/<family>.py`. It downloads into `tools/cache/<family>/`, skips files it already has, and resumes after a crash. It writes `tools/cache/grids/<vid>.f32`:
   - float32, shape (24, 64800), C order; row i = year 2001+i, through 2024
   - cell index = (floor(lat)+90)*360 + (floor(lon)+180) % 360, same as `bin1`
   - a cell value = mean of the native pixels whose centres fall in it (like `bin1`), or a sum when the variable is a count
   - NaN = no data. Years before the record starts are NaN. A year missing months is NaN unless your brief says otherwise.
2. `tools/grids/<family>.json`:
   ```json
   {"stores": {"<store>": {"grid": "<vid>.f32", "sum": false}},
    "variables": {"<vid>": <entry in the exact shape of tools/catalog.src.json variables.wind50: point_param null, first_year, store, ids, text{label,what,definition,unit,decimals,rel,aggregate,warm_up,topics,keywords,up,down,source{param,kind,resolution},caveats,doubt}; every text field in en AND km (Khmer)>},
    "sources": [<records in the exact shape of data/sources.json; "via": null; "accessed": null>],
    "docs16_rows": ["| `id` | Dataset | Agency, centre | DOI | Used for |"],
    "notes": "<anything the merger must know>"}
   ```
   `topics` must use only: heat, water, air, ice, fire, land. Reuse existing source ids where they exist (e.g. `merra2-aer-monthly`, `merra2-paper`).

## Rules
- Data only from NASA hosts: `*.nasa.gov` and the NASA Earthdata Cloud S3 links that those hosts redirect to. No third-party mirror, ever. If the only route is non-NASA, stop and report it.
- Earthdata auth: `~/.netrc` (machine urs.earthdata.nasa.gov) already works. Use a cookie-aware opener or `curl -n -L -c/-b`.
- Prefer OPeNDAP/subsetting so you download only the variables you need.
- Every DOI must resolve: `curl -s https://doi.org/api/handles/<doi>` returns `"responseCode":1`. Write citations in the provider's recommended form (landing page).
- Do NOT edit: `tools/catalog.src.json`, `data/`, `docs/`, `earthbuddy/`, `tools/build_catalog.py`, `tools/requirements-build.txt`. Only create files under `tools/grids/` and `tools/cache/`. h5py, netCDF4, pyhdf, numpy are installed in `.venv`. Install nothing else; if you need another package, say so in `notes`.
- Run downloads in the background. Use the cache, and do not re-download.
- Leave one runnable check: an assert block at the end of your script (`--check` flag) that loads each grid and asserts its shape, a finite fraction, and a plausible value range.

## Report back (short)
Per variable: file written yes/no, global land mean per year for 2001, 2012 and 2024, Cambodia value (cells lat 10–14, lon 102–107) for the same years, % finite cells, bytes downloaded, wall time, and any caveat.
