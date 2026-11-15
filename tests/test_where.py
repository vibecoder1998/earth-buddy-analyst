import httpx
import pytest
from fastapi.testclient import TestClient

from earthbuddy import fixtures, net
from earthbuddy.server import app
from earthbuddy.stats import T
from earthbuddy.words import EN

client = TestClient(app)
PHNOM_PENH = {"kind": "point", "lat": 11.55, "lon": 104.92, "name": "Phnom Penh"}


@pytest.fixture
def seen() -> list[httpx.Request]:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return fixtures.handler(request)

    net.stub(transport=httpx.MockTransport(handle))
    return requests


def where(point: dict, variable: str = "heat") -> httpx.Response:
    return client.post("/api/run", json={"question": {"kind": "where", "point": point, "variable": variable}})


def test_offline_cells_cover_box_and_counts_sum(seen):
    r = where(PHNOM_PENH)
    assert r.status_code == 200, r.text
    d = r.json()["detail"]
    lat_min, lat_max, lon_min, lon_max = d["box"]
    assert d["box"] == [9.5, 13.5, 103, 107]
    dlat, dlon = d["cell_size"]
    lats, lons = {c["lat"] for c in d["cells"]}, {c["lon"] for c in d["cells"]}
    assert (min(lats), max(lats)) == (lat_min, lat_max)
    assert lon_min <= min(lons) < lon_min + dlon and lon_max - dlon < max(lons) <= lon_max
    assert len(d["cells"]) == len(lats) * len(lons)
    c = d["counts"]
    assert c["rising"] + c["falling"] + c["flat"] == c["total"] == len(d["cells"])
    assert c["clear"] == sum(x["clear"] for x in d["cells"]) <= c["raw"]
    assert all(x["q"] >= x["p"] for x in d["cells"])
    assert len(r.json()["charts"][0]["cells"]) == c["total"]
    [request] = seen
    assert request.url.path.endswith("/regional") and request.url.params["parameters"] == "T2M"


def test_latitude_89_clamps_and_returns_cells(seen):
    r = where({"kind": "point", "lat": 89, "lon": 10, "name": "Near the pole"})
    assert r.status_code == 200, r.text
    d = r.json()["detail"]
    assert d["box"] == [90 - T.where_box, 90, 8, 12]
    assert d["cells"] and all(x["lat"] <= 90 for x in d["cells"])


def test_variable_without_point_param_is_400(seen):
    r = where(PHNOM_PENH, "fire")
    assert r.status_code == 400 and r.json()["field"] == "variable"
    assert not seen


def test_method_checks_every_cell_together(seen):
    r = where(PHNOM_PENH).json()
    *_, field = r["method"]
    assert field["title"] == EN["step.field_fdr.title"]
    assert "With 63 cells, about 3 can look clear by chance" in field["why"]
    assert r["verdict"]["key"] == ("where.clear" if r["detail"]["counts"]["clear"] else "where.chance")


def test_map_files_are_served_and_the_cache_is_not():
    assert client.get("/data/countries.geojson").json()["type"] == "FeatureCollection"
    khm = client.get("/data/summary.json").json()["heat"]["KHM"]
    assert khm["clear"] == (khm["q"] < T.fdr_q)
    assert client.get("/data/cache.sqlite").status_code == 404
