"""Greenness: MOD13C2 V061 monthly 0.05° NDVI -> yearly 1° grid (tools/grids/BRIEF.md).

  .venv/bin/python tools/grids/ndvi.py            # download (4 workers), extract, write tools/cache/grids/ndvi.f32
  .venv/bin/python tools/grids/ndvi.py --check

Each month comes from NASA's cloud OPeNDAP (Hyrax) as the NDVI SDS alone (~8 MB netCDF-4 instead of the
~95 MB HDF4 with 13 SDS). It is binned to 1° at once, kept as a 64800-float .npy, and the download deleted.
Re-running skips months whose .npy exists, so a crash resumes where it stopped.
"""
import json
import subprocess
import threading
import time
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from build_catalog import NCELL, NY, YEARS, bin1  # noqa: E402

COLLECTION = "C2565788914-LPCLOUD"
CACHE = ROOT / "tools" / "cache" / "ndvi"
OUT = ROOT / "tools" / "cache" / "grids" / "ndvi.f32"
OPENDAP = "https://opendap.earthdata.nasa.gov/collections/" + COLLECTION + "/granules/{}.dap.nc4"
SDS = "/MOD_Grid_monthly_CMG_VI/Data_Fields/CMG_0_05_Deg_Monthly_NDVI"
SCALE, VALID_MIN = 1e-4, -2000  # fill is -3000; the file's scale_factor 10000 means divide, so we scale by hand
READ = threading.Lock()
AX = {"lat": 89.975 - 0.05 * np.arange(3600), "lon": -179.975 + 0.05 * np.arange(7200)}


def granules() -> dict[tuple[int, int], str]:
    """(year, month) -> granule title, from CMR. One granule per month in V061."""
    out, page = {}, 1
    while True:
        url = (f"https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id={COLLECTION}"
               f"&temporal={YEARS[0]}-01-01T00:00:00Z,{YEARS[-1]}-12-31T23:59:59Z&page_size=2000&page_num={page}"
               "&sort_key=start_date")
        entries = json.load(urllib.request.urlopen(url, timeout=60))["feed"]["entry"]
        for e in entries:
            y, m = int(e["time_start"][:4]), int(e["time_start"][5:7])
            out[(y, m)] = e["title"]
        if len(entries) < 2000:
            return out
        page += 1


def month(key: tuple[int, int], title: str) -> str:
    npy = CACHE / f"{key[0]}-{key[1]:02d}.npy"
    if npy.exists():
        return f"{npy.name} cached"
    hdf = CACHE / f"{title}.nc4"
    jar = CACHE / "cookies.txt"
    for attempt in range(3):  # Earthdata sometimes answers 200 with an HTML login page instead of the data
        subprocess.run(["curl", "-sfnL", "--retry", "5", "--retry-all-errors", "-c", jar, "-b", jar, "-o", hdf,
                        "-G", "--data-urlencode", f"dap4.ce={SDS}", OPENDAP.format(title)], check=True)
        if hdf.read_bytes()[:4] == b"\x89HDF":
            break
        hdf.unlink()
        time.sleep(30)
    else:
        raise RuntimeError(f"{title}: no netCDF after 3 tries")
    import netCDF4
    with READ, netCDF4.Dataset(hdf) as d:  # the netCDF/HDF5 C library is not thread-safe
        var = d[SDS]
        var.set_auto_maskandscale(False)
        raw = var[:]
    v = np.where(raw >= VALID_MIN, raw * SCALE, np.nan).astype(np.float32)
    np.save(npy.with_suffix(".tmp.npy"), bin1(v[None], AX)[0].astype(np.float32))
    npy.with_suffix(".tmp.npy").rename(npy)
    size = hdf.stat().st_size
    hdf.unlink()
    with open(CACHE / "bytes.log", "a") as f:
        f.write(f"{hdf.name} {size}\n")
    return f"{npy.name} {size / 1e6:.0f} MB"


def build() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    urls = granules()
    print(f"{len(urls)} granules", flush=True)
    with ThreadPoolExecutor(4) as pool:
        for msg in pool.map(lambda kv: month(*kv), sorted(urls.items())):
            print(msg, flush=True)
    out = np.full((NY, NCELL), np.nan, np.float32)
    for i, y in enumerate(YEARS):
        files = [CACHE / f"{y}-{m:02d}.npy" for m in range(1, 13)]
        if all(f.exists() for f in files):  # a year missing a month stays NaN
            with np.errstate(invalid="ignore"):
                out[i] = np.nanmean([np.load(f) for f in files], 0)  # NaN only where all 12 months are fill
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.tofile(OUT)
    print(f"wrote {OUT}", flush=True)


def check() -> None:
    g = np.fromfile(OUT, np.float32).reshape(NY, NCELL)
    assert g.shape == (24, 64800)
    fin = np.isfinite(g)
    assert fin.mean(1).min() > 0.25, fin.mean(1)
    assert -0.3 < np.nanmin(g) and np.nanmax(g) < 1, (np.nanmin(g), np.nanmax(g))
    kh = [(r + 90) * 360 + c + 180 for r in range(10, 14) for c in range(102, 107)]
    assert 0.4 < np.nanmean(g[:, kh]) < 0.8, np.nanmean(g[:, kh])  # Cambodia is green
    print("ndvi ok", fin.mean())


if __name__ == "__main__":
    check() if "--check" in sys.argv else build()
