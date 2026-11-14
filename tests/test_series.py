import httpx
import pytest

from earthbuddy import catalog, fixtures, net, power, series
from earthbuddy.catalog import DATA
from earthbuddy.types import Country, Place, Point, QuestionError

PP = Point(lat=11.55, lon=104.92, name="Phnom Penh")
SEDAC = pytest.mark.skipif(not (DATA / "countries.geojson").exists(),
                           reason="EB-03 phase B: country series need the NASA SEDAC grids (Earthdata login)")


def synthetic() -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return fixtures.handler(request)

    net.stub(transport=httpx.MockTransport(handle))
    return seen


def constant(value: float) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        q = request.url.params
        months = {f"{y}{m:02d}": value for y in range(int(q["start"]), int(q["end"]) + 1) for m in range(1, 14)}
        return httpx.Response(200, json={"header": {"fill_value": -999.0},
                                         "properties": {"parameter": {q["parameters"]: months}}})

    net.stub(transport=httpx.MockTransport(handle))


@SEDAC
def test_country_reads_file_with_no_network():
    s = series.get_series(Country(iso3="KHM"), "heat", None)
    assert len(s.values) == 24 and s.monthly is None


def test_place_reads_file_with_no_network():
    s = series.get_series(Place(id="p.phnom-penh"), "heat", None)
    assert (s.years[0], s.years[-1], len(s.values)) == (2001, 2024, 24)
    assert s.monthly is None and s.cells == 1


def test_point_offline_keeps_monthly():
    seen = synthetic()
    s = series.get_series(PP, "heat", None)
    last = power.last_complete_year()
    assert s.years == list(range(1981, last + 1))
    assert len(s.monthly) == 12 * len(s.years)
    assert len(seen) == 1 and seen[0].url.params["parameters"] == "T2M"


def test_point_soil_is_percent():
    synthetic()
    s = series.get_series(PP, "soil", None)
    assert all(40 < v < 80 for v in s.values)


def test_constant_one_mm_per_day_gives_365_or_366():
    constant(1.0)
    s = series.get_series(PP, "rain", None)
    assert all(v == (366 if y % 4 == 0 else 365) for y, v in zip(s.years, s.values))


def test_rain_dry_counts_nov_dec_toward_next_year():
    monthly = [(y, m, 10.0 if (y, m) in {(1981, 11), (1981, 12)} else 1.0) for y in (1981, 1982, 1983) for m in range(1, 13)]
    years, values = series.annualise(monthly, catalog.variable("rain_dry"))
    assert years == [1982, 1983]
    assert values == [10 * 30 + 10 * 31 + 31 + 28 + 31 + 30, 30 + 31 + 31 + 28 + 31 + 30]


def test_incomplete_year_inside_the_record_is_none():
    monthly = [(y, m, None if (y, m) == (1982, 6) else 1.0) for y in (1981, 1982, 1983) for m in range(1, 13)]
    assert series.annualise(monthly, catalog.variable("heat")) == ([1981, 1982, 1983], [1.0, None, 1.0])


def test_hottest_is_the_warmest_month():
    monthly = [(2001, m, float(m)) for m in range(1, 13)]
    assert series.annualise(monthly, catalog.variable("hottest")) == ([2001], [12.0])


def test_window_clips_and_outside_record_is_400_window():
    s = series.get_series(Place(id="p.phnom-penh"), "heat", (1990, 2005))
    assert s.years == list(range(2001, 2006))
    with pytest.raises(QuestionError) as e:
        series.get_series(Place(id="p.phnom-penh"), "heat", (1990, 1995))
    assert e.value.field == "window"


def test_no_point_param_is_400():
    with pytest.raises(QuestionError) as e:
        series.get_series(PP, "fire", None)
    assert (e.value.field, str(e.value)) == ("variable", "no-point-data")


def test_every_series_has_registry_sources():
    synthetic()
    registry = {s.id: s for s in catalog.sources()}
    for v in catalog.variables():
        got = [series.get_series(Place(id="p.phnom-penh"), v.id, None)]
        if v.point_param:
            got.append(series.get_series(PP, v.id, None))
            assert "power" in {s.id for s in got[-1].sources}, v.id
        for s in got:
            assert s.sources and all(registry[x.id].model_copy(update={"cached": x.cached}) == x for x in s.sources), v.id
