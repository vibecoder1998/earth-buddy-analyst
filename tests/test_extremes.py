import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from earthbuddy import analyses, fixtures, net, reader, series, stats
from earthbuddy.analyses.extremes import ExtremesDetail
from earthbuddy.server import app
from earthbuddy.stats import T
from earthbuddy.types import Country, ExtremesQ, Series

client = TestClient(app)
KHM = {"kind": "country", "iso3": "KHM"}
YEARS = list(range(2001, 2025))


def synthetic(monkeypatch, values: list[float]) -> None:
    sources = series.get_series(Country(iso3="KHM"), "heat", None).sources
    monkeypatch.setattr(series, "get_series", lambda region, variable, window: Series(
        region=region, variable=variable, years=YEARS, values=values, cells=1, sources=sources))


def test_last_year_three_swings_above_the_trend_is_exceptional(monkeypatch):
    values = list(0.03 * np.arange(24) + np.random.default_rng(5).normal(0, 0.2, 24))
    fit = stats.trend_test(YEARS, values)
    values[-1] = stats.sen_at(fit, 2024) + 3 * fit.swing
    synthetic(monkeypatch, values)
    r = analyses.run(ExtremesQ(kind="extremes", region=KHM, variable="heat"))
    d = ExtremesDetail.model_validate(r.detail)
    assert d.focus.year == 2024 and d.focus.word == "exceptional" and d.focus.times_normal >= T.exceptional
    assert d.focus.rank_high == 1 and r.verdict.key == "extremes.record_high"
    assert [s.t for s in r.headline if s.hl] == ["record high", "exceptional"]


def test_printed_year_and_trend_values_differ_by_the_printed_deviation(monkeypatch):
    values = list(27 + 0.03 * np.arange(24) + np.random.default_rng(5).normal(0, 0.2, 24))
    fit = stats.trend_test(YEARS, values)
    values[-1] = stats.sen_at(fit, 2024) + 3 * fit.swing
    synthetic(monkeypatch, values)
    f = analyses.run(ExtremesQ(kind="extremes", region=KHM, variable="heat")).facts
    year, trend, dev = (float(str(f[k]).split()[0]) for k in ("year_value", "trend_value", "deviation"))
    assert dev and abs(year - trend - dev) < 0.02


def test_trendless_series_does_not_cluster(monkeypatch):
    synthetic(monkeypatch, list(np.random.default_rng(11).normal(27, 0.3, 24)))
    d = ExtremesDetail.model_validate(analyses.run(ExtremesQ(kind="extremes", region=KHM, variable="heat")).detail)
    assert d.clustering.highest.chance > 0.05 and d.clustering.lowest.chance > 0.05
    assert [x.value for x in d.highest] == sorted((x.value for x in d.highest), reverse=True)
    assert len(d.highest) == len(d.lowest) == T.extremes_listed


def test_a_steady_rise_is_ordinary_against_its_own_trend(monkeypatch):
    synthetic(monkeypatch, [0.1 * i + (-1) ** i * 0.05 for i in range(24)])
    r = analyses.run(ExtremesQ(kind="extremes", region=KHM, variable="heat"))
    assert r.detail["focus"]["rank_high"] == 1 and r.detail["focus"]["word"] == "ordinary"
    assert r.detail["clustering"]["highest"]["chance"] < T.alpha and "highest years fall" in r.facts["cluster"]


def test_point_rain_tests_each_month_through_bh_and_times_the_season():
    net.stub(transport=httpx.MockTransport(fixtures.handler))
    point = {"kind": "point", "lat": 11.55, "lon": 104.92, "name": "Phnom Penh"}
    r = analyses.run(ExtremesQ(kind="extremes", region=point, variable="rain"))
    d = ExtremesDetail.model_validate(r.detail)
    assert [m.month for m in d.months] == list(range(1, 13))
    assert [m.q for m in d.months] == pytest.approx(stats.bh([m.p for m in d.months]))
    assert d.timing is not None and 0 <= d.timing.centre_day < 365
    assert r.charts[1].type == "intervals" and len(r.charts[1].rows) == 12


def test_a_year_outside_the_record_is_a_400():
    r = client.post("/api/run", json={"question": {"kind": "extremes", "region": KHM, "variable": "heat", "year": 1990}})
    assert r.status_code == 400 and r.json()["field"] == "year"


@pytest.mark.parametrize("text, region, year", [
    ("What was the hottest year in Cambodia?", KHM, None),
    ("Was 2024 an extreme year for heat in Phnom Penh?", {"kind": "place", "id": "p.phnom-penh"}, 2024),
])
def test_keyword_reader_drafts_extremes(text, region, year):
    q = reader.read(text, "en").question
    assert q is not None and q.kind == "extremes" and q.variable == "heat"
    assert q.region.model_dump() == region and q.year == year
