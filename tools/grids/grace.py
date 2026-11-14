"""Total water storage: JPL GRACE/GRACE-FO mascon RL06.3Mv04 CRI -> yearly 1° grid (tools/grids/BRIEF.md).

  .venv/bin/python tools/grids/grace.py            # download, write tools/cache/grids/groundwater.f32
  .venv/bin/python tools/grids/grace.py --check

PO.DAAC serves the whole record as one ~46 MB netCDF. It is downloaded once (to .part, then renamed).
Value = lwe_thickness (cm) x the CRI scale_factor, land_mask == 1 only, minus each calendar month's 2004-2009 mean
(per pixel), then the mean of the year's months (needs MIN_MONTHS).
The scale factors come from a land-hydrology model (CLM) and are meant for land water, not glacier ice: the file
leaves them blank on the Greenland and Antarctic ice sheets, and poleward of 60° they reach 22x on Arctic ice caps
(Ellesmere would read -65 m). So they are applied between 60°S and 60°N only; beyond that the value is unscaled.
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from build_catalog import NCELL, NY, YEARS, bin1  # noqa: E402
from earthbuddy.stats import T  # noqa: E402

MIN_MONTHS = T.grace_min_months
COLLECTION = "C3195527175-POCLOUD"
CACHE = ROOT / "tools" / "cache" / "grace"
OUT = ROOT / "tools" / "cache" / "grids" / "groundwater.f32"
HYDRO_LAT = 60  # scale factors (land hydrology) apply equatorward of this latitude; glaciers poleward
KHM = [(r + 90) * 360 + c + 180 for r in range(10, 14) for c in range(102, 107)]


def download() -> Path:
    url = f"https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id={COLLECTION}&sort_key=-start_date"
    links = [l["href"] for l in json.load(urllib.request.urlopen(url, timeout=60))["feed"]["entry"][0]["links"]]
    href = next(h for h in links if h.startswith("https://archive.podaac") and h.endswith(".nc"))
    nc = CACHE / href.rsplit("/", 1)[1]
    if not nc.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        jar, part = CACHE / "cookies.txt", nc.with_suffix(".part")
        subprocess.run(["curl", "-sfnL", "--retry", "5", "-C", "-", "-c", jar, "-b", jar, "-o", part, href], check=True)
        part.rename(nc)
    return nc


def build() -> None:
    import netCDF4
    with netCDF4.Dataset(download()) as d:
        lwe = d["lwe_thickness"][:].filled(np.nan)
        lat = d["lat"][:]
        sf = d["scale_factor"][:].filled(1.0)  # blank only on the ice sheets
        sf[abs(lat) > HYDRO_LAT] = 1.0
        land = d["land_mask"][:] == 1
        missing, span = d.months_missing.split(";"), (d.time_coverage_start[:7], d.time_coverage_end[:7])
        ax = {"lat": lat, "lon": d["lon"][:]}
    lwe = np.where(land, lwe * sf, np.nan)
    # JPL's own month labels: every month of the record minus months_missing, in order. Midpoints would put
    # two solutions in Jan 2012 and Apr 2015, which JPL labels Dec 2011 and May 2015.
    months = [f"{y}-{m:02d}" for y in range(2002, 2100) for m in range(1, 13)]
    ym = [k for k in months[months.index(span[0]):months.index(span[1]) + 1] if k not in missing]
    assert len(ym) == len(lwe), (len(ym), len(lwe))
    # Deseasonalise per pixel: minus each calendar month's 2004-2009 mean, so a part-year carries no seasonal bias.
    base = [k for k, label in enumerate(ym) if "2004" <= label[:4] <= "2009"]
    for m in range(1, 13):
        sel = [k for k, label in enumerate(ym) if int(label[5:]) == m]
        lwe[sel] -= lwe[[k for k in base if int(ym[k][5:]) == m]].mean(0)
    out = np.full((NY, NCELL), np.nan, np.float32)
    for i, y in enumerate(YEARS):
        idx = [k for k, label in enumerate(ym) if label.startswith(str(y))]
        print(y, len(idx), "months", "" if len(idx) >= MIN_MONTHS else "-> NaN", flush=True)
        if len(idx) >= MIN_MONTHS:
            out[i] = bin1(lwe[idx].mean(0)[None], ax)[0]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.tofile(OUT)
    print(f"wrote {OUT}")


def check() -> None:
    g = np.fromfile(OUT, np.float32).reshape(NY, NCELL)
    assert g.shape == (24, 64800)
    fin = np.isfinite(g)
    years = fin.any(1)
    assert not years[0] and years[1:16].all() and years[-6:].all(), years  # 2001 before record; 2017 may be NaN
    assert 0.25 < fin[years].mean() < 0.40, fin[years].mean()
    assert -400 < np.nanpercentile(g, 1) and np.nanpercentile(g, 99) < 150, np.nanpercentile(g, [1, 99])  # ice-sheet loss reaches metres
    assert abs(np.nanmean(g[3:9][:, KHM])) < 15, np.nanmean(g[3:9][:, KHM])  # 2004-2009 is the baseline
    print("groundwater ok", fin[years].mean())


if __name__ == "__main__":
    check() if "--check" in sys.argv else build()
