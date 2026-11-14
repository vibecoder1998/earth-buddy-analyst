# Fire Watch Cambodia (add-on)

This folder adds three new tabs to Climate Watch Cambodia, **one for fire, one for soot and haze, one for rain, soil and heat**, so the topics are not mixed:

| Tab | What it is about | Data |
|---|---|---|
| `🔥 Fire · NASA FIRMS` | fire and burning only: trend, when, where (map, regions, provinces) | NASA FIRMS, MODIS Collection 6.1 (your raw CSV) |
| `🌧️ Rain, soil & heat` | the other five Giovanni series: GPM IMERG rain (a satellite-based estimate) and four MERRA-2 model fields (rain, root-zone soil wetness, 2 m air temperature, wet-bulb temperature). Rate with a 95% interval, Mann–Kendall, t-test, pre-whitened and seasonal tests, the Pettitt step, a robustness card, and a comparison of the two rain records | the repo's own Giovanni files (`GPM_3IMERGM`, `PRECTOTLAND`, `GWETROOT`, `T2M`, `T2MWET`) |
| `🌫️ Soot & haze` | smoke-type aerosol only, with a **Measure** switch: black carbon (soot), PM2.5, or aerosol optical depth (haze): over time, through the year, trend, and whether each follows fire | MERRA-2 BCSMASS, TOTSMASS25 and TOTEXTTAU (the repo's own Giovanni files) + the FIRMS fire counts for the comparison |

Both sit next to their existing tabs, which are unchanged. Each new tab has their four cards (what is happening, is it unusual, what comes next, what to do) and, **below the cards, an interactive
panel**: pick Aqua, Terra or **Aqua + Terra** for the fire counts, drag two **sliders** for the first and last fire season, and everything in that panel recomputes.
There is also an optional standalone copy of the fire panel, `fire-watch/fire-watch-cambodia.html` (fire only). Delete it if you only want the tabs.

## Open it

Open `climate-watch-cambodia.html`, go to **2 · Analysis**, and click `🔥 Fire · NASA FIRMS`, `🌫️ Soot & haze` or `🌧️ Rain, soil & heat` in the row of case buttons. Scroll down past the four cards.
(Serve the repo with `python -m http.server 8792` and visit `http://127.0.0.1:8792/climate-watch-cambodia.html`; Climate Watch itself loads Tailwind from a CDN, so it needs internet.)
A panel only shows while its own tab is selected. The standalone copy is self-contained: no CDN, no fonts, no network calls; its only links off the page are three DOIs.

## From raw CSV to the tabs: pipeline, clean data and checks

Open **`fire-watch/pipeline.html`** (self-contained, no network) for the one-page account you can show someone: the raw files as downloaded, what was checked in them, every cleaning rule with its row counts, raw versus clean, the clean files, and every check with its count.

| What | Where |
|---|---|
| The raw CSVs, exactly as downloaded, with checksums (the 57 MB FIRMS archive gzipped) | `raw-data/` and its `README.md`, packaged by `tools/package_raw.py` |
| Audit report and scorecard against the challenge | `docs/DATA_READINESS.md` (with `docs/data_readiness_*.csv` and `.json`) |
| Audit of the raw CSVs, and the export of the clean data | `tools/audit_raw.py` → `data/pipeline_audit.json`, `clean-data/` |
| Clean data (tidy tables; `DATA_DICTIONARY.md` says what each column is) | `clean-data/giovanni_cambodia_box_monthly_clean.csv`, `fire_month_counts.csv`, `fire_season_counts.csv`, `fire_province_season.csv` |
| The one-page account | `pipeline.html`, built by `tools/build_pipeline_page.py` from the audit and verification files |
| Independent check of the tabs | `tools/verify/make_expected.py` (reference numbers from the raw CSVs) and `tools/verify/browser_check.js` (compares them with each tab's own JavaScript) → `data/verification_tabs.json` |
| Re-derivation of the fire tables from the raw file | `build_fire_watch.py verify` → `data/verification.json` |

What the audit found (checked 2026-11-14 on the files you provided): all 8 Giovanni CSVs have 288 of 288 months (2001-01 to 2024-12), 0 fill values, 0 duplicate dates, every value in a plausible range. The FIRMS archive has 717,185 rows (2001-11-16 to 2026-08-27), no empty cells, no duplicate rows and no missing month; cleaning keeps 647,193 (drops 38,346 non-vegetation detections and 31,646 low-confidence ones), of which 629,913 fall in November–April. The repo's `data/giovanni/` copies and the packaged originals in `raw-data/` have the same content (the `data/giovanni/` copies differ only in line endings: git on Windows made them CRLF).

**8,510 automated checks, 0 mismatches:** 2,495 re-counting the clean fire tables from the raw file a second way, and 6,015 comparing the tabs' own JavaScript with numbers recomputed from the raw CSVs by `pymannkendall`, `scipy` and `statsmodels` (Fire 1,491, Province trends 779, Soot & haze 930, Rain, soil & heat 2,815; largest p-value difference 8e-8). Our own statistics code also matches the libraries on 28 series (differences ≤ 1.1e-16).

## The controls (both tabs)

| Control | What it does |
|---|---|
| **Measure** (Soot tab only) | black carbon, PM2.5 or aerosol optical depth (“Haze (AOD)”). Every chart, test and sentence on the tab switches to it |
| **Aqua / Terra / Aqua + Terra** | which satellite's fire detections are counted. “Aqua + Terra” adds the two counts; a fire seen by both is counted twice, so it measures detections, not unique fires (a note says so on screen). On the Soot tab it only changes the fire side of the comparison |
| **Fire seasons from … to …** | two sliders. A season is November–April, labelled by the year it ends; the exact months are shown next to the sliders (for example “Nov 2002 – Apr 2022”). Fire tab 2003–2026; Soot tab 2003–2024 because the black carbon file ends in December 2024. They push each other, so “from” never passes “to” |
| **Region chips** (Fire tab, section 3) | filter the province bars and the map's province rings to one of five regions |
| **Reset** | back to the default view: Aqua, seasons 2003–2022 (the view the four cards show) |

Warnings appear when they matter: too few seasons for the tests, a range that includes seasons after 2022 (not like-for-like), Aqua + Terra (double counting), and 2026 (no September–October yet).

## What is in each tab

**Fire tab**

| Section | What it shows (all recomputed from your selection) |
|---|---|
| Your selection | total detections, per-season mean, busiest and quietest season, trend verdict, busiest region and province, peak month |
| 1 Trend | season counts for Aqua, Terra and (when selected) the sum; your seasons shaded; Sen line; a Mann–Kendall + Sen + lag-1 + Pettitt card for Aqua, Terra and Aqua + Terra in your window; every season is labelled, and a second chart shows **every single month in your file (Nov 2001 – Aug 2026, all years, every year labelled)** with your selection shaded. The monthly totals add up to the raw file's counts (Aqua 447,469, Terra 199,724) |
| 2 When | share of detections by calendar month over your fire years (Nov of the year before to Oct) |
| 3 Where | **fire-density map** (1,595 squares of 0.1°, about 11 km; drawn only from FIRMS points, so it needs no borders; the Tonle Sap gap shows) with the 25 SEDAC province centres coloured by region; **region bars**; **province bars** (all 25, or one region) |
| 4 Where is it changing? | **trend by province**: each province's season counts are tested with Mann–Kendall + Sen slope across your selection, with a Benjamini–Hochberg false-discovery filter (25 provinces, so about one would look significant by chance); a map with trend-coloured province rings and a bar chart of the Sen rate. Needs at least 10 seasons; provinces with fewer than 200 detections are not tested |
| 5 Cross-check (fixed) | the same test on Earth Buddy's `data/v/fire.json` next to our Terra-only and Aqua-only counts; ignores the controls |
| 6 Data check | rows in your file, what was dropped and why, what was kept, exact date coverage, and the verification result |
| 7 What we cannot say | limits, in plain words |

**Soot tab**

| Section | What it shows |
|---|---|
| Your selection | average level of the chosen measure and its seasonal peak, dry-season trend, and the two fire links (season by season, month to month) |
| 1 Over time | the chosen measure monthly for your window, with the November–April fire seasons shaded |
| 2 Through the year and trend | the measure and fire by calendar month; a Mann–Kendall + Sen + Pettitt card for the dry-season values in your window and a fixed whole-year card (2001–2024) |
| 3 Does it follow fire? | season-by-season scatter and Spearman correlations: month to month raw, month to month with the yearly cycle removed, and season by season |
| 4 What we cannot say | limits for the chosen measure (model product, box includes neighbours, what PM2.5 and AOD are, correlation is not cause) |

Default view headline (all computed by code, nothing typed in):

- **Fire:** Aqua, 20 seasons 2003–2022: **−1.1% per decade, Mann–Kendall p = 0.92 → no significant trend**. Terra, same seasons: **+15.1% per decade, p = 0.23 → no significant trend**. The sign flips with the satellite. 91% of detections fall in Dec–Mar; five provinces hold about 52%.
- **Soot (black carbon):** averages 0.79 µg/m³ (2001–2024), peaks in January (1.45) and is lowest in July (0.39); yearly-mean trend −6.4% per decade, p = 0.008, but the seasonal Mann–Kendall test on all 288 months gives p = 0.24 (month-by-month anomalies p = 0.093), so the “decline” is **fragile**: it is mostly a step after 2008 (Pettitt p = 0.059). The card and the page say so. It follows fire: season by season ρ = 0.56 (p = 0.011), month to month with the yearly cycle removed ρ = 0.27 (p < 0.001), but the fire counts show no matching change, so fire alone does not explain the trend. The dry-season (Nov–Apr) soot trend in 2003–2022 is p = 0.048, only just under 0.05; the page says so. Treat trends as a question, not a finding (MERRA-2 is a model product).
- **PM2.5 and haze (AOD):** both follow fire season by season (ρ = 0.75 and 0.71, p < 0.001); their whole-year trends are not significant (PM2.5 −1.9% per decade, p = 0.26; AOD −7.2% per decade, borderline p = 0.087).
- Move the fire slider past 2022 and the verdict can change (for example Aqua + Terra, 2010–2026 reads “borderline, −25.7% per decade, p = 0.06”). The panel warns you why: those seasons are not like-for-like.

## Regions (our own grouping, for readability)

Not an official or NASA classification; shown under the chart too, so you can check it.

| Region | Provinces |
|---|---|
| North-East | Kratie, Mondulkiri, Ratanakiri, Stung Treng |
| North & North-West | Preah Vihear, Oddar Meanchey, Banteay Meanchey, Siem Reap, Battambang, Pailin |
| Tonle Sap & Centre | Kampong Thom, Pursat, Kampong Chhnang, Kampong Cham, Tboung Khmum |
| South-West & Coast | Kampong Speu, Koh Kong, Kampot, Kep, Preah Sihanouk |
| Mekong Plain | Kandal, Phnom Penh, Prey Veng, Svay Rieng, Takeo |

## What the raw file covers (month by month)

The file: `raw-data/firms/fire_archive_M-C61_846286.csv.gz` (unpacks to 717,185 rows).

- **First record 16 Nov 2001 (Terra); last record 27 Aug 2026 (Aqua).** Aqua starts 8 Jul 2002; Terra ends 26 Aug 2026. Every calendar month from Nov 2001 to Aug 2026 has detections (298 months).
- **Used by the pages:** fire seasons from **Nov 2002 – Apr 2003** (the first complete season for both satellites) to **Nov 2025 – Apr 2026** (the last complete one). Default tests: Nov 2002 – Apr 2022.
  Not offered: Nov 2001 – Apr 2002 (Aqua had not started; Terra misses 1–15 Nov 2001) and May–Aug 2026 (they belong to the 2027 season). The monthly chart stops at Oct 2025.
- **Not in the file:** before 16 Nov 2001. NASA training material says MODIS fire records in FIRMS start in November 2000, so about a year of Terra data (Nov 2000 – mid Nov 2001) was not part of this download.
  Aqua cannot go earlier than mid 2002. The companion near-real-time file (115 rows, 4 Sep – 14 Nov 2026) is recorded but not used.
- The black carbon file runs Jan 2001 – Dec 2024.

## Which files the tabs read, and how they were checked

- **FIRMS:** the raw archive and the near-real-time file are packaged in `raw-data/firms/` (the archive gzipped; SHA-256 checksums in `raw-data/SHA256SUMS.txt`).
- **Giovanni:** the eight originals in `raw-data/giovanni/` are **value-for-value identical** to the repo's `data/giovanni/` copies that the Soot tab reads (all 288 months of all 8 files, maximum difference 0; only the line endings differ, so the byte counts differ). The Soot tab uses three of the eight: BCSMASS, TOTSMASS25 (PM2.5) and TOTEXTTAU (aerosol optical depth). The other five (rain, soil wetness, 2 m temperature, wet-bulb temperature) belong to the water and heat tabs.
- The checks below were re-run reading **only** the raw files (the originals as downloaded; `raw-data/` holds the same bytes).


1. **Tables vs raw file.** `build_fire_watch.py verify <folder>` re-reads the raw CSV with a second, independent code path (a plain distance matrix instead of a KD-tree,
   boolean masks instead of groupby) and compares it with the tables the pages embed: every season total, every monthly total, every province-by-season count, every map-row total, and 600
   random map squares recounted from the coordinates. Result: **2,495 checks, 0 failures** (saved in `data/verification.json`). The first run found 6 map squares off by one detection:
   a floating-point rounding error for fires exactly on a 0.1° edge (106.1 / 0.1 is 1060.9999999999998). That is fixed (round before floor) and the check now passes.
2. **Pages vs Python.** Both panels' JavaScript statistics were compared with an independent Python calculation straight from the raw CSV (and scipy for Spearman) at **10 slider settings**
   (Aqua, Terra and Aqua + Terra; short, long and single-season windows, including seasons after 2022). Fire tab: totals, season series, all 25 province counts, region totals, monthly counts,
   Mann–Kendall p, Sen slope, lag-1, Pettitt (1,058 comparisons). Soot tab: the month-to-month and season-by-season Spearman correlations, their p-values and the monthly climatologies (292 comparisons).
   **1,350 comparisons, 0 mismatches**; the largest p-value difference is 6e-8. The province trends were checked against `pymannkendall` and a different false-discovery implementation (`statsmodels`) from the raw CSV at 7 windows (143 province tests, **779 comparisons, 0 mismatches**). The three soot measures were then checked separately at 6 windows each (18 cases: Spearman correlations and p-values, monthly climatologies, dry-season and whole-year trends, Pettitt): **747 comparisons, 0 mismatches**. Those first harnesses were throw-away; on 2026-11-14 the whole comparison was redone with a harness that **is** shipped (`tools/verify/`, 6,015 comparisons across the four tabs, 0 mismatches: see the pipeline section above).
3. **Independent library and formula.** The headline numbers on both cards were recomputed with `pymannkendall` straight from the two folders (Aqua p = 0.9225, Terra p = 0.2300, soot trend −6.4% per decade p = 0.0080), and the soot Pettitt step (after 2008, p = 0.0588) with a second formula (the rank-sum form).
4. **Defaults agree everywhere.** The default view reproduces the four cards above each panel exactly (`data/default_view.json` holds the Python numbers it must match).

## NASA-only choices (matches `docs/16-data-sources.md`)

- Fires: NASA FIRMS, MODIS Collection 6.1 (MCD14ML), DOI 10.5067/FIRMS/MODIS/MCD14ML. Cleaned to real vegetation fires (`type == 0`) with `confidence >= 30`:
  of 717,185 rows, 38,346 are not vegetation fires (`type` 2 or 3) and 31,646 more are below confidence 30, leaving 647,193 (Aqua 447,469; Terra 199,724).
- Black carbon, PM2.5 and aerosol optical depth: the repo's own MERRA-2 `M2TMNXAER` files (BCSMASS, TOTSMASS25, TOTEXTTAU; DOI 10.5067/FH9A0MLJPC7N for the collection), area-averaged over 102.3–107.6°E, 10.4–14.7°N (which includes parts of Thailand and Vietnam). kg/m³ is converted to µg/m³ (×10⁹); AOD is unitless.
- Provinces: the NASA SEDAC GPWv4 centre points already in `data/gazetteer.json` (DOI 10.7927/H4BC3WMT).
- No new source, tile server or geocoder was added. `data/sources.json` was not edited.

### The province approximation

SEDAC gives centre points, not borders, so each fire goes to the **nearest province centre**. We measured how good that is
against real borders (geoBoundaries ADM1, which is OpenStreetMap-derived and not NASA, so it is **not** shipped here; the
numbers are saved in `data/province_method_check.json`, measured for Aqua seasons 2003–2023): 99.7% of fires fall inside a province; 83% land in the same
province either way; province shares rank-correlate at ρ = 0.95; the same five provinces make the top five (the order differs);
the biggest single move is Battambang, 6.9% by border vs 3.3% by centre. **Ranks are solid, exact percentages are ±3–4 points.** Region totals are sums of those province counts, so they carry the same caveat.

## How the numbers were chosen

- Season = November–April, labelled by the year it ends, so one fire season is not split across two calendar years. 97.3% of cleaned detections fall in November–April.
- The default tests use seasons 2003–2022. Seasons after April 2022 can be selected but are **not like-for-like**: the satellites'
  overpass times have been drifting since about 2020–2022, and NASA changed processing version on 2023-01-01.
- Terra and Aqua are tested separately by default (they see Cambodia at different times of day, and Aqua detects roughly twice as many fires); “Aqua + Terra” is an option, with the double-counting note.
- Trend tests are in `tools/stats_tests.py` (Python, used to build the tables and the default numbers) and ported to the pages' JavaScript (`tools/stats_trend.js`, `tools/stats_rank.js`): Mann–Kendall with tie correction, Sen slope,
  lag-1 autocorrelation with trend-free pre-whitening when needed, Pettitt, Spearman. The Python was checked against scipy and `pymannkendall` in our separate `statistics/` work
  (`check_against_libraries.py`) and again here: the Aqua and Terra default p-values (0.9225 and 0.2300) and slopes (−208 and +1,245 detections per decade) match `pymannkendall`.

## Rain, soil & heat tab: what it found, and what it checks

- **Series:** GPM IMERG rain, MERRA-2 land rain, root-zone soil wetness, 2 m air temperature, 2 m wet-bulb temperature (2001–2024, one box). Pick one and a range of years (at least 8).
- **Default view (whole record):** GPM rain +1.0% per decade (p = 0.82, no trend); MERRA-2 rain +11.3% (p = 0.045); soil wetness +4.1% (p = 0.045); air temperature −0.01 °C per decade (p = 0.90, flat); wet-bulb +0.51 °C per decade (p = 0.001).
- **The catch:** the three significant MERRA-2 series all step after 2016–17, and the ratio MERRA-2 ÷ GPM rain goes from 0.70 to 0.94 after 2016 (Pettitt p = 0.003) while the satellite rain has no trend. The tab says so in a warning, in section 3, and on the card.
- **Robustness:** a fixed card shows six p-values for the whole record. MERRA-2 rain and soil wetness are significant under the plain and pre-whitened tests but not under Hamed–Rao (p = 0.14 and 0.16), so they are flagged “not robust”. Wet-bulb is significant under all six (but is a step).
- **Checked:** at 6 windows for each of the 5 series, every number the tab shows (rate, Sen 95% interval, plain / pre-whitened Mann–Kendall p, t-test slope, p and 95% interval, seasonal and anomaly Mann–Kendall p, climatology, ratio and its Pettitt break) was compared with `pymannkendall`, `scipy` and a rank-sum Pettitt reading your Giovanni folder: **2,145 comparisons, 0 mismatches**, largest p-value difference 8e-8.

## What produces each series (instruments and models)

Every tab names what produces its numbers (the “What is measured, and with what” table on the Rain, soil & heat tab; the Sources lists on the other two). Product names, titles and grids are copied from the CSV headers; the descriptions follow NASA's documentation (GES DISC pages for GPM IMERG V07 and MERRA-2, the MERRA-2 FAQ, the MODIS C6.1 fire user guide). In short: fire is a **direct satellite observation** (MODIS on Terra and Aqua); GPM IMERG rain is a **satellite-based estimate** adjusted to rain gauges; everything else is **MERRA-2 model output** (aerosol optical depth is the one MERRA-2 aerosol field that is directly constrained by satellite and ground observations). Not stated because the documentation did not let us: what MERRA-2's “bias corrected” rain is corrected with, and which input change causes the 2016–17 step.

## Is the data enough for the challenge?

See `fire-watch/docs/DATA_READINESS.md` (audit of every CSV: coverage, quality, each method the challenge names, a requirement-by-requirement scorecard, and the instrument table).
Short version: yes for the four objectives; the gaps are one aggregate box for the Giovanni variables (no “where”), the MERRA-2 rain step around 2016–17, and wide uncertainty on the fire trend.

## What we changed in the older tabs, and what we did not

The `🔥 Fire · North-East` tab was **removed** at your friend's request (it only covers those provinces); everything that pointed at it now points at the country-wide `🔥 Fire · NASA FIRMS` tab. For the record, its bars were typed-in index values (`84, 79, 91…`), and its “+6% per decade, p = 0.44” was close to a *whole-Cambodia* test (Earth Buddy's `data/v/fire.json` gives +6.8%, p = 0.50; our all-detections test +7.7%, p = 0.44).

The other older tabs quoted numbers that the supplied CSVs contradict. We **corrected those numbers** (recomputed from the raw CSVs by code, not typed) and **labelled what the CSVs cannot test**. We did not change their stories, actions or hotspots.

| Tab | It said | The CSVs give | What we did |
|---|---|---|---|
| Water 01 | GPM rain +12.2% per decade | +1.0% per decade, p = 0.82 (no trend); the +11–12% is the MERRA-2 model series | replaced; the headline now reads “Satellite rain shows no trend … yet Tonle Sap's flood pulse reportedly shrank” |
| Water 01 | flood pulse −56.5%, break 2017–2018 (Pettitt p < 0.01) | not testable: no SWOT or river file | kept as “reported, not checked”; the bars are labelled “typed in by the team” |
| Water 02 | rain ↔ soil r = +0.90; soil ↔ heat r = −0.83 | monthly r = +0.68 (+0.28 with the yearly cycle removed); −0.57 (−0.50) | replaced on the cards, the home screen, Demo 1 and the Q&A answer |
| Water 02 | bars: wet-season soil wetness | typed-in series | replaced with the real May–October yearly means |
| Water 02 | soil drops below 0.65 in July–August dry breaks | monthly box averages are below 0.65 in 3 of 24 Julys, in no August and in every January–April | added; breaks of 15–20 days cannot be seen in monthly data |
| Water 03 | soil ↔ fire r = −0.46 | Aqua, monthly, 2003–2024: r = −0.61 (−0.21 with the cycle removed) | replaced |
| Water 03 | bars: soot index | typed-in series | replaced with the real yearly mean black carbon |
| Water 04 | arsenic and well chain | nothing in the CSVs tests it | bars labelled “typed in”; the Q&A answer says “not tested with the supplied data” |
| Air | air temperature +0.42 °C per decade, significant, step 2016–17 | air temperature −0.01 °C per decade (p = 0.90) with no step (Pettitt p = 0.65); wet-bulb +0.51 °C per decade (p = 0.001) with a step after 2016 (p = 0.002) | rewritten around wet-bulb; the bars are now the real wet-bulb yearly means |
| Home screen | “Cross-pillar coupling r = +0.90”, and the three signal cards | +0.68, and the numbers above | replaced |

The Khmer text that quoted a changed number (the Water 01 headline and first card, the Air first card) was removed, so those fall back to English; we did not write new Khmer.
Not changed and not tested: the ash → May runoff → fish chain (Water 03), rice-yield effects, and the arsenic and salinity story (Water 04). `data/v/fire.json` behaves like Terra (ρ = 0.95, median ratio 1.01), so quote the satellite when quoting a fire trend.

## What changed in `climate-watch-cambodia.html`

`git diff` shows about 110 deleted lines and about 1,660 added. Almost all of the additions are the two generated blocks (the three tab entries and the three panels, ~300 KB including their data tables); the deletions are the removed North-East tab, the wiring that pointed at it, and the corrected numbers in the older tabs (section above).
Apart from that removal everything is additive or a backwards-compatible default. Checked after the removal: every remaining tab opens and shows its own headline, and our three panels appear only on their own tabs.

| Change | Why |
|---|---|
| New buttons `pill-fire_firms` (🔥 Fire · NASA FIRMS), `pill-soot_bc` (🌫️ Soot & haze) and `pill-water_heat` (🌧️ Rain, soil & heat) where the North-East button used to be | the three new tabs |
| New `fire_firms`, `soot_bc` and `water_heat` entries in `CASES`, between two marker comments (`fire-watch:begin` / `fire-watch:end`) | their content; **generated** by `build_fire_watch.py inject`, so every number comes from code |
| `renderBarChart(values, highlightBreakIdx = -1, startYear = 2001)` and `const year = startYear + idx` | the fire seasons run 2003–2026, not 2001–2024; default is the old behaviour |
| `id="bar-axis-labels"` on the axis row, and 2 lines in `selectCase` that fill it (`c.axisLabels`, default `2001 … 2024`) | the static `2001 2006 2012 2018 2024` labels would be wrong under the fire bars |
| `id="c2-title"` and 1 line in `selectCase` (`c.c2Title`, default `… (2001–2024)`) | same reason for the card-2 heading |
| 3 lines in `generateDeterministicFacts`: when a new tab is active and the question mentions its topic, answer from our numbers | otherwise the Q&A box under our tabs would quote another tab's text |
| New block between `fire-watch:panel:begin` / `fire-watch:panel:end` comments, after the four-card grid: `<div id="fire-watch-panel">`, `<div id="soot-watch-panel">` and `<div id="water-watch-panel">`, each with its own scoped `<style>` (every rule under `.fw`, ids start `fw-` / `sw-` / `ww-`), embedded data tables, and one `<script>` in a function scope exposing only `window.FireWatch` / `SootWatch` / `WaterWatch` | the interactive analyses; **generated** by `build_fire_watch.py inject`, no network calls, no libraries |
| 3 lines in `selectCase`: `window.FireWatch.show(caseId === 'fire_firms')`, `window.SootWatch.show(caseId === 'soot_bc')` and `window.WaterWatch.show(caseId === 'water_heat')` | show (and re-draw) a panel on its own tab, hide it everywhere else |
| **Removed:** the `pill-fire_northeast` button, `CASES.fire_northeast`, and the home-screen “Fire · North-East” card | friend's request |
| Home-screen card A now reads “Is Cambodia burning more?” and opens `fire_firms` (typed-in text; numbers from the default view: Aqua −1.1%, p = 0.92; Terra +15.1%, p = 0.23; 91% in December–March) | keeps a Fire card on the home screen |
| `activeCaseId`, the `DOMContentLoaded` call and the wizard's `fire_smoke` choice now use `fire_firms`; the static headline, badge and source labels in the step-2 header match it | nothing may point at the deleted tab |
| Demo 2 (“Watch Demo 2: Is Cambodia burning more?”) walks through the FIRMS tab; its four sentences are generated with the tab (`CASES.fire_firms.demo`) | the old Demo 2 script was the North-East story |
| The quick question and the generic “fire / burn” answer use the FIRMS finding (`CASES.fire_firms.qa`) | the old answer quoted “24 of 42 detections” |
| The older tabs' wrong numbers corrected and untestable claims labelled (table in the section above), including the home-screen strip, Demo 1 and the Q&A answers | the CSVs contradict them |
| The wizard's “North-East Forests” location keeps its place but loses the “24/42 detections, p = 0.44” figures; the “why rank tests” blurb now quotes the Aqua FIRMS p = 0.92 | those figures belonged to the deleted tab |

To undo it all: `git checkout climate-watch-cambodia.html` (nothing is committed, so this also brings the North-East tab back). To bring back only the North-East tab, copy its pieces out of `git show HEAD:climate-watch-cambodia.html`.
The new tabs have no Khmer text yet; with `ខ្មែរ` selected they fall back to English.

## Rebuild

The pages need nothing to *open*. To regenerate them you need `numpy`, `scipy` and `pandas` (pandas arrives with `statsmodels`, already in `requirements.txt`).

```bash
# 1. tables (needs the FIRMS archive CSV: unpack it first with `gunzip -k fire-watch/raw-data/firms/fire_archive_M-C61_846286.csv.gz`)
python fire-watch/tools/build_fire_watch.py tables <folder containing fire_archive_*.csv>

# 2. check them against the raw CSV a second, independent way (writes data/verification.json)
python fire-watch/tools/build_fire_watch.py verify <folder containing fire_archive_*.csv>

# 2b. audit the raw CSVs and export the clean data (also needs the Giovanni folder; writes data/pipeline_audit.json and clean-data/)
python fire-watch/tools/audit_raw.py --firms <FIRMS folder> --giovanni <Giovanni folder>

# 3. pages + panels (needs only fire-watch/data and the repo's own data/)
python fire-watch/tools/build_fire_watch.py page

# 4. refresh the two marked blocks (the tab entries and the panels) inside climate-watch-cambodia.html
python fire-watch/tools/build_fire_watch.py inject

# 5. independent check of the tabs: make the reference numbers from the raw CSVs, then run tools/verify/browser_check.js in the page's console (see tools/verify/make_expected.py)
python fire-watch/tools/verify/make_expected.py fire-watch/data <FIRMS folder> <Giovanni folder>

# 6. the one-page pipeline account
python fire-watch/tools/build_pipeline_page.py
```

The `tables`, `verify` and `page` stages write only inside `fire-watch/`. The `inject` stage rewrites only the text between the `fire-watch:` marker comments
(two pairs) in `climate-watch-cambodia.html`; running it twice changes nothing.
Sources: `tools/panel_template.html` (fire panel), `tools/soot_template.html` (soot panel), `tools/panel.css`, `tools/stats_trend.js`, `tools/stats_rank.js` (shared), `tools/page_template.html` (standalone wrapper).
Generated: `fire-watch-cambodia.html`, `data/fire_panel.html` (what `inject` pastes in: both panels), `data/fire_firms_case.js` (both tab entries), `data/default_view.json`.
Tables: `fire_month_counts.csv`, `fire_season_counts.csv`, `fire_province_season.csv`, `fire_cells_by_season.json` (the map: per satellite and season, one byte per 0.1° square),
`raw_audit.json` (row counts and coverage) and `verification.json`.

## Not here on purpose

Our separate 10-tab Streamlit dashboard (province polygons, NOAA station, extra Giovanni variables, Docker packaging) is **not** part of this add-on and is not in this repo: it uses non-NASA pieces (OpenStreetMap-derived borders, map tiles, NOAA GHCN) that
this repo's rules do not allow.

## Tests

No Python code of the repo changed, and `climate-watch-cambodia.html` and `fire-watch/` are outside the paths `tests/test_sources.py` scans
(`earthbuddy`, `web`, and `data`/`tools` for removed providers), so the existing `pytest` suite should be unaffected. It could not be run here (the `anthropic` package that its `conftest.py` imports is not installed in this environment), so run `pytest` before merging.
p-values below 0.1 are shown with three decimals, so 0.048 is not rounded to “0.05” next to the word “decreasing”.
In a browser: eight case buttons; the fire tab renders its 24 bars, six province rows, cascade and actions, and below them the fire panel; the soot tab renders its 24 yearly bars and its panel;
each panel is hidden on every other tab and redraws when you come back; every control works (satellite switch, both sliders including the push rule, region chips, Reset) and `compute()` does not move the sliders;
the Q&A box answers from our numbers only while the matching tab is active; at phone width the panels collapse to one column with no sideways overflow. The only console errors are the two 404s per page load that were already there
(`Data/gpm_rain.png` and `Data/gwetroot_soil.png`, a capital-`D` path; the files are in `data/giovanni/`).
The standalone copy makes no network request. Its only URLs are three `doi.org` links and the SVG namespace string `http://www.w3.org/2000/svg`, which is an identifier, never fetched.
