"""The yearly chart views (docs/19) drawn in Node, because the repo has no JS test runner."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).parents[1] / "web"
# A short noisy record: the band is far wider than the years, which is the case the views exist for.
CHART = {"type": "line", "title": "Rain", "unit": "mm", "x": [2001, 2002, 2003, 2004, 2005, 2006],
         "y": [1500, 1300, 1200, 1400, 2400, 1700], "trend": [[2001, 1250], [2006, 1900]],
         "band": [[2001, -400, 2900], [2003, 1300, 1800], [2006, 300, 3500]], "mark_year": 2005}
SCRIPT = """const S = { lang: "en" };
%s
const c = %s;
console.log(JSON.stringify({ plain: line(c).svg, story: line(c, { view: "story" }).svg, range: line(c, { view: "range" }).svg,
  warm: anomaly(c, { warm: true }).svg, cool: anomaly(c, { warm: false }).svg, top: PAD.t, bottom: H - PAD.b }));"""


@pytest.fixture(scope="module")
def drawn():
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    source = "\n".join((WEB / f).read_text() for f in ("i18n.js", "charts.js"))
    out = subprocess.run(["node", "-e", SCRIPT % (source, json.dumps(CHART))], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_no_view_draws_a_broken_number(drawn):
    assert not [k for k, v in drawn.items() if isinstance(v, str) and re.search("NaN|undefined|Infinity", v)]


def test_the_range_lines_stay_inside_the_plot(drawn):
    ys = [float(y) for line in re.findall(r'<line class="maybe"[^>]*>', drawn["range"]) for y in re.findall(r'y[12]="([-\d.]+)"', line)]
    assert len(ys) == 4 and all(drawn["top"] - 0.1 <= y <= drawn["bottom"] + 0.1 for y in ys)


def test_the_band_no_longer_sets_the_scale(drawn):
    assert "-1000" in drawn["plain"] and "-1000" not in drawn["story"] and "-1000" not in drawn["range"]
    assert 'class="band"' not in drawn["story"] and 'class="band"' not in drawn["range"]


def test_a_bar_takes_the_warm_colour_only_on_the_warm_side(drawn):
    above = sum(y >= sum(CHART["y"]) / len(CHART["y"]) for y in CHART["y"])
    assert drawn["warm"].count('class="bar warm"') == above == drawn["cool"].count('class="bar cool"')
    assert drawn["warm"].count("<rect") == len(CHART["x"]) and 'class="mark"' in drawn["warm"]


# The density chart the Fire panel draws (docs/14-web-ui.md, Analyze): counts, so one warm scale and no "clear" outline.
LEVEL = {"type": "cells", "title": "Fire density", "cells": [[12.0, 104.0, 400, False], [12.1, 104.0, 100, False], [12.0, 104.1, 0, False]],
         "cell_size": [0.1, 0.1], "unit": "detections per season", "warm_up": True, "scale": "level"}
LABELLED = {**CHART, "compare": [80, 90, 100, 110, 120, 130], "labels": ["Black carbon", "Fire detections"]}
PANEL_SCRIPT = """const S = { lang: "en" };
%s
const level = cells(%s), labelled = line(%s);
console.log(JSON.stringify({ level: level.svg, levelKeys: level.keys, levelHead: level.head, labelledKeys: labelled.keys,
  quarter: tone(25, 100, false, true), half: tone(50, 100, true), changeDown: tone(-50, 100, true) }));"""


@pytest.fixture(scope="module")
def panel():
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    source = "\n".join((WEB / f).read_text() for f in ("i18n.js", "charts.js", "map.js"))
    out = subprocess.run(["node", "-e", PANEL_SCRIPT % (source, json.dumps(LEVEL), json.dumps(LABELLED))],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_a_level_grid_is_one_warm_scale_shaded_by_the_square_root(panel):
    shades = re.findall(r'class="cell (\w+)" style="--s:(\d+)%"', panel["level"])
    assert shades == [("warm", "100"), ("warm", "50"), ("warm", "0")]
    assert [k for k, _ in panel["levelKeys"]] == ["k-warm"] and "detections per season" in panel["levelKeys"][0][1]
    assert len(panel["levelHead"]) == 3


def test_the_map_shades_a_level_like_the_chart(panel):
    assert panel["quarter"] == panel["half"] != panel["changeDown"]


def test_line_labels_name_both_series_in_the_legend(panel):
    assert [text for _, text in panel["labelledKeys"][:2]] == ["Fire detections", "Black carbon"]


# Line.spans: shaded x-ranges, inclusive, on a yearly, a monthly and a month-of-year line (docs/14-web-ui.md, Charts).
MONTHS = [2001 + i // 12 + round((i % 12 + 0.5) / 12, 3) for i in range(10, 308)]
SPANS = {
    "yearly": {**CHART, "spans": [[2002, 2003], [2005, 2005]], "span_label": "Selected seasons"},
    "monthly": {"type": "line", "title": "Every month", "unit": "detections per month", "x": MONTHS, "y": [(i * 37) % 900 for i in range(len(MONTHS))],
                "spans": [[y + round(10.5 / 12, 3), y + 1 + round(3.5 / 12, 3)] for y in range(2001, 2025)], "span_label": "November to April"},
    "cycle": {"type": "line", "title": "Through the year", "unit": "%", "x": list(range(1, 13)), "y": [150, 160, 140, 90, 60, 40, 35, 40, 50, 70, 110, 140],
              "compare": [130, 150, 150, 100, 50, 30, 30, 30, 40, 60, 100, 120], "labels": ["Soot", "Fire"], "spans": [[1, 4], [11, 12]], "span_label": "November to April"},
}
SPAN_SCRIPT = """const S = { lang: "en" };
%s
const out = {};
for (const [k, c] of Object.entries(%s)) out[k] = { svg: line(c).svg, keys: line(c).keys };
out.anomaly = anomaly(%s, { warm: true });
console.log(JSON.stringify({ ...out, left: PAD.l, right: W - PAD.r }));"""


@pytest.fixture(scope="module")
def spans():
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    source = "\n".join((WEB / f).read_text() for f in ("i18n.js", "charts.js"))
    out = subprocess.run(["node", "-e", SPAN_SCRIPT % (source, json.dumps(SPANS), json.dumps(SPANS["yearly"]))],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def rects(svg):
    return [(float(x), float(w)) for x, w in re.findall(r'<rect class="span" x="([-\d.]+)" y="[-\d.]+" width="([-\d.]+)"', svg)]


@pytest.mark.parametrize("name, n", [("yearly", 2), ("monthly", 24), ("cycle", 2)])
def test_each_span_is_one_band_inside_the_plot_behind_the_series(spans, name, n):
    svg = spans[name]["svg"]
    bands = rects(svg)
    assert len(bands) == n and all(w > 0 and spans["left"] - 0.1 <= x and x + w <= spans["right"] + 0.1 for x, w in bands)
    assert svg.rindex('class="span"') < min(svg.find(m) for m in ('class="series', 'class="dot"') if m in svg)
    assert not re.search("NaN|undefined|Infinity", svg)
    assert ["k-span", SPANS[name]["span_label"]] in spans[name]["keys"]


def test_an_inclusive_span_covers_whole_years_and_whole_months(spans):
    (x0, w0), (x1, w1) = rects(spans["yearly"]["svg"])
    assert w0 == pytest.approx(2 * w1, abs=0.2)  # two years against one
    widths = [w for _, w in rects(spans["monthly"]["svg"])][1:]  # the first starts at the first month, so the edge clips it
    assert max(widths) - min(widths) < 1  # every November to April is six months wide
    (_, a), (_, b) = rects(spans["cycle"]["svg"])
    assert a > b  # January to April against November to December


def test_the_yearly_bars_keep_the_spans(spans):
    assert len(rects(spans["anomaly"]["svg"])) == 2 and ["k-span", "Selected seasons"] in spans["anomaly"]["keys"]
