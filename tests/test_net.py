import httpx
import pytest

from earthbuddy import fixtures, net, power, series
from earthbuddy.types import DataSourceError, Point

PP = Point(lat=11.55, lon=104.92, name="Phnom Penh")


def answer(status: int) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return fixtures.handler(request) if status == 200 else httpx.Response(status, json={"messages": []})

    net.stub(transport=httpx.MockTransport(handle))
    return seen


def test_second_point_call_reads_cache():
    seen = answer(200)
    first = series.get_series(PP, "heat", None)
    second = series.get_series(PP, "heat", None)
    assert len(seen) == 1
    assert not any(s.cached for s in first.sources) and all(s.cached for s in second.sources)
    assert (first.years, first.values) == (second.years, second.values)


def test_503_retries_then_raises_with_url():
    seen = answer(503)
    with pytest.raises(DataSourceError) as e:
        power.point(11.55, 104.92, "T2M", 1981, 1990)
    assert len(seen) == 4
    assert e.value.status == 503 and e.value.url.startswith(power.BASE) and "parameters=T2M" in e.value.url


def test_422_raises_at_once():
    seen = answer(422)
    with pytest.raises(DataSourceError) as e:
        power.point(11.55, 104.92, "T2M", 1981, 1990)
    assert len(seen) == 1 and e.value.status == 422


def test_422_on_the_latest_year_retries_once_with_the_year_before():
    last = power.last_complete_year()
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(422) if request.url.params["end"] == str(last) else fixtures.handler(request)

    net.stub(transport=httpx.MockTransport(handle))
    m = power.point(11.55, 104.92, "T2M", 1981, last)
    assert [r.url.params["end"] for r in seen] == [str(last), str(last - 1)]
    assert m.values[-1][:2] == (last - 1, 12)


def test_fill_values_become_missing():
    def handle(request: httpx.Request) -> httpx.Response:
        months = {"198101": -999.0, "198102": -995.5, "198103": 27.0, "198113": 27.0}
        return httpx.Response(200, json={"header": {"fill_value": -999.0}, "properties": {"parameter": {"T2M": months}}})

    net.stub(transport=httpx.MockTransport(handle))
    assert power.point(11.55, 104.92, "T2M", 1981, 1981).values == [(1981, 1, None), (1981, 2, None), (1981, 3, 27.0)]


def test_transport_error_retries():
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) < 3:
            raise httpx.ConnectError("down", request=request)
        return fixtures.handler(request)

    net.stub(transport=httpx.MockTransport(handle))
    assert power.point(11.55, 104.92, "T2M", 1981, 1981).values
    assert len(calls) == 3


def test_refuses_a_host_outside_the_data_hosts():
    with pytest.raises(ValueError, match="not on an allowed data host"):
        net.get_json("https://api.open-meteo.com/v1/forecast", ttl_days=1, source="power")
