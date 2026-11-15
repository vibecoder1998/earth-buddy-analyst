"""OMI tropospheric NO2 (OMNO2d V004, GES DISC) -> tools/cache/grids/no2.f32, yearly 1° grid 2001-2024.

  .venv/bin/python tools/grids/omi.py            # download (8 workers, resumable) then reduce
  .venv/bin/python tools/grids/omi.py --check

Each day is read through Earthdata OPeNDAP, ColumnAmountNO2TropCloudScreened only (~0.86 MB as nc4);
a file OPeNDAP refuses is fetched whole from data.gesdisc.earthdata.nasa.gov instead.
A 1° cell's daily value is the mean of its valid 0.25° pixels; its yearly value is the mean over its valid
days, kept only when it has at least MIN_DAYS valid days.
"""
import json
import re
import subprocess
import datetime
import sys
import threading
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from build_catalog import NCELL, NY, YEARS, bin1  # noqa: E402
from earthbuddy.stats import T  # noqa: E402

COLLECTION = "C3333493715-GES_DISC"  # OMNO2d V004
FIRST, LAST = 2005, 2024
MIN_DAYS = T.no2_min_days
VAR = "ColumnAmountNO2TropCloudScreened"
EVERY = 2  # keep days whose day-of-year divides by this; the download is bandwidth-bound
CACHE = ROOT / "tools" / "cache" / "omi"
OUT = ROOT / "tools" / "cache" / "grids" / "no2.f32"
AX = {"lat": -89.875 + 0.25 * np.arange(720), "lon": -179.875 + 0.25 * np.arange(1440)}  # GridOrigin Center, span -180..180, -90..90


def curl(url: str, out: Path) -> bool:
    jar = CACHE / f"cookies-{threading.get_ident()}.txt"
    part = out.with_suffix(out.suffix + ".part")
    r = subprocess.run(["curl", "-sf", "-n", "-L", "-c", jar, "-b", jar, "--retry", "4", "--max-time", "300", "-o", part, url])
    if r.returncode or not part.exists() or part.read_bytes()[:4] != b"\x89HDF":
        part.unlink(missing_ok=True)
        return False
    part.rename(out)
    return True


def granules() -> list[dict]:
    path = CACHE / "granules.json"
    if path.exists():
        return json.loads(path.read_text())
    out, after = [], None
    while True:
        req = urllib.request.Request(f"https://cmr.earthdata.nasa.gov/search/granules.umm_json?collection_concept_id={COLLECTION}"
                                     f"&temporal={FIRST}-01-01T00:00:00Z,{LAST}-12-31T23:59:59Z&page_size=500",
                                     headers={"CMR-Search-After": after} if after else {})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=300) as r:
                    items, after = json.load(r)["items"], r.headers.get("CMR-Search-After")
                break
            except OSError:
                if attempt == 4:
                    raise
        for it in items:
            urls = [u["URL"] for u in it["umm"]["RelatedUrls"]]
            name = next(u for u in urls if u.startswith("https://data.gesdisc") and u.endswith(".he5")).rsplit("/", 1)[1]
            y, m, d = re.search(r"_(\d{4})m(\d{2})(\d{2})_", name).groups()
            out.append({"date": f"{y}-{m}-{d}", "name": name,
                        "opendap": next(u for u in urls if u.startswith("https://opendap.earthdata.nasa.gov")),
                        "https": next(u for u in urls if u.startswith("https://data.gesdisc") and u.endswith(".he5"))})
        if not items or not after:
            break
    out = sorted({g["date"]: g for g in out if FIRST <= int(g["date"][:4]) <= LAST}.values(), key=lambda g: g["date"])
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    return out


def fetch(g: dict) -> str:
    sub, whole = CACHE / (g["name"] + ".nc4"), CACHE / g["name"]
    if sub.exists() or whole.exists():
        return "cached"
    ce = "?dap4.ce=/HDFEOS/GRIDS/ColumnAmountNO2/Data_Fields/" + VAR
    if curl(g["opendap"] + ".dap.nc4" + ce, sub):
        return "opendap"
    return "whole" if curl(g["https"], whole) else "FAILED"


def day(g: dict) -> np.ndarray:
    sub, whole = CACHE / (g["name"] + ".nc4"), CACHE / g["name"]
    with h5py.File(sub if sub.exists() else whole) as f:
        x = f["HDFEOS/GRIDS/ColumnAmountNO2/" + ("Data_Fields/" if sub.exists() else "Data Fields/") + VAR][:]
    x = np.where(x > -1e29, x / 1e15, np.nan)  # fill -1.27e30; unit 10^15 molecules/cm²
    return bin1(x[None], AX)[0]


def reduce(gs: list[dict]) -> None:
    by_year = defaultdict(list)
    for g in gs:
        by_year[int(g["date"][:4])].append(g)
    Y = np.full((NY, NCELL), np.nan, np.float32)
    for y in range(FIRST, LAST + 1):
        s, n = np.zeros(NCELL), np.zeros(NCELL)
        for g in by_year[y]:
            v = day(g)
            ok = np.isfinite(v)
            s[ok] += v[ok]
            n[ok] += 1
        Y[y - YEARS[0]] = np.where(n >= MIN_DAYS, s / np.maximum(n, 1), np.nan)
        print(y, len(by_year[y]), "days", f"{np.isfinite(Y[y - YEARS[0]]).mean():.3f} cells finite", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Y.tofile(OUT)


def check() -> None:
    Y = np.fromfile(OUT, np.float32).reshape(NY, NCELL)
    assert Y.shape == (24, 64800)
    assert np.isnan(Y[: FIRST - YEARS[0]]).all()
    fin = np.isfinite(Y[FIRST - YEARS[0]:]).mean()
    assert 0.5 < fin <= 1, fin
    v = Y[np.isfinite(Y)]
    # the median cell is clean ocean, about 0.2
    assert -2 < v.min() and v.max() < 60 and 0.1 < np.median(v) < 3, (v.min(), np.median(v), v.max())
    khm = Y[:, [(r + 90) * 360 + c + 180 for r in range(10, 14) for c in range(102, 107)]]
    assert np.isfinite(khm[FIRST - YEARS[0]:]).any(1).all()
    print(f"no2 ok: finite {fin:.3f}, range {v.min():.2f}..{v.max():.2f}, median {np.median(v):.2f}")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
        sys.exit()
    gs = [g for g in granules() if datetime.date.fromisoformat(g["date"]).timetuple().tm_yday % EVERY == 0]
    years = defaultdict(int)
    for g in gs:
        years[g["date"][:4]] += 1
    print("granules per year:", dict(years), flush=True)
    with ThreadPoolExecutor(8) as ex:
        res = defaultdict(int)
        for i, r in enumerate(ex.map(fetch, gs)):
            res[r] += 1
            if i % 200 == 0:
                print(i, dict(res), flush=True)
    print("downloads:", dict(res), flush=True)
    if res["FAILED"]:
        sys.exit("some days failed; run again to resume")
    reduce(gs)
    check()
