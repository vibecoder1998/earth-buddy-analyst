"""Build data/ from the claim-desk snapshot and NASA data (docs/01-catalog-and-data.md).

  uv pip install --python .venv -r tools/requirements-build.txt
  .venv/bin/python tools/build_catalog.py --adapt [SNAPSHOT]
  .venv/bin/python tools/build_catalog.py --extend     # add catalog.src.json variables the snapshot lacks
  .venv/bin/python tools/build_catalog.py --summary    # data/summary.json from data/v, no network
  .venv/bin/python tools/build_catalog.py --points     # city points in data/catalog.json from data/gazetteer.json, no network
  .venv/bin/python tools/build_catalog.py --check
"""
import argparse
import calendar
import csv
import datetime
import functools
import io
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from earthbuddy import catalog, stats  # noqa: E402
from earthbuddy.words import ascii_digits  # noqa: E402
from earthbuddy.types import Country, TooShort  # noqa: E402

DATA = ROOT / "data"
CACHE = ROOT / "tools" / "cache"
SRC = json.loads((ROOT / "tools" / "catalog.src.json").read_text())
SNAPSHOT = Path.home() / "earth-buddy-claimdesk-snapshot"
SEDAC = {
    "gpw-natid": CACHE / "gpw-v4-national-identifier-grid-rev11_30_sec_asc.zip",
    "gpw-adm-points": CACHE / "gpw-v4-admin-unit-center-points-population-estimates-rev11_global_csv.zip",
}
RENAME = {"warmUp": "warm_up", "knownBefore": "known_before"}
DROP = {"gridded", "icon"}
BUILD_ONLY = {"ids", "store", "land", "text"}
NEW_FIELDS = {"regional": True, "per_day": False, "season": None, "point_scale": 1}
YEARS = list(range(SRC["years"][0], SRC["years"][1] + 1))
NY, NCELL = len(YEARS), 180 * 360
ROWS, COLS = np.divmod(np.arange(NCELL), 360)
CLAT, CLON = ROWS - 89.5, COLS - 179.5
PIXELS = 120


def write(path: Path, obj, indent: int | None = None) -> None:
    path.write_text(ascii_digits(json.dumps(obj, ensure_ascii=False, indent=indent, separators=None if indent else (",", ":"))) + "\n")


def variable(v: dict) -> dict:
    add = SRC["variables"][v["id"]]
    out = {RENAME.get(k, k): x for k, x in v.items() if k not in DROP}
    out["source"] = {k: v["source"][k] for k in ("param", "kind", "resolution")} | {"ids": add["ids"]}
    out.setdefault("doubt", None)
    return out | NEW_FIELDS | {k: x for k, x in add.items() if k not in BUILD_ONLY}


