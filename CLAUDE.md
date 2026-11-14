# Earth Buddy

Read `SPEC.md` before any work. It is the contract. Each feature's spec is in `docs/`.

- Build in the order of the table in `SPEC.md`. Finish each row's acceptance checks before the next row.
- Code makes every number and verdict. A language model only reads the sentence and writes text from `facts`.
- Every statistical constant lives in `earthbuddy/stats.py` under `T`. Do not repeat a threshold anywhere else.
- A new question kind adds one `ANALYSES` entry and one doc. It adds no `if kind ==` branch in routes or screens.
- Run `pytest` before you say a step is done. Run `python run.py` and try the demo sentences before you say a screen works.
- The prototypes in `~/earth-buddy` and `~/earth-buddy/earth-buddy-analyst` are reference code. Read them for the logic. Copy only the data files that `SPEC.md` lists.

## Data sources

Take data only from the sources below. Before you add any other source, ask the user. This rule covers new connectors, datasets, fixtures, and links in the `sources` field.

Already in use by `SPEC.md`:
- NASA POWER: https://power.larc.nasa.gov
- Nominatim and Open-Meteo geocoding. Use them to look up places only, never to get Earth data.

NASA Space Apps 2026 "Earth System Trend Detective" resources (https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/?tab=resources):
- Giovanni: https://giovanni.gsfc.nasa.gov/
- Hydrology Time Series: https://disc.gsfc.nasa.gov/information/tools?title=Hydrology%20Time%20Series
- AppEEARS: https://appeears.earthdatacloud.nasa.gov/
- NOAA Climate Data Online: https://www.ncei.noaa.gov/cdo-web/
- SeaWiFS time-series paper (method reference): https://ntrs.nasa.gov/api/citations/20090042747/downloads/20090042747.pdf
- KNMI Climate Explorer: https://climexp.knmi.nl/
- Trend tests article (method reference): https://medium.com/@snp.kriss/statistical-test-methods-to-detect-trends-in-time-series-data-b361a0ec530b
- Statistical significance guide (method reference): https://www.statsig.com/perspectives/a-comprehensive-guide-to-statistical-significance
- CSA RADARSAT Constellation Mission data: https://donnees-data.asc-csa.gc.ca/en/dataset/rcm
- Geo.ca: http://geo.ca/
- CSA SWOT mission: https://www.asc-csa.gc.ca/eng/satellites/swot/
- CSA ecosystem monitoring: https://www.asc-csa.gc.ca/eng/satellites/everyday-lives/monitoring-and-protecting-our-ecosystems-from-space.asp
- CSA SAR Python tutorial: https://github.com/asc-csa/Synthetic_Aperture_Radar_Tutorial

Follow each non-U.S. Government site's own data-use terms.
