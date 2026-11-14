import httpx
import pytest
from fastapi.testclient import TestClient

from earthbuddy import analyses, fixtures, net, reader
from earthbuddy.analyses.relate import RelateDetail
from earthbuddy.server import app
from earthbuddy.types import QuestionError, RelateQ

client = TestClient(app)
KHM = {"kind": "country", "iso3": "KHM"}


def test_rain_and_soil_in_cambodia_move_together_with_the_shared_model_note():
    r = analyses.run(RelateQ(kind="relate", region=KHM, x="rain", y="soil"))
    d = RelateDetail.model_validate(r.detail)
    assert r.verdict.key == "relate.together" and d.direction == "together" and d.strength == "strong"
    assert "This is a pattern, not proof that one causes the other." in "".join(s.t for s in r.headline)
    assert any("MERRA-2" in n for n in r.notes)
    assert d.effective_years <= d.n_years == 24 and d.x_leads_one_year is not None and not d.short_record
    chart = r.charts[0]
    assert chart.type == "scatter" and [p[2] for p in chart.points] == [str(y) for y in range(2001, 2025)]


def test_satellite_and_reanalysis_pair_has_no_shared_model_note():
    net.stub(transport=httpx.MockTransport(fixtures.handler))
    point = {"kind": "point", "lat": 11.55, "lon": 104.92, "name": "Phnom Penh"}
    r = analyses.run(RelateQ(kind="relate", region=point, x="cloud", y="heat"))
    assert not any("one dataset" in n for n in r.notes)
    assert "pattern" in "".join(s.t for s in r.headline)


@pytest.mark.parametrize("question, field", [
    ({"x": "heat", "y": "heat"}, "y"),
    ({"x": "snow", "y": "rain"}, "x"),
])
def test_bad_pairs_are_400(question, field):
    r = client.post("/api/run", json={"question": {"kind": "relate", "region": KHM, **question}})
    assert r.status_code == 400 and r.json()["field"] == field


def test_fewer_shared_years_than_reliable_is_refused():
    with pytest.raises(QuestionError) as e:
        analyses.run(RelateQ(kind="relate", region=KHM, x="heat", y="rain", window=(2001, 2009)))
    assert e.value.field == "window"


@pytest.mark.parametrize("text, region", [
    ("Does rain relate to heat in Cambodia?", KHM),
    ("Is humidity linked to temperature in Battambang?", None),
])
def test_keyword_reader_drafts_relate(text, region):
    q = reader.read(text, "en", ai=False).question
    assert q is not None and q.kind == "relate" and {q.x, q.y} in ({"heat", "rain"}, {"heat", "humid"})
    assert region is None or q.region.model_dump() == region
