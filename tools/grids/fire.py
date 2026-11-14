"""Fire family grids: VIIRS 375 m active fires (NASA FIRMS) and GFWED yearly mean Fire Weather Index (NASA GISS).

.venv/bin/python tools/grids/fire.py            # download (resumable) and write tools/cache/grids/{fire_viirs,fire_weather}.f32
.venv/bin/python tools/grids/fire.py --check    # assert the grids look right
"""
import calendar
import csv
import io
import struct
import sys
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from build_catalog import bin1  # noqa: E402
from earthbuddy.stats import T  # noqa: E402

CACHE, OUT = ROOT / "tools/cache/fire", ROOT / "tools/cache/grids"
YEARS, NCELL = list(range(2001, 2025)), 64800

FIRMS = "https://firms.modaps.eosdis.nasa.gov/data/country/zips/viirs-snpp_{y}_all_countries.zip"
VIIRS_FIRST = 2013    # S-NPP detections start 2012-01-20, so 2012 is not a full year
MIN_MEAN = T.fire_min_mean  # fires/yr: cells whose mean is lower are NaN, as in the MODIS `fire` grid

GFWED = "https://portal.nccs.nasa.gov/datashare/GlobalFWI/v2.0/fwiCalcs.MERRA2/Default/MERRA2.CORRECTED/{y}/FWI.MERRA2.CORRECTED.Monthly.Default.{y}{m:02d}.nc"
FWI_VAR = b"MERRA2.CORRECTED_FWI"
NLAT, NLON = 267, 576  # GFWED MERRA-2 grid: lat -58..75 by 0.5, lon -180..179.375 by 0.625

pool = ThreadPoolExecutor(16)  # FIRMS chunks; GFWED months use their own pool
got = 0  # bytes downloaded this run


def http(url: str, rng: tuple[int, int] | None = None, tries: int = 6) -> bytes:
    global got
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={rng[0]}-{rng[1]}"} if rng else {})
            with urllib.request.urlopen(req, timeout=120) as r:
                b = r.read()
            if rng and len(b) != rng[1] - rng[0] + 1:
                raise IOError(f"short read {len(b)}")
            got += len(b)
            return b
        except Exception as e:  # noqa: BLE001 - retry any network failure
            if k == tries - 1:
                raise
            print(f"retry {url} {rng}: {e}", flush=True)
            time.sleep(2 ** k)


