# Is our data enough for “Be An Earth System Trend Detective”?

Audit of every CSV you provided, against the challenge text on the Space Apps page (14 Nov 2026).
Files read: the 8 Giovanni CSVs and the FIRMS archive + near-real-time CSVs, exactly as downloaded (now in `fire-watch/raw-data/`).
Numbers below are recomputed from those files (`audit_csvs.py` logic; raw outputs in `results/data_readiness_audit.csv` / `.json` and `results/data_readiness_province_trends.csv`).

## Verdict

**Yes, the data is enough to meet the challenge. It is not yet enough to be safe or strong.** Three gaps decide how good the entry is:

1. **“Where is it changing?” is only answerable for fire.** All 8 Giovanni files are one area-average over a single box (102.3–107.6°E, 10.4–14.7°N, which also takes in parts of Thailand and Vietnam). The challenge stresses that a variable can rise in one region and fall in another; one box cannot show that. FIRMS can, because it is point data (see section 5).
2. **The MERRA-2 hydrology/humidity variables share a step around 2016–17 that the satellite rain does not have.** Rain, soil wetness, wet-bulb temperature and aerosol optical depth all show a step after 2016–17 (up for the first three, down for aerosol optical depth). The independent satellite rain (GPM IMERG) shows no trend at all. Several “significant trends” are probably one model step, not climate. The new Rain, soil & heat tab shows this directly (its section 3).
3. **Some claims on the existing Climate Watch tabs are not supported by these CSVs** (section 6). They should be fixed or sourced before judging.

## 1. What the challenge asks

From the challenge page: build a tool that selects Earth-science variables (mission or model), visualises how they change over time, and determines **what** is changing, **where**, **how much**, and whether it is **significant**. The objectives are: (1) identify variables of interest; (2) acquire them for a particular region; (3) build a time series long enough for statistics; (4) report the rate of change and test significance (t-test, Mann–Kendall, or confidence intervals). “A response that does both the visualization and the analysis meets the full scope.” The page adds that trends can be hidden unless the seasonal cycle is removed, and that linear trends are enough.

## 2. The files you provided

| File (in `raw-data/giovanni/`) | What it is | Source type | Unit | Months | Missing | Range |
|---|---|---|---|---|---|---|
| `GPM_3IMERGM_07_precipitation` | Precipitation (GPM IMERG Final) | satellite mission (GPM) | mm/day | 288 of 288 | none | 0.0941 to 17.4 |
| `M2TMNXLND_5_12_4_PRECTOTLAND` | Land precipitation, bias-corrected (MERRA-2) | model reanalysis (MERRA-2) | mm/day | 288 of 288 | none | 0.0179 to 15.3 |
| `M2TMNXLND_5_12_4_GWETROOT` | Root-zone soil wetness (MERRA-2) | model reanalysis (MERRA-2) | fraction 0-1 | 288 of 288 | none | 0.47 to 0.974 |
| `M2TMNXSLV_5_12_4_T2M` | 2 m air temperature (MERRA-2) | model reanalysis (MERRA-2) | deg C | 288 of 288 | none | 23.3 to 32.8 |
| `M2TMNXSLV_5_12_4_T2MWET` | 2 m wet-bulb temperature (MERRA-2) | model reanalysis (MERRA-2) | deg C | 288 of 288 | none | 15.4 to 24.9 |
| `M2TMNXAER_5_12_4_TOTEXTTAU` | Aerosol optical depth, 550 nm (MERRA-2) | model reanalysis (MERRA-2) | unitless | 288 of 288 | none | 0.0894 to 0.68 |
| `M2TMNXAER_5_12_4_BCSMASS` | Black carbon surface mass (MERRA-2) | model reanalysis (MERRA-2) | ug/m3 | 288 of 288 | none | 0.286 to 2.74 |
| `M2TMNXAER_5_12_4_TOTSMASS25` | PM2.5 surface mass (MERRA-2) | model reanalysis (MERRA-2) | ug/m3 | 288 of 288 | none | 7.66 to 39.1 |

