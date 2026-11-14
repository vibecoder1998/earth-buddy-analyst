# Earth Buddy

Earth Buddy answers questions about how the Earth is changing at a place, using NASA data. You type a claim, such as "Cambodia is getting hotter and drier", or a question, such as "Which Southeast Asian capital is warming fastest?". The app returns a verdict, the numbers behind it, a chart, the method, and the NASA sources.

Code makes every number and every verdict. A language model reads the sentence and writes plain-language text from the results, and nothing more. With AI switched off, the app still answers every question.

Built for the NASA Space Apps Challenge 2026, Phnom Penh, challenge "Be An Earth System Trend Detective".

## Status

This repository holds the build spec. It holds no code yet. The spec merges two earlier prototypes, the claim desk and the Earth Buddy analyst, into one app.

## Build it with a coding agent

1. Clone the repository.

   ```
   git clone https://github.com/vibecoder1998/earth-buddy-analyst
   cd earth-buddy-analyst
   ```

2. Open a Claude Code session in the folder. `CLAUDE.md` loads automatically and points the agent at `SPEC.md`.
3. Tell the agent: "Read SPEC.md and build row 1."
4. When the row's acceptance checks pass, ask for the next row.

The build-order table in `SPEC.md` gives each feature a priority and an estimate. P0 is the demo, about 19 hours of agent work.

## What is in the spec

| File | Contents |
|---|---|
| `SPEC.md` | The contract: the one rule, the architecture, the shared types, the HTTP API, the build order, what is cut and why, and the definition of done |
| `CLAUDE.md` | Standing instructions for a coding agent |
| `docs/00-foundation.md` | Skeleton, configuration, and the first deploy |
| `docs/01-catalog-and-data.md` | 27 NASA variables, 248 countries, 43 places, and how the data is built |
| `docs/02-series.md` | Precomputed region series, live NASA POWER points, and the cache |
| `docs/03-stats.md` | Trend test, change point, false-discovery check, and claim verdicts |
| `docs/04-reader.md` | Sentence to typed question, by keywords or by AI |
| `docs/05-claim-check.md` | Test a claim and build the evidence board |
| `docs/06-trend.md` | How one variable is changing at one place |
| `docs/07-where-map.md` | Where around a place the change is |
| `docs/08-baseline.md` | Recent years against a reference period |
| `docs/09-rank.md` | Which places lead, and when they cannot be told apart |
| `docs/10-extremes.md` | Record years, unusual years, and monthly changes |
| `docs/11-relate.md` | Whether two variables move together |
| `docs/12-scan-and-audit.md` | Every variable for one region, and claims frozen before the data existed |
| `docs/13-explainer.md` | Plain-language text with every number checked |
| `docs/14-web-ui.md` | Ask, card, and result screens, charts, map, and share links |
| `docs/15-i18n.md` | Khmer and English |
| `docs/16-data-sources.md` | The NASA-only data rule, every reference with its DOI, and the checks that enforce it |
| `docs/screenshots/` | Screens of the Earth Buddy analyst prototype, as a reference for the visual design |

## Stack

Python 3.12 with FastAPI, numpy, scipy, statsmodels, and pymannkendall. Vanilla JavaScript with no build step, MapLibre GL for the map, and SVG charts. SQLite caches NASA responses. It deploys to Vercel.

## Data and references

All data comes from NASA or its partner agencies. The app needs no login. The build downloads two NASA SEDAC files with an Earthdata login. The SEDAC National Identifier Grid sets the country count at 248. Measurements, country borders, place names, and map imagery are all included. Tests fail on any data source outside this list. `docs/16-data-sources.md` has the full rule.

