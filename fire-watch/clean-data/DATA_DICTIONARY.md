# Clean data: what each file is

Everything here is made from the raw NASA files by `fire-watch/tools/audit_raw.py` and `fire-watch/tools/build_fire_watch.py`. The raw files are never edited.

## `giovanni_cambodia_box_monthly_clean.csv`

One row per month, January 2001 to December 2024 (288 rows), one column per NASA Giovanni series. Every series is an **area average over one box, 102.3–107.6°E, 10.4–14.7°N** (Cambodia plus parts of Thailand, Laos, Vietnam and the Gulf of Thailand). The grid cells actually used span 102.35,10.45,107.55,14.65.

Cleaning applied: the header lines are skipped; any value of 1e10 or more is a Giovanni fill value and would be dropped (0 were found); each timestamp becomes the first day of its month; units are converted as shown. No value was changed in any other way: no smoothing, interpolation or gap filling.

| Column | Unit | Conversion from the raw file | What it is | Produced by |
|---|---|---|---|---|
| `imerg_precip_mm_day` | mm/day | none | Rain | GPM IMERG v07 Final Run (satellite-based estimate, adjusted to rain gauges) |
| `merra2_precip_land_mm_day` | mm/day | × 86400 | Rain over land (bias corrected) | MERRA-2 M2TMNXLND v5.12.4 (model reanalysis); file is kg m-2 s-1, x86400 |
| `root_zone_soil_wetness` | fraction 0-1 | none | Root-zone soil wetness | MERRA-2 M2TMNXLND v5.12.4 (Catchment land model) |
| `t2m_c` | deg C | none | 2 m air temperature | MERRA-2 M2TMNXSLV v5.12.4 (model reanalysis) |
| `t2m_wetbulb_c` | deg C | none | 2 m wet-bulb temperature | MERRA-2 M2TMNXSLV v5.12.4 (model reanalysis) |
| `aod_550nm` | unitless | none | Aerosol optical depth, 550 nm | MERRA-2 M2TMNXAER v5.12.4 (constrained by satellite and AERONET observations) |
| `black_carbon_ugm3` | ug/m3 | × 1e+09 | Black carbon surface mass | MERRA-2 M2TMNXAER v5.12.4 (GOCART aerosol module); file is kg m-3, x1e9 |
| `pm25_ugm3` | ug/m3 | × 1e+09 | PM2.5 surface mass | MERRA-2 M2TMNXAER v5.12.4 (GOCART aerosol module); file is kg m-3, x1e9 |

## `fire_month_counts.csv`

Cleaned MODIS fire detections per calendar month and satellite. Columns: `year`, `month`, `satellite` (Aqua or Terra), `detections`.

## `fire_season_counts.csv`

Detections per November–April fire season (labelled by the year it ends: season 2020 = November 2019 to April 2020). Columns: `season`, `aqua`, `terra`.

## `fire_province_season.csv`

The same detections assigned to the **nearest** NASA SEDAC GPWv4 province centre point. This is an approximation (centre points, not borders): treat province shares as ±3–4 points. Columns: `satellite`, `province`, `season`, `detections`.

## How a fire detection becomes a clean row

1. Start from the FIRMS archive `fire_archive_M-C61_846286.csv` (717,185 rows, 2001-11-16 to 2026-08-27, MODIS Collection 6.1 on Terra and Aqua).
2. Keep `type == 0` (a vegetation fire): drops 38,346 rows (volcanoes, other static sources, offshore).
3. Keep `confidence >= 30`: drops 31,646 rows.
4. That leaves 647,193 clean detections. 629,913 of them (97.3%) fall in November–April and are the ones the trend tests count.
5. Count per satellite and season, per satellite and month, and per nearest province centre.

The near-real-time file in the same download is recorded but never used.