**FIRMS** (`fire_archive_M-C61_846286.csv`): 717,185 detections from MODIS on Terra and Aqua, 2001-11-16 to 2026-08-27; Terra starts 2001-11-16, Aqua starts 2002-07-08. 647,193 are real vegetation fires with confidence ≥ 30. All 298 calendar months have detections; in the tested Nov–Apr seasons 2003–2022 detections exist on 3,027 of 3,625 days for Aqua and 3,081 for Terra (a day without a detection can mean no fire or cloud cover). Coordinates span 10.43–14.69°N, 102.31–107.61°E, i.e. the file is already clipped to Cambodia. `fire_nrt_M-C61_846286.csv` (115 rows, 2026-09-04 to 2026-11-14) is a near-real-time extension, too short for trends. The FIRMS archive is reported to start in Nov 2000, so about a year of Terra (Nov 2000 – mid Nov 2001) is not in your download.

Data quality: no missing months, no fill values, no duplicates and plausible ranges in all 8 Giovanni files; FIRMS tables re-derived from the raw file with 0 mismatches (2,495 checks).

## 3. Scorecard against the challenge

| Challenge element | What you have | Verdict |
|---|---|---|
| Identify variables of interest (mission or model; land / ocean / atmosphere) | 9: GPM rain (mission), MERRA-2 land rain, root-zone soil wetness, 2 m temperature, wet-bulb temperature, aerosol optical depth, black carbon, PM2.5 (models), MODIS fire (mission). Covers water cycle, land, atmosphere, fire. No ocean, ice or vegetation index. | **Enough** (ocean/vegetation are optional) |
| Acquire for a particular region | One Cambodia box for Giovanni; FIRMS clipped to Cambodia with 25 provinces | **Enough** for one region |
| Long enough time series | 24 years monthly (288 points) for 8 variables; 20 tested fire seasons (24 available) | **Enough** (Mann–Kendall needs about 10 or more points) |
| Rate of change | Sen slope with 95% confidence interval, and OLS slope with 95% interval | **Enough** |
| Significance test (t-test, Mann–Kendall, confidence interval) | All three are done: yearly Mann–Kendall, seasonal Mann–Kendall on all months, t-test on the OLS slope, both intervals | **Enough** |
| Remove the seasonal cycle | Seasonal Mann–Kendall and month-by-month anomalies are computed | **Enough** |
| “What / how much / significant” | Yes for every variable | **Enough** |
| “Where is it changing?” | Fire: yes, by province. Giovanni: **no** (one box) | **Partial** |
| A tool that lets users select variables | Three tabs with controls: **Fire** (satellite, season range, province view), **Soot & haze** (3 aerosol measures, satellite, season range), **Rain, soil & heat** (5 series, year range). All 8 Giovanni variables and the fire data are selectable, and every tab names its instrument or model | **Enough** (as three tabs, not one selector) |

## 4. What the data actually says

Annual means 2001–2024 for the Giovanni variables (n = 24 years). “Rate” is the Sen slope. Intervals are 95%.

