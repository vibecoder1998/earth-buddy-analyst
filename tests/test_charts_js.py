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