def natid() -> dict[str, np.ndarray]:
    cached = CACHE / "natid_cells.npz"
    if not cached.exists():
        counts = np.zeros((NCELL, 1000), np.int32)
        centre = np.full(NCELL, -1, np.int32)
        with zipfile.ZipFile(SEDAC["gpw-natid"]) as z:
            for tile in sorted(n for n in z.namelist() if n.endswith(".asc")):
                with z.open(tile) as f:
                    head = {k.decode(): float(x) for k, x in (f.readline().split() for _ in range(6))}
                    x0, y0, nrows = int(head["xllcorner"]), int(head["yllcorner"]), int(head["nrows"])
                    width = int(head["ncols"]) // PIXELS
                    col = (np.arange(int(head["ncols"])) // PIXELS)[None, :] * 1000
                    for band in range(nrows // PIXELS):
                        block = np.fromstring(b"".join(f.readline() for _ in range(PIXELS)), np.int32, sep=" ")
                        block = block.reshape(PIXELS, -1)
                        land = block >= 0
                        key = np.broadcast_to(col, block.shape)[land] + block[land]
                        first = (y0 + nrows // PIXELS - 1 - band + 90) * 360 + x0 + 180
                        counts[first:first + width] += np.bincount(key, minlength=width * 1000).reshape(width, 1000)
                        centre[first:first + width] = np.maximum(block[PIXELS // 2, PIXELS // 2::PIXELS], -1)
        cell, code = np.nonzero(counts)
        np.savez_compressed(cached, centre=centre, cell=cell, code=code, pixels=counts[cell, code])
    return dict(np.load(cached))


def natid_lookup() -> dict[int, dict]:
    with zipfile.ZipFile(SEDAC["gpw-natid"]) as z:
        name = next(n for n in z.namelist() if n.endswith("_rev11_lookup.txt"))
        rows = csv.DictReader(io.TextIOWrapper(z.open(name), "latin-1"), delimiter="\t")
        return {int(r["Value"]): r for r in rows}


def ownership() -> dict[str, np.ndarray]:
    g = natid()
    cell, code, pixels = g["cell"], g["code"], g["pixels"]
    iso = {k: r["ISOCODE"] for k, r in natid_lookup().items()}
    owned: dict[int, list[int]] = {}
    for c in np.flatnonzero(g["centre"] >= 0):
        owned.setdefault(int(g["centre"][c]), []).append(int(c))
    order = np.lexsort((-pixels, code))
    for i in order[np.r_[True, code[order][1:] != code[order][:-1]]]:
        owned.setdefault(int(code[i]), [int(cell[i])])
    return {iso[k]: np.array(sorted(cs)) for k, cs in sorted(owned.items())}


def get(url: str, path: Path) -> bytes:
    if not path.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "python-urllib"})
        for attempt in range(5):
            try:
                data = urllib.request.urlopen(req, timeout=120).read()
                break
            except urllib.error.HTTPError as e:
                if e.code < 500 or attempt == 4:
                    raise
            except OSError:
                if attempt == 4:
                    raise
            time.sleep(2 ** attempt)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.parent / (path.name + ".part")
        tmp.write_bytes(data)
        tmp.replace(path)
    return path.read_bytes()


def decode(raw: bytes, meta: dict) -> np.ndarray:
    from numcodecs import Blosc, get_codec
    a = np.frombuffer(Blosc().decode(raw), dtype=meta["dtype"])
    for f in reversed(meta.get("filters") or []):
        a = get_codec(f).decode(a)
    a = np.array(a, dtype=np.float64 if a.dtype.kind == "f" else a.dtype).reshape(meta["chunks"])
    fill = meta.get("fill_value")
    if a.dtype.kind == "f" and fill not in (None, "NaN"):
        a[a == float(fill)] = np.nan
    return a


@functools.cache
def store(name: str):
    url = SRC["stores"][name]["zarr"]
    zm = json.loads(get(f"{url}/.zmetadata", CACHE / name / ".zmetadata"))["metadata"]
    ax = {k: decode(get(f"{url}/{k}/0", CACHE / name / k / "0"), zm[f"{k}/.zarray"]) for k in ("time", "lat", "lon")}
    t0 = datetime.date.fromisoformat(zm["time/.zattrs"]["units"].split("since ")[1][:10])
    ax["dates"] = [t0 + datetime.timedelta(days=int(d)) for d in ax["time"]]
    return url, zm, ax


def read(name: str, param: str, tidx: list[int]) -> np.ndarray:
    url, zm, ax = store(name)
    meta = zm[f"{param}/.zarray"]
    _, nlat, nlon = meta["shape"]
    _, cy, cx = meta["chunks"]
    keys = [(a, b) for a in range(-(-nlat // cy)) for b in range(-(-nlon // cx))]
    grid = np.full((len(tidx), nlat, nlon), np.nan, np.float32)

    def load(k):
        raw = get(f"{url}/{param}/0.{k[0]}.{k[1]}", CACHE / name / param / f"0.{k[0]}.{k[1]}")
        return k, decode(raw, meta)[tidx]

    with ThreadPoolExecutor(16) as ex:
        for (a, b), block in ex.map(load, keys):
            ys, xs = slice(a * cy, min((a + 1) * cy, nlat)), slice(b * cx, min((b + 1) * cx, nlon))
            grid[:, ys, xs] = block[:, : ys.stop - ys.start, : xs.stop - xs.start]
    return grid


def bin1(grid: np.ndarray, ax: dict) -> np.ndarray:
    row = np.clip(np.floor(ax["lat"] + 90).astype(int), 0, 179)
    col = np.floor(ax["lon"] + 180).astype(int) % 360
    idx = (row[:, None] * 360 + col[None, :]).ravel()
    out = np.full((len(grid), NCELL), np.nan)
    for t, g in enumerate(grid):
        v = g.ravel().astype(np.float64)
        ok = np.isfinite(v)
        cnt = np.bincount(idx[ok], minlength=NCELL)
        out[t] = np.where(cnt > 0, np.bincount(idx[ok], v[ok], minlength=NCELL) / np.maximum(cnt, 1), np.nan)
    return out


def yearly(v: dict, snapshot: Path) -> np.ndarray:
    src, st = SRC["variables"][v["id"]], SRC["stores"][SRC["variables"][v["id"]]["store"]]
    if "snapshot" in st or "grid" in st:  # a ready yearly 1° grid: tools/grids/*.py writes the "grid" ones
        path = snapshot / st["snapshot"] if "snapshot" in st else CACHE / "grids" / st["grid"]
        return np.fromfile(path, np.float32).reshape(NY, NCELL).astype(np.float64)
    _, _, ax = store(src["store"])
    if st.get("monthly"):
        months = src.get("season") or list(range(1, 13))
        ym = [(d.year, d.month) for d in ax["dates"]]
        want = [(y - (m > months[-1]), m) for y in YEARS for m in months]
        grid = read(src["store"], v["source"]["param"], [ym.index(k) for k in want])
        days = np.array([calendar.monthrange(*k)[1] for k in want], np.float32)
        grid = (grid * days[:, None, None]).reshape(NY, len(months), *grid.shape[1:]).sum(1)
    else:
        ys = [d.year for d in ax["dates"]]
        tidx = [ys.index(y) for y in YEARS]
        grid = read(src["store"], v["source"]["param"], tidx)
        if src.get("land"):  # the annual store fills land-model values over ocean; EVLAND is NaN there
            grid[np.isnan(read(src["store"], "EVLAND", tidx))] = np.nan
    return bin1(grid, ax) * src.get("point_scale", 1)


def area_series(Y: np.ndarray, cells: np.ndarray, total: bool, first_year: int = YEARS[0]):
    # a record that starts late leaves earlier years NaN; a year no cell has (a mission gap) stays a gap
    rows = np.isfinite(Y).any(1) & (np.array(YEARS) >= first_year)
    ok = cells[np.isfinite(Y[np.ix_(rows, cells)]).all(0)]
    if not len(ok):
        return None, 0
    if total:
        return Y[:, ok].sum(1), len(ok)
    w = np.cos(np.radians(CLAT[ok]))
    return (Y[:, ok] * w).sum(1) / w.sum(), len(ok)


def series_json(s, d: int) -> list[float | None]:
    return [None if not math.isfinite(x) else round(float(x), d) for x in s]


def geometry(cells: np.ndarray) -> dict:
    import shapely
    from shapely.geometry import box, mapping
    shape = shapely.union_all([box(CLON[c] - 0.5, CLAT[c] - 0.5, CLON[c] + 0.5, CLAT[c] + 0.5) for c in cells])
    return mapping(shapely.normalize(shape))


def khmer_names(snapshot: Path) -> dict[str, str]:
    text = (snapshot / "js" / "names.km.js").read_text()
    return dict(re.findall(r'([A-Z]{3}):"([^"]+)"', text))


def countries(own: dict[str, np.ndarray], snapshot: Path) -> dict[str, dict]:
    names = {r["ISOCODE"]: r["NAME0"] for r in natid_lookup().values()}
    km, aliases = khmer_names(snapshot), SRC["country_aliases"]
    out = {}
    for iso, cells in own.items():
        lon = math.degrees(math.atan2(np.sin(np.radians(CLON[cells])).mean(), np.cos(np.radians(CLON[cells])).mean()))
        out[iso] = {"name": {"en": names[iso], "km": km.get(iso)}, "aliases": {"en": aliases.get(iso, []), "km": []},
                    "cells": len(cells), "lat": round(float(CLAT[cells].mean()), 3), "lon": round(lon, 3)}
    return out


def groups(places: list[dict], country: dict, gazetteer: list[dict]) -> list[dict]:
    members = {"countries": [{"kind": "country", "iso3": iso} for iso in country],
               "places": [{"kind": "place", "id": p["id"]} for p in places]}
    spellings = {}
    for g in SRC["groups"]:
        if "points" in g:
            members[g["id"]] = [resolve(p, gazetteer, country) for p in g["points"]]
            spellings[g["id"]] = {m["name"]: sorted({a.casefold() for a in (p.get("gazetteer", p["name"]), *p.get("aliases", []))}
                                                    - {p["name"].casefold()})
                                  for p, m in zip(g["points"], members[g["id"]])}
    return [{k: g[k] for k in ("id", "name", "aliases", "note")}
            | {"members": members[g["id"]], "member_aliases": {n: a for n, a in spellings.get(g["id"], {}).items() if a}}
            | ({"member_names": {"km": {m["name"]: f"{p['km']}, {country[p['iso3']]['name']['km']}"
                                        for p, m in zip(g["points"], members[g["id"]])}}} if "points" in g else {})
            for g in SRC["groups"]]


def entry(point: dict, gazetteer: list[dict]) -> dict:
    key = point.get("gazetteer", point["name"]).casefold()
    hits = [e for e in gazetteer if e["iso3"] == point["iso3"] and key in (e["name"].casefold(), *map(str.casefold, e["alt_names"]))]
    if not hits:
        sys.exit(f"{point['name']} ({point['iso3']}) matches no gazetteer entry")
    return min(hits, key=lambda e: e["level"])


def resolve(point: dict, gazetteer: list[dict], country: dict) -> dict:
    e = entry(point, gazetteer)
    return {"kind": "point", "lat": e["lat"], "lon": e["lon"], "name": f"{point['name']}, {country[point['iso3']]['name']['en']}"}


def located(places: list[dict], gazetteer: list[dict]) -> list[dict]:
    """Each place in place_points gets the gazetteer centre of its city as `point`; the rest keep their cell centre."""
    at = {pid: entry(p, gazetteer) for pid, p in SRC["place_points"].items()}
    return [p | ({"point": {"lat": at[p["id"]]["lat"], "lon": at[p["id"]]["lon"]}} if p["id"] in at else {}) for p in places]


def points() -> None:
    path = DATA / "catalog.json"
    c = json.loads(path.read_text())
    c["places"] = located(c["places"], json.loads((DATA / "gazetteer.json").read_text()))
    write(path, c, indent=1)


def gazetteer() -> list[dict]:
    sums: dict[tuple, list[float]] = {}
    with zipfile.ZipFile(SEDAC["gpw-adm-points"]) as z:
        for name in sorted(n for n in z.namelist() if n.endswith(".csv")):
            for r in csv.DictReader(io.TextIOWrapper(z.open(name), "utf-8", errors="replace")):
                w = float(r["LAND_A_KM"]) or float(r["TOTAL_A_KM"]) or 1e-9
                lat, lon = math.radians(float(r["CENTROID_Y"])), math.radians(float(r["CENTROID_X"]))
                v = (w * lat, w * math.cos(lon), w * math.sin(lon), w)
                names = [r[k].strip() for k in ("COUNTRYNM", "NAME1", "NAME2")]
                for level in range(3):
                    if names[level] in ("NA", ""):
                        break
                    s = sums.setdefault((r["ISOALPHA"], level, *names[:level + 1]), [0.0] * 4)
                    for i in range(4):
                        s[i] += v[i]
    composed = set()
    for c in SRC["composed"]:
        parent = next(k for k in sums if k[0] == c["iso3"] and k[1] == 1 and k[3] == c["parent"])
        keys = [(*parent[:1], 2, *parent[2:], d) for d in c["districts"]]
        if missing := [k[-1] for k in keys if k not in sums]:
            sys.exit(f"{c['name']}: no gazetteer district {missing}")
        part = [sum(sums[k][i] for k in keys) for i in range(4)]
        sums[parent] = [a - b for a, b in zip(sums[parent], part)]
        key = (c["iso3"], c["level"], parent[2], c["name"])
        sums[key] = part
        composed.add(key)
    out = []
    for key, (lat, x, y, w) in sorted(sums.items()):
        iso, level, *names = key
        parts = [p.strip() for p in names[-1].split("/")]
        out.append({"name": names[-1], "alt_names": parts if len(parts) > 1 else [], "iso3": iso, "level": level,
                    "lat": round(math.degrees(lat / w), 3), "lon": round(math.degrees(math.atan2(y, x)), 3)}
                   | ({"composed": True} if key in composed else {}))
    return out


def accessed(path: Path) -> str:
    return datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()


def stamp_sources() -> None:
    dates = {"gpw-natid": accessed(SEDAC["gpw-natid"]), "gpw-adm-points": accessed(SEDAC["gpw-adm-points"]),
             "power": accessed(CACHE / "merra2-annual" / ".zmetadata")}
    path = ROOT / "data" / "sources.json"
    registry = json.loads(path.read_text())
    for s in registry:
        s["accessed"] = dates.get(s["id"], s["accessed"])
    write(path, registry, indent=2)


def adapt(snapshot: Path) -> None:
    missing = [name for name, path in SEDAC.items() if not path.exists()]
    if missing:
        sys.exit(f"SEDAC grids missing from tools/cache: {', '.join(missing)}. Download them with the Earthdata login.")
    old = json.loads((snapshot / "data" / "catalog.json").read_text())
    own = ownership()
    gaz = gazetteer()
    write(DATA / "gazetteer.json", gaz)
    country = countries(own, snapshot)
    variables = [variable(v) for v in old["variables"]]
    write(DATA / "catalog.json", {
        "years": SRC["years"],
        "variables": variables,
        "places": located(old["places"], gaz),
        "countries": country,
        "groups": groups(old["places"], country, gaz),
        "topics": old["topics"],
    }, indent=1)
    write(DATA / "countries.geojson", {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"id": iso, "name": country[iso]["name"]["en"]}, "geometry": geometry(cells)}
        for iso, cells in own.items()]})

    (DATA / "v").mkdir(exist_ok=True)
    for v in variables:
        f = json.loads((snapshot / "data" / "v" / f"{v['id']}.json").read_text())
        Y, total = yearly(v, snapshot), SRC["stores"][SRC["variables"][v["id"]]["store"]].get("sum", False)
        regions = {r: s for r, s in f["regions"].items() if r.startswith("p.")}
        cells = {r: n for r, n in f["cells"].items() if r.startswith("p.")}
        for iso, cs in own.items():
            s, n = area_series(Y, cs, total)
            if s is not None:
                regions[iso], cells[iso] = series_json(s, v["decimals"] + 2), n
        write(DATA / "v" / f"{v['id']}.json", {"id": v["id"], "years": SRC["years"], "regions": regions, "cells": cells})
        print(f"{v['id']}: {sum(not r.startswith('p.') for r in regions)} countries", flush=True)

    a = json.loads((snapshot / "data" / "audit.json").read_text())
    write(DATA / "audit.json", {
        "frozen": a["frozen"], "note": {"en": a["note"]},
        "claims": [{RENAME.get(k, k): x for k, x in c.items()} for c in a["claims"]],
    }, indent=1)
    stamp_sources()
    extend()


def place_cells(bbox: list[int]) -> np.ndarray:
    s, w, n, e = bbox
    rows, cols = np.arange(s + 90, n + 90), np.arange(w + 180, e + 180) % 360
    return np.sort((rows[:, None] * 360 + cols[None, :]).ravel())


def extend() -> None:
    """Variables the claim desk never had: their text comes from catalog.src.json, their series from yearly()."""
    cat = json.loads((DATA / "catalog.json").read_text())
    have = {v["id"] for v in cat["variables"]}
    own = None
    for vid, add in SRC["variables"].items():
        if vid in have:
            continue
        text = add["text"]
        v = {"id": vid} | text | {"source": text["source"] | {"ids": add["ids"]}} | NEW_FIELDS | \
            {k: x for k, x in add.items() if k not in BUILD_ONLY}
        Y = yearly(v, SNAPSHOT)
        own = own or ownership()
        areas = {p["id"]: place_cells(p["bbox"]) for p in cat["places"]} | own
        regions, cells, total = {}, {}, SRC["stores"][add["store"]].get("sum", False)
        for r, cs in areas.items():
            s, n = area_series(Y, cs, total, add["first_year"])
            if s is not None:
                regions[r], cells[r] = series_json(s, v["decimals"] + 2), n
        write(DATA / "v" / f"{vid}.json", {"id": vid, "years": SRC["years"], "regions": regions, "cells": cells})
        cat["variables"].append(v)
        print(f"{vid}: {sum(not r.startswith('p.') for r in regions)} countries", flush=True)
    for v in cat["variables"]:
        v.update({k: x for k, x in SRC["variables"][v["id"]].items() if k not in BUILD_ONLY})
    write(DATA / "catalog.json", cat, indent=1)
    summary()


def summary() -> None:
    """Per regional variable and country: the trend, its p, and its Benjamini-Hochberg q across countries."""
    out = {}
    for v in json.loads((DATA / "catalog.json").read_text())["variables"]:
        if not v["regional"]:
            continue
        f = json.loads((DATA / "v" / f"{v['id']}.json").read_text())
        years = list(range(f["years"][0], f["years"][1] + 1))
        fits = {}
        for region, values in f["regions"].items():
            if region.startswith("p."):
                continue
            try:
                fits[region] = stats.trend_test(years, values)
            except TooShort:
                pass
        qs = stats.bh([fit.p for fit in fits.values()])
        out[v["id"]] = {region: {"trend_per_decade": round(fit.slope_per_decade, v["decimals"] + 2),
                                 "p": round(fit.p, 6), "q": round(q, 6), "direction": fit.direction}
                        for (region, fit), q in zip(fits.items(), qs)}
    write(DATA / "summary.json", out)


def check(snapshot: Path) -> int:
    c = catalog.load()
    lo, hi = c.years
    fails = []
    registry = {s.id for s in catalog.sources()}
    places = {p.id for p in c.places}
    for v in c.variables:
        fails += [f"{v.id}: unregistered source {i}" for i in v.source.ids if i not in registry]
        if not v.regional:
            continue
        f = json.loads((DATA / "v" / f"{v.id}.json").read_text())
        if tuple(f["years"]) != c.years or any(len(s) != hi - lo + 1 for s in f["regions"].values()):
            fails.append(f"v/{v.id}.json: years or series length differ from the catalog")
        if (missing := places - set(f["regions"])) and v.point_param:  # a grid can lack a place: sst has no inland sea
            fails.append(f"v/{v.id}.json: no series for {sorted(missing)}")
        if unknown := set(f["regions"]) - places - set(c.countries):
            fails.append(f"v/{v.id}.json: unknown regions {sorted(unknown)[:5]}")
    if len(c.variables) != len(SRC["variables"]) or len(c.places) != 43:
        fails.append(f"expected {len(SRC['variables'])} variables and 43 places, got {len(c.variables)} and {len(c.places)}")
    if len(c.countries) < 200:
        fails.append(f"{len(c.countries)} countries, expected at least 200")
    if len(c.groups) != 4:
        fails.append(f"{len(c.groups)} groups, expected 4")
    old = json.loads((snapshot / "data" / "v" / "heat.json").read_text())["regions"]["KHM"]
    new = catalog.regional_values("heat", Country(iso3="KHM"))
    if (gap := max(abs(a - b) for a, b in zip(new, old))) > 0.2:
        fails.append(f"KHM heat differs from the snapshot by up to {gap:.3f} °C, more than 0.2")
    gaz = json.loads((DATA / "gazetteer.json").read_text())
    if (n := sum(e["iso3"] == "KHM" and e["level"] == 1 for e in gaz)) != 25:
        fails.append(f"{n} Cambodian provinces in the gazetteer, expected 25")
    for f in fails:
        print("FAIL", f)
    if not fails:
        print(f"catalog ok: {len(c.variables)} variables, {len(c.places)} places, {len(c.countries)} countries, {len(c.groups)} groups")
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapt", nargs="?", const=SNAPSHOT, type=Path)
    ap.add_argument("--extend", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--points", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.adapt:
        adapt(args.adapt.expanduser())
    elif args.extend:
        extend()
    elif args.summary:
        summary()
    elif args.points:
        points()
    if args.check:
        sys.exit(check(SNAPSHOT))
