import httpx
import pytest
from fastapi.testclient import TestClient

from earthbuddy import analyses, catalog, fixtures, net, power, stats
from earthbuddy.analyses import trend
from earthbuddy.server import app
from earthbuddy.types import QuestionError, Seg, TrendQ
from earthbuddy.words import EN, Words

client = TestClient(app)
POINT = {"kind": "point", "lat": 11.55, "lon": 104.92, "name": "Phnom Penh"}
SIEM_REAP = {"kind": "place", "id": "p.siem-reap"}
STEP_6 = {"place", "variable", "unit", "period", "n_years", "direction", "change_per_decade",
          "change_per_decade_95pct_range", "total_change", "average", "p_value", "certainty", "typical_swing",
          "size_word", "test", "t_test_p", "data_source"}


def run(region, variable) -> dict:
    r = client.post("/api/run", json={"question": {"kind": "trend", "region": region, "variable": variable}})
    assert r.status_code == 200, r.text
    return r.json()


def stub_power(only_last_years: int | None = None) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        body = fixtures.handler(request).json()
        if only_last_years is not None:
            months = body["properties"]["parameter"][request.url.params["parameters"]]
            keep_from = power.last_complete_year() - only_last_years + 1
            for k in months:
                if int(k[:4]) < keep_from:
                    months[k] = fixtures.FILL
        return httpx.Response(200, json=body)

    net.stub(transport=httpx.MockTransport(handle))


def test_point_offline_clear_rise_with_stl_and_cycle():
    stub_power()
    r = run(POINT, "heat")
    assert r["verdict"] == {"key": "trend.clear", "level": "clear"}
    assert r["headline"][:2] == [{"t": "Phnom Penh's average air temperature is ", "hl": False},
                                 {"t": "clearly rising", "hl": True}]
    assert r["facts"]["period"] == f"{catalog.variable('heat').first_year}–{power.last_complete_year()}"
    detail = trend.TrendDetail.model_validate(r["detail"])
    assert r["facts"]["average"] == f"{stats.fmt_level(detail.fit.mean)} °C" and "." in r["facts"]["average"]
    assert detail.decomposition is not None and sum(detail.decomposition.variance_share.values()) == pytest.approx(1)
    assert detail.seasonal_cycle is not None
    assert r["facts"]["peak_month"] == EN[f"month.{detail.seasonal_cycle.peak_month}"]
    assert len(r["charts"]) == 5 and r["tiles"][-1]["id"] == "peak_month"
    assert r["charts"][-1]["compare"] == detail.seasonal_cycle.early


def test_point_rain_months_add_up_to_the_year():
    stub_power()
    r = run(POINT, "rain")
    cycle = r["charts"][-1]
    assert cycle["unit"] == "mm/month"
    late = r["detail"]["annual"][-10:]
    assert sum(cycle["y"]) == pytest.approx(sum(v for _, v in late) / len(late))


def test_country_has_no_decomposition_and_no_network():
    r = run({"kind": "country", "iso3": "KHM"}, "heat")
    assert r["detail"]["decomposition"] is None and r["detail"]["seasonal_cycle"] is None


def test_place_has_no_decomposition_and_no_network():
    r = run(SIEM_REAP, "rain")
    assert r["detail"]["decomposition"] is None and r["detail"]["seasonal_cycle"] is None
    assert r["facts"]["period"] == "2001–2024" and "percent_change" in r["facts"]
    assert r["tiles"][-1]["id"] == "highest_year" and len(r["charts"]) == 1
    assert r["method"][-1]["why"] == EN["step.not_clear.why"]


def test_nine_years_is_too_short_headline():
    r = analyses.run(TrendQ(kind="trend", region=SIEM_REAP, variable="heat", window=(2001, 2009)))
    assert r.verdict.key == "trend.too_short"
    assert r.headline == [Seg(t="Too few years", hl=True), Seg(t=" to judge.")]
    stub_power(only_last_years=9)
    assert run(POINT, "heat")["verdict"]["key"] == "trend.too_short"


def test_seven_years_is_400_window():
    with pytest.raises(QuestionError) as e:
        analyses.run(TrendQ(kind="trend", region=SIEM_REAP, variable="heat", window=(2001, 2007)))
    assert e.value.field == "window"
    stub_power(only_last_years=7)
    r = client.post("/api/run", json={"question": {"kind": "trend", "region": POINT, "variable": "heat"}})
    assert r.status_code == 400 and r.json()["field"] == "window"


def test_facts_cover_docs_06_step_6():
    stub_power()
    point, place = run(POINT, "heat")["facts"], run(SIEM_REAP, "rain")["facts"]
    assert STEP_6 | {"peak_month", "seasonal_share"} <= set(point) and "percent_change" not in point
    assert STEP_6 | {"percent_change"} <= set(place)
    assert all(v is None or type(v) in (str, int, bool) for v in [*point.values(), *place.values()])


@pytest.mark.parametrize("lang", ["en", "km"])
def test_slope_t_test_p_sits_beside_the_mann_kendall_p(lang):
    question = {"kind": "trend", "region": {"kind": "country", "iso3": "KHM"}, "variable": "rain"}
    r = client.post("/api/run", json={"question": question, "lang": lang}).json()
    f = r["facts"]
    assert f["t_test_p"] == stats.fmt_p(r["detail"]["fit"]["t_p"]) != f["p_value"]
    shown = [next(t["note"] for t in r["tiles"] if t["id"] == "sure"),
             next(s["did"] for s in r["method"] if s["title"] == Words(lang)("step.tested.title"))]
    if lang == "en":
        shown.append(client.post("/api/explain", json={"result": r, "audience": "researcher", "lang": lang,
                                                       "ai": False}).json()["short"])
    for text in shown:
        assert f["p_value"] in text and f["t_test_p"] in text, text


def test_a_tied_record_reads_no_clear_change_and_says_why():
    r = run({"kind": "place", "id": "p.cairo"}, "albedo")
    fit = r["detail"]["fit"]
    assert fit["p"] < stats.T.alpha and fit["slope_per_decade"] == 0, "the premise: ties, a small p, a slope of 0"
    assert r["verdict"] == {"key": "trend.unclear", "level": "unclear"}
    assert "".join(s["t"] for s in r["headline"]).startswith("No clear change")
    assert r["detail"]["sure"]["word"] == "cant_tell"
    assert r["notes"] == [Words("en")("note.tied", **r["facts"])]
    assert run(SIEM_REAP, "rain")["notes"] == []
