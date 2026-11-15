"""Copy the Fire panel's tables from the branch feat/fire-watch-cambodia into data/firms/ (docs/20-fire.md).

    python tools/firms_copy.py [git ref]

The four tables are copied byte for byte, straight from git, so the same ref always gives the same files.
index.json is written here from the branch's REGIONS, raw_audit.json and verification.json.
Nothing else of the branch is copied.
"""
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "firms"
BRANCH = "feat/fire-watch-cambodia"
FILES = {
    "seasons": "clean-data/fire_season_counts.csv",
    "months": "clean-data/fire_month_counts.csv",
    "provinces": "clean-data/fire_province_season.csv",
    "cells": "data/fire_cells_by_season.json",
}
SOURCES = ["modis-mcd14ml", "modis-fire-paper", "gpw-adm-points"]
SEASON_MONTHS = [11, 12, 1, 2, 3, 4]
# Overpass times have drifted since, and NASA changed the processing version on 2023-01-01,
# so later seasons are not like-for-like with earlier ones (the branch's panel_template.html).
LIKE_FOR_LIKE_UNTIL = 2022
MIN_CONFIDENCE = 30   # percent; the branch's build_fire_watch.py keeps type 0 (vegetation fire) at or above it
RENAME = {"Tboung Khmum": "Tbong Khmum"}   # the branch's spelling -> the one in data/catalog.json
ZONES_KM = {"all": "កម្ពុជាទាំងមូល", "ne": "ភាគឦសាន", "nw": "ភាគខាងជើង និងពាយ័ព្យ", "ts": "ទន្លេសាប និងភាគកណ្តាល",
            "sw": "ភាគនិរតី និងឆ្នេរ", "mk": "វាលទំនាបមេគង្គ"}


def show(ref: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{ref}:fire-watch/{path}"], cwd=ROOT)


def regions(ref: str) -> list[tuple[str, str, list[str]]]:
    tree = ast.parse(show(ref, "tools/build_fire_watch.py"))
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "REGIONS")
    return ast.literal_eval(node.value)


def main(ref: str = BRANCH) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for path in FILES.values():
        (OUT / Path(path).name).write_bytes(show(ref, path))
    raw, checked = json.loads(show(ref, "data/raw_audit.json")), json.loads(show(ref, "data/verification.json"))
    cells = json.loads((OUT / "fire_cells_by_season.json").read_text())
    side = cells["cell"]
    zones = [(key, label.replace("&", "and"), [RENAME.get(p, p) for p in members]) for key, label, members in regions(ref)]
    zones.insert(0, ("all", "All of Cambodia", [p for _, _, members in zones for p in members]))
    index = {
        "copied_from": f"{BRANCH}@{subprocess.check_output(['git', 'rev-parse', '--short', ref], cwd=ROOT, text=True).strip()}",
        "sources": SOURCES,
        "place": {"en": "Cambodia", "km": "កម្ពុជា"},
        "box": [round(min(cells["iy"]) * side, 4), round(min(cells["ix"]) * side, 4),
                round((max(cells["iy"]) + 1) * side, 4), round((max(cells["ix"]) + 1) * side, 4)],
        "season_months": SEASON_MONTHS,
        "seasons": [min(cells["seasons"]), max(cells["seasons"])],
        "like_for_like_until": LIKE_FOR_LIKE_UNTIL,
        "min_confidence": MIN_CONFIDENCE,
        "cell_deg": side,
        "zones": {key: {"name": {"en": label, "km": ZONES_KM[key]}, "provinces": members} for key, label, members in zones},
        "rename": RENAME,
        "audit": {
            "raw_rows": raw["raw_rows"],
            "dropped_type": raw["raw_rows"] - raw["raw_by_type"]["0"],
            "dropped_confidence": raw["type0_low_confidence"],
            "clean_rows": raw["clean_rows"],
            "first": raw["first"],
            "last": raw["last"],
            "checks": checked["checks"],
            "failures": checked["failures"],
        },
        "files": {key: Path(path).name for key, path in FILES.items()},
    }
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} from {index['copied_from']}")


if __name__ == "__main__":
    main(*sys.argv[1:2])