def fetch(url: str, dest: Path, chunk: int = 4 << 20) -> Path:
    """FIRMS serves one connection at ~0.3 MB/s, so pull ranged chunks in parallel; finished chunks survive a crash."""
    if dest.exists():
        return dest
    req = urllib.request.Request(url, method="HEAD")
    size = int(urllib.request.urlopen(req, timeout=60).headers["Content-Length"])
    parts = dest.with_suffix(".parts")
    parts.mkdir(exist_ok=True)

    def one(i):
        p = parts / f"{i:05d}"
        lo, hi = i * chunk, min((i + 1) * chunk, size) - 1
        if not (p.exists() and p.stat().st_size == hi - lo + 1):
            p.write_bytes(http(url, (lo, hi)))

    list(pool.map(one, range(-(-size // chunk))))
    with open(dest.with_suffix(".tmp"), "wb") as f:
        for p in sorted(parts.iterdir()):
            f.write(p.read_bytes())
    dest.with_suffix(".tmp").rename(dest)
    for p in parts.iterdir():
        p.unlink()
    parts.rmdir()
    return dest


def cell(lat: float, lon: float) -> int:
    return min(int(np.floor(lat)) + 90, 179) * 360 + (int(np.floor(lon)) + 180) % 360


def viirs_year(y: int) -> np.ndarray:
    """Vegetation fires (type 0) at nominal or high confidence, counted per 1° cell; CSVs are streamed from the zip."""
    npy = CACHE / f"viirs_{y}.npy"
    if npy.exists():
        return np.load(npy)
    z = fetch(FIRMS.format(y=y), CACHE / f"viirs-snpp_{y}_all_countries.zip")
    n, versions, first = np.zeros(NCELL, np.float32), {}, "9999"
    with zipfile.ZipFile(z) as zf:
        for name in zf.namelist():
            if not name.endswith(".csv"):
                continue
            with zf.open(name) as f:
                rows = csv.reader(io.TextIOWrapper(f, "utf-8"))
                h = next(rows)
                la, lo, co, ty, ve, da = (h.index(c) for c in ("latitude", "longitude", "confidence", "type", "version", "acq_date"))
                for r in rows:
                    first = min(first, r[da])
                    versions[r[ve]] = versions.get(r[ve], 0) + 1
                    if r[ty] == "0" and r[co] in ("n", "h"):
                        n[cell(float(r[la]), float(r[lo]))] += 1
    print(f"viirs {y}: {int(n.sum())} fires, first date {first}, versions {versions}", flush=True)
    np.save(npy, n)
    return n


def nc3_begin(head: bytes, want: bytes) -> tuple[int, int]:
    """Byte offset and size of one variable in a netCDF-3 (64-bit offset) header."""
    assert head[:4] == b"CDF\x02", head[:4]
    p = 8
    size = {1: 1, 2: 1, 3: 2, 4: 4, 5: 4, 6: 8}

    def i4():
        nonlocal p
        p += 4
        return struct.unpack(">i", head[p - 4:p])[0]

    def name():
        nonlocal p
        n = i4()
        p += n + (-n) % 4
        return head[p - n - (-n) % 4:p - (-n) % 4]

    def atts():
        nonlocal p
        i4()
        for _ in range(i4()):
            name()
            t, k = i4(), i4()
            p += k * size[t] + (-k * size[t]) % 4

    i4()
    for _ in range(i4()):
        name(), i4()
    atts()
    i4()
    for _ in range(i4()):
        nm, nd = name(), i4()
        p += 4 * nd
        atts()
        i4()
        vsize = i4()
        begin = struct.unpack(">q", head[p:p + 8])[0]
        p += 8
        if nm == want:
            assert p < len(head)
            return begin, vsize
    raise KeyError(want)


def gfwed_month(y: int, m: int) -> np.ndarray:
    """Monthly mean FWI on the native grid, read by byte range from the netCDF-3 file (one variable of seven)."""
    out = CACHE / "gfwed" / f"{y}{m:02d}.f4"
    if not out.exists():
        url = GFWED.format(y=y, m=m)
        begin, vsize = nc3_begin(http(url, (0, 32767)), FWI_VAR)
        assert vsize == NLAT * NLON * 4, vsize
        out.parent.mkdir(parents=True, exist_ok=True)
        out.with_suffix(".tmp").write_bytes(http(url, (begin, begin + vsize - 1)))
        out.with_suffix(".tmp").rename(out)
    return np.fromfile(out, ">f4").reshape(NLAT, NLON)


def gfwed_year(y: int) -> np.ndarray:
    """Day-weighted yearly mean FWI per native pixel. A month with no FWI (winter snow shutdown) counts as 0;
    a pixel with no FWI all year (masked: water, bare ground, ice) is NaN."""
    with ThreadPoolExecutor(6) as ex:
        a = np.stack(list(ex.map(lambda m: gfwed_month(y, m), range(1, 13))))
    days = np.array([calendar.monthrange(y, m)[1] for m in range(1, 13)], np.float32)[:, None, None]
    seen = np.isfinite(a).any(0)
    return np.where(seen, (np.nan_to_num(a) * days).sum(0) / days.sum(), np.nan).astype(np.float32)


def weather():
    ax = {"lat": -58 + 0.5 * np.arange(NLAT), "lon": -180 + 0.625 * np.arange(NLON)}
    bin1(np.stack([gfwed_year(y) for y in YEARS]), ax).astype(np.float32).tofile(OUT / "fire_weather.f32")
    print("fire_weather.f32 written", flush=True)


def viirs():
    Y = np.full((len(YEARS), NCELL), np.nan, np.float32)
    for y in range(VIIRS_FIRST, YEARS[-1] + 1):
        Y[y - YEARS[0]] = viirs_year(y)
    rec = Y[VIIRS_FIRST - YEARS[0]:]
    Y[:, rec.mean(0) < MIN_MEAN] = np.nan  # too few fires for a trend
    Y.tofile(OUT / "fire_viirs.f32")
    print("fire_viirs.f32 written", flush=True)


def build():
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    weather()  # small (~180 MB) and on a different host; finish it before the 4.4 GB of FIRMS zips
    viirs()
    print(f"{got / 1e9:.2f} GB downloaded this run, {time.time() - t0:.0f} s", flush=True)


def check():
    lat = np.repeat(np.arange(-90, 90) + 0.5, 360)
    lon = np.tile(np.arange(-180, 180) + 0.5, 180)
    khm = (lat > 10) & (lat < 14) & (lon > 102) & (lon < 107)
    for vid, lo, hi, first in (("fire_viirs", 0, 1e6, VIIRS_FIRST), ("fire_weather", 0, 150, 2001)):
        Y = np.fromfile(OUT / f"{vid}.f32", np.float32).reshape(len(YEARS), NCELL)
        assert Y.shape == (24, NCELL)
        assert np.isnan(Y[: first - YEARS[0]]).all()
        rec = Y[first - YEARS[0]:]
        fin = np.isfinite(rec).mean()
        v = rec[np.isfinite(rec)]
        assert 0.03 < fin < 0.6, fin
        assert lo <= v.min() and v.max() <= hi, (v.min(), v.max())
        assert np.isfinite(rec[:, khm]).any(1).all(), "Cambodia must have data every year"
        assert (np.nanmean(rec[:, khm], 1) > (100 if vid == "fire_viirs" else 3)).all()  # dry-season fires and fire weather
        w = np.cos(np.radians(lat))
        for y in (2001, 2012, 2024):
            r = Y[y - YEARS[0]]
            ok = np.isfinite(r)
            m = (r[ok] * w[ok]).sum() / w[ok].sum() if ok.any() else float("nan")
            print(f"{vid} {y}: area-weighted mean {m:.1f}, Cambodia mean {np.nanmean(r[khm]) if ok[khm].any() else float('nan'):.1f}"
                  f"{'' if vid == 'fire_weather' else f', Cambodia sum {r[khm].sum():.0f}'}")
        print(f"{vid}: {fin:.1%} finite cells over its record")
    print("check ok")


if __name__ == "__main__":
    check() if "--check" in sys.argv else build()
