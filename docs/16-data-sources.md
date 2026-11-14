# Data sources and references

Every piece of data the app uses comes from NASA or a NASA partner agency, and every one is cited. This covers measurements, country borders, place names, and map imagery. Code enforces the rule: a source that is not in the registry, or not from an allowed agency, fails the tests. Priority P0. Estimate 1 hour.

## The rule

1. Every data file and every live data call names a source id from `data/sources.json`.
2. Every source in `data/sources.json` comes from an agency in `ALLOWED_AGENCIES`.
3. Every source carries a full citation, and a DOI when the dataset has one.
4. Every result shows its sources with their citations. The **About the data** page and the README list them all.

Software is not data. MapLibre, fonts, and Python libraries are listed with their licenses in the README, not in the registry.

## Registry

`data/sources.json` is a list of `Source` records. The `Source` type in `SPEC.md` gains these fields.

```python
class Source(BaseModel):
    id: str                  # "merra2-slv-monthly"
    name: str                # "MERRA-2 tavgM_2d_slv_Nx: 2d, Monthly mean, Single-Level Diagnostics"
    short_name: str          # "M2TMNXSLV"
    version: str             # "5.12.4"
    agency: str              # "NASA" | "NASA/JAXA"; must be in ALLOWED_AGENCIES
    center: str              # "NASA GSFC GES DISC"
    doi: str | None
    url: str                 # landing page
    citation: str            # full reference text, shown on screen
    via: str | None          # "NASA POWER" when the app reads it through POWER
    accessed: str | None     # set by the build, YYYY-MM-DD
    cached: bool             # per response, set at run time
```

`ALLOWED_AGENCIES` lives in `earthbuddy/catalog.py`. It starts as `{"NASA", "NASA/JAXA"}`. To add a partner agency, add its name with a link to the Space Apps 2026 resources page that lists it as a partner.

## References

All DOIs below resolved through doi.org on 14 Nov 2026.

| id | Dataset | Agency, centre | DOI | Used for |
|---|---|---|---|---|
| `power` | NASA POWER (Prediction Of Worldwide Energy Resources) | NASA LaRC | none | Live point and regional data, and the Zarr stores the build reads |
| `merra2-slv-monthly` | MERRA-2 M2TMNXSLV v5.12.4, monthly single-level | NASA GSFC GES DISC | 10.5067/AP1B0BA5PD2K | heat, skin, humid, vapor, colvapor, ozone, wind |
| `merra2-flx-monthly` | MERRA-2 M2TMNXFLX v5.12.4, monthly surface flux | NASA GSFC GES DISC | 10.5067/0JRLVL8YV2Y4 | rain, rain_dry, rain_wet, seaice |
| `merra2-lnd-monthly` | MERRA-2 M2TMNXLND v5.12.4, monthly land surface | NASA GSFC GES DISC | 10.5067/8S35XF81C28F | soil, topsoil, evap, snow |
| `merra2-slv-daily` | MERRA-2 M2SDNXSLV v5.12.4, daily statistics | NASA GSFC GES DISC | 10.5067/9SC1VNTWGWV3 | tmax, tmin, hottest, trange, frost |
| `merra2-paper` | Gelaro, R., et al. (2017). The Modern-Era Retrospective Analysis for Research and Applications, Version 2 (MERRA-2). *Journal of Climate*, 30, 5419–5454. | NASA GMAO | 10.1175/JCLI-D-16-0758.1 | Method reference for all MERRA-2 values |
| `ceres-syn1deg` | CERES SYN1deg Month, Terra-Aqua-NOAA20, Edition 4B | NASA LaRC ASDC | 10.5067/TERRA-AQUA-NOAA20/CERES/SYN1DEGMONTH_L3.004B | sun, cloud, aerosol, albedo, uv |
| `ceres-paper` | Doelling, D. R., et al. (2013). Geostationary enhanced temporal interpolation for CERES flux products. *J. Atmos. Oceanic Technol.*, 30, 1072–1090. | NASA LaRC | 10.1175/JTECH-D-12-00136.1 | Method reference for CERES SYN1deg |
| `imerg-monthly` | GPM IMERG Final Precipitation L3 1 month 0.1° V07 (GPM_3IMERGM) | NASA/JAXA, NASA GSFC GES DISC | 10.5067/GPM/IMERG/3B-MONTH/07 | rain_sat |
| `modis-mcd14ml` | MODIS Collection 6.1 active fire detections MCD14ML, distributed by NASA FIRMS | NASA | 10.5067/FIRMS/MODIS/MCD14ML | fire |
| `modis-fire-paper` | Giglio, L., Schroeder, W., Justice, C. O. (2016). The collection 6 MODIS active fire detection algorithm and fire products. *Remote Sensing of Environment*, 178, 31–41. | NASA | 10.1016/j.rse.2016.02.054 | Method reference for fire |
| `gpw-natid` | GPWv4.11 National Identifier Grid, Revision 11 | NASA SEDAC (CIESIN) | 10.7927/H4TD9VDP | Which country each grid cell belongs to, and the country shapes on the map |
| `gpw-adm-points` | GPWv4.11 Administrative Unit Center Points with Population Estimates, Revision 11 | NASA SEDAC (CIESIN) | 10.7927/H4BC3WMT | Place-name search, province and capital points |
| `gibs-bluemarble` | NASA GIBS, layer `BlueMarble_ShadedRelief_Bathymetry` | NASA ESDIS | none | Map background imagery |