| Variable | Rate per decade | % of mean per decade (95% CI) | Mann–Kendall p (yearly means, n = 24) | Seasonal Mann–Kendall p (288 months) | t-test p (OLS slope) | p after pre-whitening | Hamed–Rao p | Biggest step (Pettitt) | Plain verdict |
|---|---|---|---|---|---|---|---|---|---|
| Precipitation (GPM IMERG Final) | +0.059 mm/day | +1.0% (−5.2 to +6.1) | 0.82 | 0.95 | 0.86 | 0.83 | 0.82 | after 2005 (p = 0.99) | No trend. This is the satellite rain, and it disagrees with the MERRA-2 rain below. |
| Land precipitation, bias-corrected (MERRA-2) | +0.506 mm/day | +11.3% (+0.6 to +19.2) | 0.045 | 0.009 | 0.011 | 0.008 | 0.14 | after 2017 (p = 0.012) | Significant by the plain test and the pre-whitened test, but **not** by Hamed–Rao (p = 0.14); and it is a **step after 2017** that the satellite rain (IMERG) does not show. Treat as a model artefact until proven otherwise. |
| Root-zone soil wetness (MERRA-2) | +0.027 (fraction) | +4.1% (+0.2 to +8.0) | 0.045 | < 0.001 | 0.009 | 0.004 | 0.16 | after 2016 (p = 0.005) | Significant by the plain and pre-whitened tests, **not** by Hamed–Rao (p = 0.16); a **step after 2016** that follows the MERRA-2 rain step. |
| 2 m air temperature (MERRA-2) | −0.012 °C | 0.0% (−1.0 to +1.2) | 0.90 | 0.64 | 0.96 | 0.87 | 0.90 | after 2016 (p = 0.65) | No trend (flat). |
| 2 m wet-bulb temperature (MERRA-2) | +0.506 °C | +2.3% (+1.1 to +3.3) | 0.001 | < 0.001 | < 0.001 | < 0.001 | 0.001 | after 2016 (p = 0.002) | Significant by every test (about +0.5 °C per decade), but again a **step after 2016**. |
| Aerosol optical depth, 550 nm (MERRA-2) | −0.018 (AOD units) | −7.2% (−15.7 to +2.4) | 0.087 | < 0.001 | 0.082 | 0.007 | 0.20 | after 2016 (p = 0.009) | Yearly means: borderline. Seasonal tests: highly significant decline. A real signal is likely, with a step after 2016 too. |
| Black carbon surface mass (MERRA-2) | −0.050 µg/m³ | −6.4% (−11.2 to −2.2) | 0.008 | 0.24 | 0.019 | 0.001 | < 0.001 | after 2008 (p = 0.059) | Yearly means say falling (p = 0.008); the seasonal test says not significant (p = 0.24). **Fragile**: it looks mostly like a single step after 2008. |
| PM2.5 surface mass (MERRA-2) | −0.294 µg/m³ | −1.9% (−6.8 to +2.2) | 0.26 | 0.22 | 0.27 | 0.10 | 0.26 | after 2016 (p = 0.40) | No trend. |
| Fire detections, Aqua (Nov–Apr seasons 2003–2022, n = 20) | −208 detections | −1.1% (−22.3 to +20.6) | 0.92 | n/a (season totals) | 0.70 | n/a | n/a | after 2016 (p = 0.88) | No clear trend. The interval is wide (−22% to +21% per decade), so a real change of that size cannot be ruled out. |
| Fire detections, Terra (Nov–Apr seasons 2003–2022, n = 20) | +1245 detections | +15.1% (−10.6 to +40.5) | 0.23 | n/a (season totals) | 0.24 | n/a | n/a | after 2010 (p = 0.29) | No clear trend. The interval is wide (−11% to +40% per decade), so a real change of that size cannot be ruled out. |

Three cross-checks matter most:
- **Rain, two ways.** GPM IMERG and MERRA-2 land rain correlate well month to month (r = 0.93), but the yearly ratio MERRA-2 ÷ IMERG goes from 0.70 before to 0.94 after a break in 2016 (Pettitt p = 0.003). IMERG has no trend (p = 0.82); MERRA-2 does (plain p = 0.045). The disagreement is in the model series.
- **Correcting for year-to-year memory changes the answer too.** MERRA-2 rain and soil wetness have large lag-1 memory (a step creates it). The pre-whitened test calls them more significant (p = 0.008 and 0.004); the Hamed–Rao correction calls them not significant (p = 0.14 and 0.16). Do not quote one p-value alone for these.
- **Which test you pick changes the answer** for black carbon (yearly p = 0.008, seasonal p = 0.24) and aerosol optical depth (yearly p = 0.087, seasonal p < 0.0001). Report both, and say which one you trust and why.

## 5. “Where is it changing?”: fire by province

Each province's Aqua season counts (2003–2022) tested with Mann–Kendall: 8 of 25 provinces reach p < 0.05 (2 increasing, 6 decreasing); 4 survive a false-discovery filter. Terra: 7 of 23 (5 increasing, 2 decreasing); 1 survives.

- **Aqua:** Stung Treng +36% (p 0.002), Kratie +24% (p 0.048), Kampong Speu −24% (p 0.021), Oddar Meanchey −28% (p 0.016), Kampong Cham −49% (p 0.030), Banteay Meanchey −60% (p < 0.001), Tboung Khmum −65% (p 0.001), Pailin −124% (p < 0.001)

