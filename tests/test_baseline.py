import httpx
import pytest
from fastapi.testclient import TestClient

from earthbuddy import analyses, fixtures, net, reader
from earthbuddy.analyses.baseline import BaselineDetail
from earthbuddy.server import app
from earthbuddy.stats import T
from earthbuddy.types import BaselineQ

client = TestClient(app)
POINT = {"kind": "point", "lat": 11.55, "lon": 104.92, "name": "Phnom Penh"}


@pytest.fixture(autouse=True)
def offline_power():
    net.stub(transport=httpx.MockTransport(fixtures.handler))


def test_phnom_penh_heat_is_clearly_higher_than_1981_2010():
    r = analyses.run(BaselineQ(kind="baseline", point=POINT, variable="heat"))
    d = BaselineDetail.model_validate(r.detail)
    assert (d.baseline.start, d.baseline.end, d.recent.start) == (1981, 2010, 2011)
    assert d.level.difference > 0 and d.level.p < T.alpha and d.level.level == "clear"
    assert r.verdict.key == "baseline.higher"
    assert [s.t for s in r.headline if s.hl] == ["clearly higher"]
    assert d.pace is not None and r.tiles[-1].id == "pace"
    assert r.charts[0].means == [(1981, 2010, d.baseline.mean), (2011, d.recent.end, d.recent.mean)]


def test_printed_averages_differ_by_the_printed_difference():
    f = analyses.run(BaselineQ(kind="baseline", point=POINT, variable="heat")).facts
    base, recent, diff = (float(str(f[k]).split()[0]) for k in ("baseline_average", "recent_average", "difference"))
    assert diff and abs(recent - base - diff) < 0.02


def test_baseline_2018_2023_is_a_400():
    r = client.post("/api/run", json={"question": {"kind": "baseline", "point": POINT, "variable": "heat",
                                                   "baseline": [2018, 2023]}})
    assert r.status_code == 400 and r.json()["field"] == "baseline"


def test_short_recent_period_skips_the_pace_test():
    last = analyses.run(BaselineQ(kind="baseline", point=POINT, variable="heat")).facts["last_year"]
    r = analyses.run(BaselineQ(kind="baseline", point=POINT, variable="heat", baseline=(1981, last - T.reliable + 1)))
    assert r.detail["pace"] is None and r.tiles[-1].id == "recent_years"
    assert "pace_difference" not in r.facts and r.method[4].title == "Pace not compared"


@pytest.mark.parametrize("text, period", [
    ("Is Phnom Penh hotter than the 1981-2010 average?", [1981, 2010]),
    ("Is Phnom Penh hotter than in the 1980s?", [1980, 1989]),
])
def test_keyword_reader_drafts_a_baseline_at_the_city_centre(text, period):
    r = reader.read(text, "en", ai=False)
    assert r.question is not None and r.question.kind == "baseline"
    assert r.question.point.name == "Phnom Penh" and r.question.variable == "heat"
    assert abs(r.question.point.lat - 11.548) < 0.1 and abs(r.question.point.lon - 104.869) < 0.1
    assert list(r.question.baseline) == period
