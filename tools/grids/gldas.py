"""GLDAS Noah 0.25° monthly V2.1 -> yearly 1° grids for runoff and drought (tools/grids/BRIEF.md).

  .venv/bin/python tools/grids/gldas.py          # download (resumable) and write tools/cache/grids/{runoff,drought}.f32
  .venv/bin/python tools/grids/gldas.py --check  # assert the grids look right

Source: GLDAS_NOAH025_M 2.1 (C1342986036-GES_DISC) through NASA Earthdata Cloud OPeNDAP, three variables only.
"""
import calendar
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import netCDF4
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from build_catalog import bin1  # noqa: E402
from earthbuddy.stats import T  # noqa: E402

CACHE = ROOT / "tools" / "cache" / "gldas"
OUT = ROOT / "tools" / "cache" / "grids"
YEARS = range(2001, 2025)
MONTHS = [(y, m) for y in YEARS for m in range(1, 13)]
URL = ("https://opendap.earthdata.nasa.gov/collections/C1342986036-GES_DISC/granules/"
       "GLDAS_NOAH025_M.2.1%3AGLDAS_NOAH025_M.A{y}{m:02d}.021.nc4.dap.nc4?dap4.ce=/Qs_acc;/Qsb_acc;/RootMoist_inst;/lat;/lon")
DRY_PCT = T.dry_pct  # drought: a month counts as dry below this percentile of the same calendar month, 2001-2024


def path(y: int, m: int) -> Path:
    return CACHE / f"GLDAS_NOAH025_M.A{y}{m:02d}.021.nc4"


def fetch(ym: tuple[int, int]) -> int:
    p = path(*ym)
    if p.exists():
        return 0
    part, ck = p.with_suffix(".part"), CACHE / ".cookies"
    for _ in range(4):
        r = subprocess.run(["curl", "-sfnL", "--retry", "3", "--max-time", "300", "-c", ck, "-b", ck, "-o", part, URL.format(y=ym[0], m=ym[1])])
        if r.returncode == 0 and part.read_bytes()[:4] == b"\x89HDF":
            part.rename(p)
            return p.stat().st_size
    raise RuntimeError(f"download failed: {ym}")


def load(y: int, m: int, name: str) -> np.ndarray:
    with netCDF4.Dataset(path(y, m)) as d:
        return d[name][0].filled(np.nan).astype(np.float32)


def axes() -> dict:
    with netCDF4.Dataset(path(*MONTHS[0])) as d:
        return {"lat": d["lat"][:].data, "lon": d["lon"][:].data}


def runoff() -> np.ndarray:
    """mm/yr: monthly files hold the mean 3-hour accumulation (kg m-2 = mm), so a month is value x 8 x days."""
    out = []
    for y in YEARS:
        yr = sum((load(y, m, "Qs_acc") + load(y, m, "Qsb_acc")) * 8 * calendar.monthrange(y, m)[1] for m in range(1, 13))
        out.append(yr)  # a NaN month leaves the pixel NaN for that year
    return np.stack(out)


def drought() -> np.ndarray:
    """% of months per year with root-zone soil moisture below the DRY_PCT percentile of that calendar month."""
    dry = np.zeros((len(YEARS), 600, 1440), np.float32)
    bad = np.zeros((600, 1440), bool)
    for m in range(1, 13):
        x = np.stack([load(y, m, "RootMoist_inst") for y in YEARS])
        bad |= ~np.isfinite(x).all(0) | (np.nanmax(x, 0) == np.nanmin(x, 0))  # gaps, or frozen ice-sheet pixels that never vary
        dry += x < np.nanpercentile(x, DRY_PCT, axis=0)
    dry *= 100 / 12
    dry[:, bad] = np.nan
    return dry


def build() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(6) as ex:
        got = sum(ex.map(fetch, MONTHS))
    print(f"downloaded {got / 1e6:.1f} MB this run; cache {sum(f.stat().st_size for f in CACHE.glob('*.nc4')) / 1e6:.1f} MB")
    ax = axes()
    for vid, f in (("runoff", runoff), ("drought", drought)):
        bin1(f(), ax).astype(np.float32).tofile(OUT / f"{vid}.f32")
        print(f"wrote {vid}.f32", flush=True)


def check() -> None:
    cells = ((np.arange(10, 14)[:, None] + 90) * 360 + (np.arange(102, 107)[None, :] + 180)).ravel()
    w = np.cos(np.radians(np.arange(64800) // 360 - 89.5))
    for vid, lo, hi in (("runoff", 0, 8000), ("drought", 0, 100)):
        g = np.fromfile(OUT / f"{vid}.f32", np.float32)
        assert g.size == 24 * 64800, vid
        g = g.reshape(24, 64800)
        ok = np.isfinite(g)
        assert 0.2 < ok.mean() < 0.35, (vid, ok.mean())  # land only, -60..90°N
        assert (ok == ok[0]).all(), vid  # same land mask every year
        assert lo <= np.nanmin(g) and np.nanmax(g) <= hi, (vid, np.nanmin(g), np.nanmax(g))
        for i in (0, 11, 23):
            gm = np.nansum(g[i] * w) / w[ok[i]].sum()
            print(f"{vid} {2001 + i}: global land {gm:.2f}  Cambodia {np.nanmean(g[i, cells]):.2f}")
        print(f"{vid}: {ok.mean() * 100:.1f}% finite cells")
    d = np.fromfile(OUT / "drought.f32", np.float32).reshape(24, 64800)
    assert 15 < np.nanmean(d) < 25, np.nanmean(d)  # ~20% by construction
    print("gldas grids ok")


if __name__ == "__main__":
    check() if "--check" in sys.argv else build()
