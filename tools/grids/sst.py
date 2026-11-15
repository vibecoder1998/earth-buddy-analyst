"""Sea surface temperature (GHRSST MUR 0.25° v4.2, PO.DAAC) -> tools/cache/grids/sst.f32, yearly 1° grid 2001-2024.

  .venv/bin/python tools/grids/sst.py            # download (8 workers, resumable) then reduce
  .venv/bin/python tools/grids/sst.py --check

Each day is read through Earthdata OPeNDAP, analysed_sst only (~0.87 MB as nc4); a file OPeNDAP refuses is
fetched whole from archive.podaac.earthdata.nasa.gov instead. analysed_sst is filled over land, so a 1° cell's
value is the mean of its water pixels: a coastal land cell gets the sea along its coast, an inland cell stays NaN.
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

COLLECTION = "C2036880657-POCLOUD"  # MUR25-JPL-L4-GLOB-v04.2, starts 2002-08-31
FIRST, LAST = 2003, 2024
EVERY = 5  # keep days whose day-of-year divides by this; the download is bandwidth-bound
CACHE = ROOT / "tools" / "cache" / "sst"
OUT = ROOT / "tools" / "cache" / "grids" / "sst.f32"


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
            https = next(u for u in urls if u.startswith("https://archive.podaac") and u.endswith(".nc"))
            name = https.rsplit("/", 1)[1]
            y, m, d = re.match(r"(\d{4})(\d{2})(\d{2})", name).groups()
            out.append({"date": f"{y}-{m}-{d}", "name": name, "https": https,
                        "opendap": next((u for u in urls if u.startswith("https://opendap.earthdata.nasa.gov")), None)})
        if not items or not after:
            break
    out = sorted({g["date"]: g for g in out if FIRST <= int(g["date"][:4]) <= LAST}.values(), key=lambda g: g["date"])
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    return out


def fetch(g: dict) -> str:
    sub, whole = CACHE / (g["name"] + "4"), CACHE / g["name"]
    if sub.exists() or whole.exists():
        return "cached"
    if g["opendap"] and curl(g["opendap"] + ".dap.nc4?dap4.ce=/analysed_sst", sub):
        return "opendap"
    return "whole" if curl(g["https"], whole) else "FAILED"


def reduce(gs: list[dict]) -> None:
    by_year = defaultdict(list)
    for g in gs:
        by_year[int(g["date"][:4])].append(g)
    Y = np.full((NY, NCELL), np.nan, np.float32)
    # the OPeNDAP subsets carry lat/lon filled with zeros, so use the fixed MUR25 axis (checked against a whole file)
    ax = {"lat": -89.875 + 0.25 * np.arange(720), "lon": -179.875 + 0.25 * np.arange(1440)}
    for y in range(FIRST, LAST + 1):
        if len({g["date"][5:7] for g in by_year[y]}) < 12:  # a year missing a month stays NaN
            print(y, "missing months", flush=True)
            continue
        s, n = 0, 0
        for g in by_year[y]:
            sub, whole = CACHE / (g["name"] + "4"), CACHE / g["name"]
            with h5py.File(sub if sub.exists() else whole) as f:
                x = f["analysed_sst"][0]
            k = np.where(x == -32768, np.nan, x * 0.001 + 298.15 - 273.15)  # int16 kelvin, scale 0.001, offset 298.15
            s, n = s + np.nan_to_num(k), n + np.isfinite(k)
        mean = np.where(n > 0, s / np.maximum(n, 1), np.nan)  # per 0.25° pixel; water pixels have every day
        Y[y - YEARS[0]] = bin1(mean[None], ax)[0]
        print(y, len(by_year[y]), "days", f"{np.isfinite(Y[y - YEARS[0]]).mean():.3f} cells finite", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Y.tofile(OUT)


def check() -> None:
    Y = np.fromfile(OUT, np.float32).reshape(NY, NCELL)
    assert Y.shape == (24, 64800)
    assert np.isnan(Y[: FIRST - YEARS[0]]).all()
    fin = np.isfinite(Y[FIRST - YEARS[0]:]).mean()
    assert 0.6 < fin < 0.85, fin  # the ocean plus coastal cells
    v = Y[np.isfinite(Y)]
    assert -2.5 < v.min() and v.max() < 35 and 10 < v.mean() < 25, (v.min(), v.mean(), v.max())
    gulf = Y[FIRST - YEARS[0]:, (10 + 90) * 360 + 103 + 180]  # Gulf of Thailand off Cambodia, 10-11 N 103-104 E
    assert np.isfinite(gulf).all() and 27 < gulf.mean() < 31, gulf
    print(f"sst ok: finite {fin:.3f}, range {v.min():.2f}..{v.max():.2f}, mean {v.mean():.2f}")


if __name__ == "__main__":
    if "--reduce" in sys.argv:  # downloads already done
        reduce([g for g in granules() if datetime.date.fromisoformat(g["date"]).timetuple().tm_yday % EVERY == 0])
        check()
        sys.exit()
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