- **Terra:** Kampong Thom +56% (p 0.006), Svay Rieng +43% (p 0.016), Stung Treng +38% (p 0.007), Ratanakiri +35% (p 0.025), Kratie +21% (p 0.023), Banteay Meanchey −28% (p 0.032), Pailin −89% (p < 0.001)

This is exactly the pattern the challenge describes: **fire rising in the north-east (Stung Treng, Kratie) and falling in the west (Pailin, Banteay Meanchey) while the national total shows no trend.** Cautions: provinces are nearest-centre zones, not borders; Aqua and Terra do not agree everywhere; with 25 tests a few p < 0.05 results are expected by chance (that is what the filter handles). The Fire tab now shows this under “4 · Where is it changing?”.

## 6. Claims on the existing Climate Watch tabs that these CSVs do not support

Recomputed from your CSVs. **These numbers have since been corrected in the page**, and claims no CSV can test were labelled (table in `fire-watch/README.md`); the table below records what the tabs said before:

| Their text | What the CSVs give |
|---|---|
| Air tab: 2 m temperature “+0.42 °C/decade”, significant (p < 0.01) | 2 m temperature is **flat**: Sen −0.012 °C/decade, p = 0.90. **Wet-bulb** is significant: +0.51 °C/decade, p = 0.001, but it is a step after 2016 |
| Water 01: GPM rain “+12.2% per decade” | GPM IMERG: +1.0% per decade, p = 0.82 (not significant). The +11–12% matches **MERRA-2** land rain (+11.3%, p = 0.045), the series with the step |
| Water 02: rain ↔ soil r = +0.90 | Not reproduced at monthly level: IMERG vs soil wetness r = +0.68 (+0.28 with the yearly cycle removed); MERRA-2 rain vs soil +0.71 (+0.65). Only MERRA-2 rain vs soil at yearly-mean level is that high (+0.97), but both come from the same model and share the 2016–17 step; with satellite rain it is +0.34 |
| Water 02: soil ↔ heat r = −0.83 | Monthly soil wetness vs 2 m temperature r = −0.57 (−0.50 with the cycle removed); yearly means −0.73 |
| Water 03: soil ↔ fire r = −0.46 | Monthly soil wetness vs Aqua fire (2003–2024) r = −0.61 raw, −0.21 with the cycle removed (their definition of “fire activity” is not given, so a different definition could differ) |
| Water 01: Tonle Sap flood pulse −56.5%, SWOT | No SWOT or river-level CSV was provided, so it cannot be checked |
| The bar charts in the existing tabs | The North-East fire bars were typed-in index numbers (84, 79, 91…), not data; that tab has since been removed. The other tabs' bars were not checked |

## 7. What to add, in priority order

