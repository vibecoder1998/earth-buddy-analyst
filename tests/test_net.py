import json

import httpx
import pytest

from earthbuddy import fixtures, net, power, series
from earthbuddy.types import AIFailed, DataSourceError, Point

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


SCHEMA = {"type": "object", "properties": {"kind": {"type": ["string", "null"]}}, "required": ["kind"]}


def model_server(monkeypatch, response: httpx.Response, key: str | None = "k-not-real") -> list[httpx.Request]:
    monkeypatch.setenv("EB_LLM_URL", "https://llm.example.invalid/v1/")
    if key:
        monkeypatch.setenv("EB_LLM_KEY", key)
    else:
        monkeypatch.delenv("EB_LLM_KEY", raising=False)
    monkeypatch.setattr(net, "OFFLINE", False)
    monkeypatch.setattr(net, "_model", None)
    seen: list[httpx.Request] = []
    net.stub(transport=httpx.MockTransport(lambda request: seen.append(request) or response))
    return seen


def completion(content: str, finish_reason: str = "stop") -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"finish_reason": finish_reason,
                                                  "message": {"role": "assistant", "content": content}}]})


def test_ask_model_posts_a_strict_schema_chat_completion(monkeypatch):
    seen = model_server(monkeypatch, completion('{"kind": null}'))
    assert net.ask_model("SYS", "hi", SCHEMA, 2048) == {"kind": None}
    [r] = seen
    body = json.loads(r.content)
    assert (r.method, str(r.url)) == ("POST", "https://llm.example.invalid/v1/chat/completions")
    assert r.headers["authorization"] == "Bearer k-not-real"
    assert body["model"] == net.model_id() and body["max_tokens"] == 2048 and body["temperature"] == 0
    assert body["messages"] == [{"role": "system", "content": "SYS"}, {"role": "user", "content": "hi"}]
    assert body["response_format"] == {"type": "json_schema",
                                       "json_schema": {"name": "reply", "strict": True, "schema": SCHEMA}}


def test_ask_model_sends_no_auth_header_without_a_key(monkeypatch):
    seen = model_server(monkeypatch, completion('{"kind": null}'), key=None)
    net.ask_model("SYS", "hi", SCHEMA, 64)
    assert "authorization" not in seen[0].headers


@pytest.mark.parametrize("response", [
    completion('{"kind": null}', finish_reason="length"),
    completion("I cannot help with that."),
    completion("[1, 2]"),
    httpx.Response(500, json={"error": "boom"}),
    httpx.Response(200, json={"choices": []}),
    httpx.Response(200, text="not json"),
], ids=["truncated", "prose", "not-an-object", "http-500", "no-choices", "body-not-json"])
def test_ask_model_fails_on_a_bad_reply(monkeypatch, response):
    model_server(monkeypatch, response)
    with pytest.raises(AIFailed):
        net.ask_model("SYS", "hi", SCHEMA, 64)


def test_ask_model_fails_without_a_network_call_when_no_server_is_set(monkeypatch):
    seen = model_server(monkeypatch, completion('{"kind": null}'))
    monkeypatch.delenv("EB_LLM_URL")
    assert not net.ai_available()
    with pytest.raises(AIFailed):
        net.ask_model("SYS", "hi", SCHEMA, 64)
    assert seen == []
