"""Our Cambodia series against independent NASA Giovanni area averages (box 102.5-107.5 E, 10.5-14.5 N)."""
import csv
import json
import statistics

import pytest

from earthbuddy import ROOT, catalog, stats

DIR = ROOT / "data" / "giovanni"
MANIFEST = json.loads((DIR / "index.json").read_text())
MIN_R = 0.95   # a test tolerance, not an app threshold


def giovanni_annual(entry: dict) -> dict[int, float]:
    months: dict[int, list[float]] = {}
    with open(DIR / entry["file"]) as f:
        rows = csv.reader(f)
        for row in rows:
            if row and row[0] == "time":
                break
        for t, value in rows:
            months.setdefault(int(t[:4]), []).append(float(value) * entry["scale"])
    return {y: statistics.fmean(v) for y, v in months.items() if len(v) == 12}


def ours(variable: str) -> dict[int, float]:
    d = json.loads((ROOT / "data" / "v" / f"{variable}.json").read_text())
    return dict(zip(range(d["years"][0], d["years"][1] + 1), d["regions"]["KHM"]))


def test_every_file_is_in_the_manifest_with_registered_sources():
    ids = {s.id for s in catalog.sources()}
    assert sorted(p.name for p in DIR.glob("*.csv")) == sorted(e["file"] for e in MANIFEST)
    assert all(set(e["sources"]) <= ids and "giovanni" in e["sources"] for e in MANIFEST)


CHECKED = [e for e in MANIFEST if e["variable"]]   # variable null: kept for reference, no catalog variable reads it


@pytest.mark.parametrize("entry", CHECKED, ids=[e["variable"] for e in CHECKED])
def test_ours_matches_giovanni(entry):
    g, o = giovanni_annual(entry), ours(entry["variable"])
    years = sorted(set(g) & set(o))
    gv, ov = [g[y] for y in years], [o[y] for y in years]
    fg, fo = stats.trend_test(years, gv), stats.trend_test(years, ov)
    r = statistics.correlation(gv, ov)
    print(f"{entry['variable']}: n {len(years)}, r {r:.3f}, slope/decade Giovanni {fg.slope_per_decade:+.3g} "
          f"ours {fo.slope_per_decade:+.3g}, p {fg.p:.2f} / {fo.p:.2f}")
    assert len(years) == 24
    assert r >= MIN_R
    assert fg.level == fo.level