- Global Modeling and Assimilation Office (GMAO) (2015). MERRA-2 tavgM_2d_slv_Nx, monthly single-level diagnostics, V5.12.4. NASA GES DISC. https://doi.org/10.5067/AP1B0BA5PD2K
- GMAO (2015). MERRA-2 tavgM_2d_flx_Nx, monthly surface flux diagnostics, V5.12.4. NASA GES DISC. https://doi.org/10.5067/0JRLVL8YV2Y4
- GMAO (2015). MERRA-2 tavgM_2d_lnd_Nx, monthly land surface diagnostics, V5.12.4. NASA GES DISC. https://doi.org/10.5067/8S35XF81C28F
- GMAO (2015). MERRA-2 statD_2d_slv_Nx, daily aggregated statistics, V5.12.4. NASA GES DISC. https://doi.org/10.5067/9SC1VNTWGWV3
- Gelaro, R., et al. (2017). The Modern-Era Retrospective Analysis for Research and Applications, Version 2 (MERRA-2). *Journal of Climate*, 30, 5419–5454. https://doi.org/10.1175/JCLI-D-16-0758.1
- NASA/LARC/SD/ASDC. CERES and GEO-Enhanced TOA, Within-Atmosphere and Surface Fluxes, Clouds and Aerosols Monthly Terra-Aqua-NOAA20 Edition 4B (SYN1deg). https://doi.org/10.5067/TERRA-AQUA-NOAA20/CERES/SYN1DEGMONTH_L3.004B
- Doelling, D. R., et al. (2013). Geostationary enhanced temporal interpolation for CERES flux products. *Journal of Atmospheric and Oceanic Technology*, 30, 1072–1090. https://doi.org/10.1175/JTECH-D-12-00136.1
- GPM IMERG Final Precipitation L3 1 month 0.1 degree x 0.1 degree V07 (GPM_3IMERGM). NASA and JAXA, NASA GES DISC. https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07
- MODIS Collection 6.1 active fire detections (MCD14ML), distributed by NASA FIRMS. https://doi.org/10.5067/FIRMS/MODIS/MCD14ML
- Giglio, L., Schroeder, W., Justice, C. O. (2016). The collection 6 MODIS active fire detection algorithm and fire products. *Remote Sensing of Environment*, 178, 31–41. https://doi.org/10.1016/j.rse.2016.02.054
- CIESIN, Columbia University. Gridded Population of the World, Version 4 (GPWv4): National Identifier Grid, Revision 11. NASA SEDAC. https://doi.org/10.7927/H4TD9VDP
- CIESIN, Columbia University. Gridded Population of the World, Version 4 (GPWv4): Administrative Unit Center Points with Population Estimates, Revision 11. NASA SEDAC. https://doi.org/10.7927/H4BC3WMT
- The data was obtained from the National Aeronautics and Space Administration (NASA) Langley Research Center (LaRC) Prediction of Worldwide Energy Resource (POWER) Project funded through the NASA Earth Science Division.
- We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS).
- Analyses and visualizations used in this app were produced with the Giovanni online data system, developed and maintained by the NASA GES DISC. Giovanni area averages for Cambodia check our heat, soil, rain, and satellite rain series (`docs/16-data-sources.md`, "Giovanni cross-check").

Every DOI above resolved through doi.org on 14 Nov 2026. Once the app is built, `tools/check_refs.py --markdown` regenerates this list from `data/sources.json`.

## Claims frozen before the data

`data/audit.json` holds 8 claims that the team wrote and committed on 10 Nov 2026, before the 27-variable series existed. The ask screen shows each claim with its live verdict, and `GET /api/audit` returns them. Nobody edits these claims to change a verdict, and nobody adds a claim after seeing results.

The claim desk recorded 7 of 8 claims as **not supported**, and `arctic-ice` as **a jump, not a trend** (`docs/12-scan-and-audit.md`). Under the current statistics every verdict is the same.

| Claim | Claim desk | Now | Numbers now, 2001 to 2024 |
|---|---|---|---|
| `khm-hotter` | Not supported | Not supported | heat −0.13 °C per decade, p 0.623 |
| `khm-nights` | Not supported | Not supported | tmin 0.11 °C per decade, p 0.474 |
| `khm-dry-season` | Not supported | Not supported | rain_dry 3.2 % per decade, p 0.808; soil 3.2 % per decade, p 0.437 |
| `pp-air` | Not supported | Not supported | aerosol 0 AOD per decade, p 0.907 |
| `delta-drying` | Not supported | Not supported | rain 19 % per decade, p 0.254; soil 2.8 % per decade, p 0.174 |
| `sahara-hotter` | Not supported | Not supported | heat 0.11 °C per decade, p 0.380; tmax 0.021 °C per decade, p 0.980 |
| `amazon-drying` | Not supported | Not supported | rain −11 % per decade, p 0.115; soil −2.7 % per decade, p 0.151; humid −1.2 % per decade, p 0.151 |
| `arctic-ice` | A jump, not a trend | A jump, not a trend | seaice −0.81 % per decade, p 0.035, jump in 2007 |

Two changes moved the numbers but no verdict:

- **A new trend test.** The claim desk used a one-sided test. The app runs a two-sided Mann-Kendall test that corrects for year-to-year memory (`docs/03-stats.md`). This changes every p-value. It only makes a verdict stricter.
- **Country series rebuilt on NASA SEDAC cells.** The claim desk built its country series from Natural Earth borders. The app rebuilds them from the NASA SEDAC National Identifier Grid. This moved Cambodia's heat from −0.07 °C per decade, p 0.68 (claim desk, `decisions.tsv` row 24) to −0.13 °C per decade, p 0.623. Place series are the claim desk's own files, so their slopes did not change.

## AI use

AI coding assistants helped write this spec. In the app, Claude on Amazon Bedrock (AWS region `ap-southeast-2`) reads a typed sentence into a structured question, and writes explanations. Both are optional and off by default. The model never produces a data value or a verdict. KiriTTS (`api.kiritts.com`) turns a spoken question into text and reads the answer aloud: speech to text and text to speech only. It never supplies a number, a place name, or a source. Without `KIRITTS_API_KEY`, voice is off and typing works the same.
