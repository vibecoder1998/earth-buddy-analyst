"""Build data/ from the claim-desk snapshot and NASA data (docs/01-catalog-and-data.md).

  .venv/bin/python tools/build_catalog.py --adapt [SNAPSHOT]
  .venv/bin/python tools/build_catalog.py --check
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from earthbuddy import catalog  # noqa: E402

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
NEW_FIELDS = {"regional": True, "per_day": False, "season": None, "point_scale": 1}


def write(path: Path, obj, indent: int | None = None) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=indent, separators=None if indent else (",", ":")) + "\n")


def variable(v: dict) -> dict:
    add = SRC["variables"][v["id"]]
    out = {RENAME.get(k, k): x for k, x in v.items() if k not in DROP}
    out["source"] = {k: v["source"][k] for k in ("param", "kind", "resolution")} | {"ids": add["ids"]}
    out.setdefault("doubt", None)
    return out | NEW_FIELDS | {k: x for k, x in add.items() if k != "ids"}


def groups(places: list[dict], countries: dict) -> list[dict]:
    members = {"countries": [{"kind": "country", "iso3": iso} for iso in countries],
               "places": [{"kind": "place", "id": p["id"]} for p in places]}
    return [{k: g[k] for k in ("id", "name", "aliases", "note")} | {"members": members[g["id"]]}
            for g in SRC["groups"] if g["id"] in members]


def adapt(snapshot: Path) -> None:
    old = json.loads((snapshot / "data" / "catalog.json").read_text())
    countries: dict = {}
    write(DATA / "catalog.json", {
        "years": SRC["years"],
        "variables": [variable(v) for v in old["variables"]],
        "places": old["places"],
        "countries": countries,
        "groups": groups(old["places"], countries),
        "topics": old["topics"],
    }, indent=1)

    (DATA / "v").mkdir(exist_ok=True)
    for v in old["variables"]:
        f = json.loads((snapshot / "data" / "v" / f"{v['id']}.json").read_text())
        write(DATA / "v" / f"{v['id']}.json", {
            "id": v["id"], "years": SRC["years"],
            "regions": {r: s for r, s in f["regions"].items() if r.startswith("p.")},
            "cells": {r: n for r, n in f["cells"].items() if r.startswith("p.")},
        })

    a = json.loads((snapshot / "data" / "audit.json").read_text())
    write(DATA / "audit.json", {
        "frozen": a["frozen"], "note": {"en": a["note"]},
        "claims": [{RENAME.get(k, k): x for k, x in c.items()} for c in a["claims"]],
    }, indent=1)
    write(DATA / "summary.json", {})

    missing = [name for name, path in SEDAC.items() if not path.exists()]
    if missing:
        print(f"SEDAC grids missing from tools/cache: {', '.join(missing)}. "
              "Countries, country series, countries.geojson, gazetteer.json, and the two point groups are not built.")


def check() -> int:
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
        if missing := places - set(f["regions"]):
            fails.append(f"v/{v.id}.json: no series for {sorted(missing)}")
        if unknown := set(f["regions"]) - places - set(c.countries):
            fails.append(f"v/{v.id}.json: unknown regions {sorted(unknown)[:5]}")
    if len(c.variables) != 27 or len(c.places) != 43:
        fails.append(f"expected 27 variables and 43 places, got {len(c.variables)} and {len(c.places)}")
    if len(c.countries) < 200:
        fails.append(f"{len(c.countries)} countries, expected at least 200 (needs the SEDAC grids)")
    if len(c.groups) != 4:
        fails.append(f"{len(c.groups)} groups, expected 4 (the point groups need the SEDAC gazetteer)")
    for f in fails:
        print("FAIL", f)
    if not fails:
        print(f"catalog ok: {len(c.variables)} variables, {len(c.places)} places, {len(c.countries)} countries, {len(c.groups)} groups")
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapt", nargs="?", const=SNAPSHOT, type=Path)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.adapt:
        adapt(args.adapt.expanduser())
    if args.check:
        sys.exit(check())