Use the reference text each provider asks for:

- **NASA POWER.** "The data was obtained from the National Aeronautics and Space Administration (NASA) Langley Research Center (LaRC) Prediction of Worldwide Energy Resource (POWER) Project funded through the NASA Earth Science Division." Add the service version and the access date. This is the text on https://power.larc.nasa.gov/docs/referencing/.
- **NASA GIBS.** "We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS)."

Before submission, confirm two details:

- The variable-to-collection mapping above. POWER derives some values, such as RH2M and FROST_DAYS, from MERRA-2 fields. POWER's parameter documentation names the source of each one.
- The CERES edition that POWER serves. The table cites Edition 4B, which is the current CMR record. Cite the edition POWER documents if it differs.

## What this rule replaced

| Was | Not NASA | Now |
|---|---|---|
| Country borders from Natural Earth 50m | Natural Earth is a public-domain cartography project | `gpw-natid`: each 1° cell belongs to the country that owns most of its land pixels. A country owning no majority cell gets the cell that holds most of its pixels. The map draws each country as the mosaic of its cells. |
| Place search through Open-Meteo and OpenStreetMap Nominatim | Third-party geocoders | `gpw-adm-points`: a local gazetteer of admin-unit names and centre points, built once. Typed "lat, lon" input and map clicks still work. |
| Rank-group coordinates from a hand-made `places.json` | No stated source | Group members are gazetteer entries, named in `tools/catalog.src.json`. The build fails on a name it cannot find. |
| OpenStreetMap map tiles | Third-party basemap | `gibs-bluemarble` tiles from `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg` |

The 43 named places keep their bounding boxes. The team drew those boxes, so they are definitions and not data. The **About the data** page says so.

Synthetic data (`EB_OFFLINE=1`) is never data. The server refuses to start with it when `VERCEL` is set. Every synthetic result carries the banner.

## Checks

- `tests/test_sources.py`:
  - every variable's `source` ids exist in the registry
  - every registry entry's `agency` is in `ALLOWED_AGENCIES`
  - every entry has a `citation`, and either a `doi` or an `id` in the two named acknowledgement texts
  - every `Result.sources` entry produced by the demo questions is a registry entry
  - no URL in `earthbuddy/` or `web/` points outside an allowed host: `*.nasa.gov`, `nasa-power.s3.amazonaws.com`, `api.anthropic.com`, and the app's own origin
- `tools/check_refs.py` resolves every DOI through `https://doi.org/api/handles/<doi>` and fails on any response other than 200. Run it before each submission. It needs a network connection, so it is not part of `pytest`.

## Screens

- The result's **Sources** panel shows the citation and a DOI link for each source, plus "via NASA POWER" and the access date.
- An **About the data** page lists every registry entry, the place-box note, and the AI-use statement.
- The README has a **Data and references** section generated from `data/sources.json` by `tools/check_refs.py --markdown`.

## Acceptance

- `pytest tests/test_sources.py` passes.
- `python tools/check_refs.py` reports every DOI as resolved.
- A search for "naturalearth", "nominatim", "open-meteo", and "openstreetmap" finds nothing in the code, data, or web files.
