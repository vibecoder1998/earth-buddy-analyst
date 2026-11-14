import random
import zlib

import httpx
import pytest
from fastapi.testclient import TestClient

from earthbuddy import fixtures, net, reader
from earthbuddy.server import app

client = TestClient(app)
PAIR = ({"kind": "point", "lat": 11.55, "lon": 104.91, "name": "Phnom Penh"},
        {"kind": "point", "lat": 11.56, "lon": 104.92, "name": "Chamkar Mon"})
FAR = {"kind": "point", "lat": 13.36, "lon": 103.86, "name": "Siem Reap"}


def run(question: dict) -> httpx.Response:
    return client.post("/api/run", json={"question": {"kind": "rank", **question}})


def test_countries_top_10_with_no_network():
    r = run({"variable": "heat", "among": "countries", "top_n": 10})
    assert r.status_code == 200, r.text
    d = r.json()["detail"]
    assert len(d["rows"]) == 10 and [x["rank"] for x in d["rows"]] == list(range(1, 11))
    assert [x["value"] for x in d["rows"]] == sorted((x["value"] for x in d["rows"]), reverse=True)
    assert d["tied_with_first"] == sum(x["same_as_leader"] for x in d["rows"])


def _same_cell(request: httpx.Request) -> httpx.Response:
    q = request.url.params
    far = float(q["latitude"]) > 12
    start, end, param = int(q["start"]), int(q["end"]), q["parameters"]
    rng = random.Random(zlib.crc32(f"{far}{param}".encode()))
    monthly = fixtures._monthly(rng, param, start, end, trend_scale=0 if far else 4)
    return httpx.Response(200, json={"header": {"fill_value": fixtures.FILL}, "properties": {"parameter": {param: monthly}}})


def test_same_cell_pair_marks_both_and_ties():
    net.stub(transport=httpx.MockTransport(_same_cell))
    r = run({"variable": "heat", "among": [*PAIR, FAR]})
    assert r.status_code == 200, r.text
    first, second, third = r.json()["detail"]["rows"]
    assert {first["name"], second["name"]} == {"Phnom Penh", "Chamkar Mon"}
    assert first["shares_grid_cell"] and second["shares_grid_cell"] and not third["shares_grid_cell"]
    assert second["same_as_leader"] and not third["same_as_leader"]
    assert any("fall in one grid cell" in n for n in r.json()["notes"])


def test_one_place_list_is_400():
    r = run({"variable": "heat", "among": [FAR]})
    assert r.status_code == 400 and r.json()["field"] == "among"


def test_demo_4_ranks_every_capital_and_says_whether_the_lead_is_clear():
    net.stub(transport=httpx.MockTransport(fixtures.handler))
    q = reader.read("Which Southeast Asian capital is warming fastest?", "en", ai=False).question
    assert q is not None and q.kind == "rank" and q.among == "southeast_asia_capitals"
    r = client.post("/api/run", json={"question": q.model_dump()}).json()
    assert len(r["detail"]["rows"]) == len(r["charts"][0]["rows"]) == 11
    assert r["verdict"]["key"] in ("rank.clear_leader", "rank.tied", "rank.none")
    assert any(n.startswith("Each capital is the NASA POWER grid cell") for n in r["notes"])


@pytest.mark.parametrize("text, metric, order, top_n", [
    ("Top 10 hottest countries", "level", "highest", 10),
    ("Which Southeast Asian capital is getting drier fastest?", "change", "lowest", 11),
    ("Which Cambodian province is warming fastest?", "change", "highest", 25),
])
def test_keyword_reader_fills_metric_order_and_count(text, metric, order, top_n):
    q = reader.read(text, "en", ai=False).question
    assert q is not None and (q.metric, q.order, q.top_n) == (metric, order, top_n)


def test_level_ranks_the_recent_mean():
    r = run({"variable": "hottest", "among": "countries", "metric": "level", "top_n": 5})
    assert r.status_code == 200, r.text
    rows = r.json()["detail"]["rows"]
    assert len(rows) == 5 and all(x["lo"] <= x["value"] <= x["hi"] for x in rows)