1. **Three sub-region boxes for the same 8 Giovanni variables** (fixes “where” for climate variables and lets you show opposite trends). Suggested boxes (adjust as you like; open while signed in to Earthdata, then download the CSV for each):
   - North-East plateau (105.8, 12.2, 107.6, 14.5): [Giovanni link](https://giovanni.gsfc.nasa.gov/giovanni/#service=ArAvTs&starttime=2001-01-01T00:00:00Z&endtime=2024-12-31T23:59:59Z&bbox=105.8,12.2,107.6,14.5&data=GPM_3IMERGM_07_precipitation(units%3Dmm%2Fday)%2CM2TMNXLND_5_12_4_GWETROOT%2CM2TMNXLND_5_12_4_PRECTOTLAND%2CM2TMNXSLV_5_12_4_T2M(units%3DC)%2CM2TMNXSLV_5_12_4_T2MWET(units%3DC)%2CM2TMNXAER_5_12_4_TOTEXTTAU%2CM2TMNXAER_5_12_4_BCSMASS%2CM2TMNXAER_5_12_4_TOTSMASS25&dataKeyword=BCSMASS&portal=GIOVANNI)
   - Tonle Sap and north-west (102.6, 12.4, 104.6, 14.2): [Giovanni link](https://giovanni.gsfc.nasa.gov/giovanni/#service=ArAvTs&starttime=2001-01-01T00:00:00Z&endtime=2024-12-31T23:59:59Z&bbox=102.6,12.4,104.6,14.2&data=GPM_3IMERGM_07_precipitation(units%3Dmm%2Fday)%2CM2TMNXLND_5_12_4_GWETROOT%2CM2TMNXLND_5_12_4_PRECTOTLAND%2CM2TMNXSLV_5_12_4_T2M(units%3DC)%2CM2TMNXSLV_5_12_4_T2MWET(units%3DC)%2CM2TMNXAER_5_12_4_TOTEXTTAU%2CM2TMNXAER_5_12_4_BCSMASS%2CM2TMNXAER_5_12_4_TOTSMASS25&dataKeyword=BCSMASS&portal=GIOVANNI)
   - South, Mekong plain and coast (103.2, 10.5, 105.9, 11.7): [Giovanni link](https://giovanni.gsfc.nasa.gov/giovanni/#service=ArAvTs&starttime=2001-01-01T00:00:00Z&endtime=2024-12-31T23:59:59Z&bbox=103.2,10.5,105.9,11.7&data=GPM_3IMERGM_07_precipitation(units%3Dmm%2Fday)%2CM2TMNXLND_5_12_4_GWETROOT%2CM2TMNXLND_5_12_4_PRECTOTLAND%2CM2TMNXSLV_5_12_4_T2M(units%3DC)%2CM2TMNXSLV_5_12_4_T2MWET(units%3DC)%2CM2TMNXAER_5_12_4_TOTEXTTAU%2CM2TMNXAER_5_12_4_BCSMASS%2CM2TMNXAER_5_12_4_TOTSMASS25&dataKeyword=BCSMASS&portal=GIOVANNI)
2. **Wire all 8 Giovanni variables into one selectable tool** with the tests above (rate, confidence interval, Mann–Kendall, seasonal Mann–Kendall, step test). Today only the aerosol measures are selectable.
3. **Replace typed-in numbers and unsupported correlations** in the existing tabs with values computed from these CSVs (section 6).
4. **Optional:** a river or water-level series (Hydrology Time Series on the challenge's Resources page) to back the Tonle Sap story; a vegetation index (MODIS NDVI via AppEEARS); the missing FIRMS year (request from 2000-11-01).

## 8. What changed in our tabs because of this audit

- **Fire tab:** added “4 · Where is it changing? Trend by province” (Mann–Kendall + Sen per province for your selected satellite and seasons, with the false-discovery filter, a map and a bar chart). Checked against `pymannkendall` and `statsmodels` from the raw CSV at 7 windows: 779 comparisons, 0 mismatches.
- **Soot & haze tab:** the whole-year card now shows the seasonal Mann–Kendall p next to the yearly one and flags when they disagree; the black carbon card and headline now say “whether it is falling depends on the test” instead of “falling”.
- **New tab, Rain, soil & heat:** the other 5 Giovanni series (GPM IMERG rain; MERRA-2 rain, soil wetness, air temperature, wet-bulb temperature). Pick a series and a range of years; it shows the rate with a 95% interval (Sen), the Mann–Kendall p, a t-test on a straight-line fit, pre-whitened and seasonal tests, the Pettitt step, a fixed robustness card (Hamed–Rao, Yue–Wang), and the MERRA-2 ÷ IMERG rain comparison. Checked against `pymannkendall` and `scipy` from your CSVs at 6 windows for each series: 2,145 comparisons, 0 mismatches.
- **Instrument and model descriptions** now sit next to every variable on all three tabs (section 9).
- **Older tabs corrected.** The numbers in the table of section 6 were replaced with values recomputed from these CSVs, and claims no CSV can test (SWOT flood pulse, wells, rice yields) were labelled as not checked. The `Fire · North-East` tab was removed at the friend's request.
- **Pipeline, clean data and checks.** `fire-watch/pipeline.html` shows raw CSV → clean data → tabs with every row count; `fire-watch/clean-data/` holds tidy CSVs and a data dictionary; 8,510 automated checks, 0 mismatches (`fire-watch/data/verification.json` and `verification_tabs.json`).

## 9. What produces each series (as shown on the tabs)

Product names, titles and grids are copied from the CSV headers; the descriptions follow NASA's own documentation (GES DISC product pages for GPM IMERG V07 and MERRA-2, the MERRA-2 FAQ at NASA GMAO, the MODIS C6.1 fire user guide). Only two of the nine are direct satellite observations.

| Series | Kind | Produced by | Product in your file | Grid |
|---|---|---|---|---|
| GPM IMERG rain | satellite-based estimate | NASA's IMERG merges rain estimates from the passive-microwave sensors of the GPM satellite constellation, calibrated to the GPM Core Observatory's combined radar-and-radiometer product, and adjusts the result to monthly rain-gauge analyses (the Final Run). | `GPM_3IMERGM_07` — Merged satellite-gauge precipitation estimate, Final Run (recommended for general use) | 0.1° (about 10 km) |
| MERRA-2 land rain | model (reanalysis) | MERRA-2 is NASA's atmospheric reanalysis: the GEOS-5 weather model run over many years and constrained by assimilated satellite and surface observations. This is the model's rain over land, “bias corrected” according to the file's title (the file does not say what it was corrected with). No instrument measures it directly. | `M2TMNXLND v5.12.4 · PRECTOTLAND` — Total precipitation land, bias corrected | 0.5° × 0.625° (about 55 × 70 km) |
| Root-zone soil wetness | model (land-surface model) | How full the top 100 cm of soil is, from 0 (dry) to 1 (saturated), computed by the Catchment land-surface model inside MERRA-2. Nothing in these files measures it directly. | `M2TMNXLND v5.12.4 · GWETROOT` — Root zone soil wetness | 0.5° × 0.625° (about 55 × 70 km) |
| 2 m air temperature | model (reanalysis) | Air temperature two metres above the ground from the MERRA-2 reanalysis: a model constrained by assimilated observations, not a thermometer record. | `M2TMNXSLV v5.12.4 · T2M` — 2-meter air temperature | 0.5° × 0.625° (about 55 × 70 km) |
| 2 m wet-bulb temperature | model (reanalysis) | The temperature a wet thermometer would read: it combines heat and humidity, so it tracks heat stress better than air temperature alone. Computed by MERRA-2. | `M2TMNXSLV v5.12.4 · T2MWET` — 2-meter wet bulb temperature | 0.5° × 0.625° (about 55 × 70 km) |
| Black carbon surface mass | model (reanalysis, aerosol module) | Produced by the GOCART aerosol module inside MERRA-2's GEOS-5 model. Satellite aerosol optical depth (MODIS, AVHRR, MISR) and AERONET ground stations constrain the total aerosol; the split into black carbon and other types comes from the model, so black carbon is not measured directly. | `M2TMNXAER v5.12.4 · BCSMASS` — Black Carbon Surface Mass Concentration | 0.5° × 0.625° (about 55 × 70 km) |
| PM2.5 surface mass | model (reanalysis, aerosol module) | The model's total mass of aerosol particles smaller than 2.5 micrometres at the surface, all types together. Observations constrain total aerosol optical depth, not PM2.5 itself. | `M2TMNXAER v5.12.4 · TOTSMASS25` — Total Surface Mass Concentration - PM 2.5 | 0.5° × 0.625° (about 55 × 70 km) |
| Aerosol optical depth, 550 nm | model, constrained by satellite and ground observations | How much light the aerosol in the whole air column blocks at 550 nm. This is the aerosol field MERRA-2 is directly constrained to match (satellite MODIS, AVHRR, MISR and AERONET observations), so it is the most observation-based of the three. | `M2TMNXAER v5.12.4 · TOTEXTTAU` — Total Aerosol Extinction AOT 550 nm | 0.5° × 0.625° (about 55 × 70 km) |
| Fire detections (hotspots) | direct satellite observation | MODIS (Moderate Resolution Imaging Spectroradiometer) on NASA's Terra and Aqua satellites flags 1 km pixels that are burning at the moment of overpass under relatively clear skies; Terra passes in the morning and Aqua in the early afternoon (about 10:30 and 13:30 local time). Collection 6.1 changed the calibration of the input imagery, not the detection logic. | `MCD14ML` Collection 6.1 (FIRMS archive) | 1 km pixels |

Things the documentation did not let us state, so the tabs do not: exactly which datasets MERRA-2's “bias corrected” land rain is corrected with; which input change causes the 2016–17 step.
