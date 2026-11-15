"""MERRA-2 aerosol and CO yearly 1° grids (tools/grids/BRIEF.md): pm25, dust, smoke, co.

  .venv/bin/python tools/grids/merra2.py           # download (resumes), then write tools/cache/grids/<vid>.f32
  .venv/bin/python tools/grids/merra2.py --check   # assert the written grids look right

GES DISC's on-prem OPeNDAP (goldsmr4) is retired (HTTP 410), so this asks Earthdata Cloud OPeNDAP
(opendap.earthdata.nasa.gov) for only the needed variables of each monthly granule. Granule names come from CMR.
"""
import json
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import netCDF4
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from build_catalog import NCELL, bin1, ownership  # noqa: E402

CACHE = ROOT / "tools" / "cache" / "merra2"
OUT = ROOT / "tools" / "cache" / "grids"
COOKIES = CACHE / "cookies.txt"
YEARS = range(2001, 2025)
AX = {"lat": -90 + 0.5 * np.arange(361), "lon": -180 + 0.625 * np.arange(576)}  # MERRA-2 native grid; the subsets carry no lat/lon
COLLECTIONS = {  # short name: (CMR concept id, variables to subset)
    "M2TMNXAER": ("C1276812866-GES_DISC", ["DUSMASS25", "SSSMASS25", "BCSMASS", "OCSMASS", "SO4SMASS"]),
    "M2TMNXCHM": ("C1276812852-GES_DISC", ["COCL"]),
}
GRIDS = {  # vid: (collection, monthly field from the subset dict, plausible yearly cell range)
    # Buchard et al. 2016: PM2.5 = DU2.5 + SS2.5 + BC + 1.4 OC + 1.375 SO4; kg/m3 -> µg/m3
    "pm25": ("M2TMNXAER", lambda d: 1e9 * (d["DUSMASS25"] + d["SSSMASS25"] + d["BCSMASS"] + 1.4 * d["OCSMASS"] + 1.375 * d["SO4SMASS"]), (0, 500)),
    "dust": ("M2TMNXAER", lambda d: 1e9 * d["DUSMASS25"], (0, 400)),
    "smoke": ("M2TMNXAER", lambda d: 1e9 * (d["BCSMASS"] + d["OCSMASS"]), (0, 400)),  # Canada 2023 fires reach ~210
    "co": ("M2TMNXCHM", lambda d: 1e3 * d["COCL"], (0.05, 5)),  # kg/m2 -> g/m2
}


def granules(short: str) -> dict[tuple[int, int], str]:
    """(year, month) -> granule UR, from CMR; cached so a rerun works offline."""
    path = CACHE / f"granules_{short}.json"
    if not path.exists():
        url = (f"https://cmr.earthdata.nasa.gov/search/granules.json?collection_concept_id={COLLECTIONS[short][0]}"
               f"&temporal=2001-01-01T00:00:00Z,2024-12-31T23:59:59Z&page_size=2000")
        titles = [e["title"] for e in json.load(urllib.request.urlopen(url))["feed"]["entry"]]
        path.write_text(json.dumps(sorted(titles)))
    return {(int(t[-10:-6]), int(t[-6:-4])): t for t in json.loads(path.read_text())}  # ...Nx.YYYYMM.nc4


def fetch(short: str, ur: str) -> Path:
    path = CACHE / ur.split(":")[1]
    if path.exists():
        return path
    concept, names = COLLECTIONS[short]
    url = (f"https://opendap.earthdata.nasa.gov/collections/{concept}/granules/{ur.replace(':', '%3A')}.dap.nc4"
           f"?dap4.ce={'%3B'.join('/' + n for n in names)}")
    part = path.with_suffix(".part")
    subprocess.run(["curl", "-sS", "--fail", "-n", "-L", "-c", COOKIES, "-b", COOKIES, "--retry", "3", "-o", part, url], check=True)
    part.rename(path)
    return path


def download() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    jobs = [(s, ur) for s in COLLECTIONS for ur in granules(s).values()]
    before = sum(p.stat().st_size for p in CACHE.glob("*.nc4"))
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda j: fetch(*j), jobs))
    return sum(p.stat().st_size for p in CACHE.glob("*.nc4")) - before


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for short in COLLECTIONS:
        files = granules(short)
        vids = [v for v, g in GRIDS.items() if g[0] == short]
        native = {v: [] for v in vids}  # per year: mean of the 12 monthly native fields, or None when a month is missing
        for y in YEARS:
            months = [files.get((y, m)) for m in range(1, 13)]
            if None in months:
                for v in vids:
                    native[v].append(None)
                continue
            acc = {v: 0.0 for v in vids}
            for ur in months:
                with netCDF4.Dataset(CACHE / ur.split(":")[1]) as d:
                    fields = {k: d[k][0].filled(np.nan).astype(np.float64) for k in COLLECTIONS[short][1]}
                for v in vids:
                    acc[v] = acc[v] + GRIDS[v][1](fields)
            for v in vids:
                native[v].append(acc[v] / 12)
        for v in vids:
            nan = np.full((361, 576), np.nan)
            grid = bin1(np.stack([g if g is not None else nan for g in native[v]]), AX)
            grid.astype(np.float32).tofile(OUT / f"{v}.f32")
            print(f"{v}: wrote {OUT / f'{v}.f32'}", flush=True)


def check() -> None:
    land = np.unique(np.concatenate(list(ownership().values())))
    w = np.cos(np.radians(land // 360 - 89.5))
    cam = np.array([(r + 90) * 360 + (c + 180) % 360 for r in range(10, 14) for c in range(102, 107)])
    for v, (_, _, (lo, hi)) in GRIDS.items():
        g = np.fromfile(OUT / f"{v}.f32", np.float32)
        assert g.size == len(YEARS) * NCELL, v
        g = g.reshape(len(YEARS), NCELL)
        ok = np.isfinite(g)
        assert ok.mean() > 0.99, (v, ok.mean())  # MERRA-2 covers every cell, land and ocean
        assert lo <= np.nanmin(g) and np.nanmax(g) <= hi, (v, np.nanmin(g), np.nanmax(g))
        glob = [(g[i, land] * w).sum() / w.sum() for i in (0, 11, 23)]
        print(f"{v}: finite {ok.mean():.1%}, global land 2001/2012/2024 {[round(float(x), 3) for x in glob]}, "
              f"Cambodia {[round(float(g[i, cam].mean()), 3) for i in (0, 11, 23)]}")
    print("merra2 check ok")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    else:
        print(f"downloaded {download() / 1e6:.0f} MB", flush=True)
        build()
        check()
