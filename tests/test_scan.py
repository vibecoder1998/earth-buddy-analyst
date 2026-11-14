from fastapi.testclient import TestClient

from earthbuddy import catalog, reader
from earthbuddy.server import app

client = TestClient(app)
KHM = {"kind": "country", "iso3": "KHM"}


def scan(region: dict) -> dict:
    r = client.post("/api/run", json={"question": {"kind": "scan", "region": region}})
    assert r.status_code == 200, r.text
    return r.json()


def test_khm_scan_has_27_rows_sorted_by_p_with_q():
    rows = scan(KHM)["detail"]["rows"]
    assert len(rows) == len(catalog.variables()) == 27
    assert [r["p"] for r in rows] == sorted(r["p"] for r in rows)
    assert all(r["p"] <= r["q"] <= 1 for r in rows)


def test_headline_counts_the_rows_that_survive():
    r = scan({"kind": "place", "id": "p.mekong-delta"})
    n = sum(row["survives"] for row in r["detail"]["rows"])
    assert "".join(s["t"] for s in r["headline"]).startswith(f"{n} of 27 measures in Mekong Delta show a clear change")


def test_a_point_is_not_a_scan_region():
    point = {"kind": "point", "lat": 11.55, "lon": 104.92, "name": "Phnom Penh"}
    r = client.post("/api/run", json={"question": {"kind": "scan", "region": point}})
    assert r.status_code == 400 and r.json()["field"] == "region"


def test_trying_a_row_as_a_claim_shows_the_second_look_note():
    row = scan(KHM)["detail"]["rows"][0]
    claim = {"kind": "claim", "region": KHM, "tests": [{"variable": row["variable"], "direction": row["observed"]}]}
    r = client.post("/api/run", json={"question": claim, "revision": 1, "via": "form"})
    assert r.status_code == 200 and r.json()["notes"][0].startswith("You changed this after seeing results.")


def test_khmer_scan_sentence_reads_as_a_scan():
    q = reader.read("អ្វីកំពុងផ្លាស់ប្តូរនៅដីសណ្តទន្លេមេគង្គ", "km").question
    assert q is not None and q.kind == "scan" and q.region.id == "p.mekong-delta"
