import httpx
import pytest
from fastapi.testclient import TestClient

from earthbuddy import catalog, fixtures, net, stats
from earthbuddy.analyses import claim
from earthbuddy.server import app
from earthbuddy.words import EN, Words, number_tokens

client = TestClient(app)
KHM = {"kind": "country", "iso3": "KHM"}
PHNOM_PENH = {"kind": "place", "id": "p.phnom-penh"}
POINT = {"kind": "point", "lat": 11.55, "lon": 104.92, "name": "Phnom Penh"}
HOTTER_DRIER = [{"variable": "heat", "direction": "up"}, {"variable": "rain", "direction": "down"}]
EIGHT = ["heat", "rain", "tmax", "tmin", "humid", "wind", "cloud", "fire"]


def run(region, tests, *, revision=0, window=None) -> dict:
    question = {"kind": "claim", "region": region, "tests": tests, "window": window}
    r = client.post("/api/run", json={"question": question, "revision": revision})
    assert r.status_code == 200, r.text
    return r.json()


def _two_rows(r: dict) -> None:
    assert [e["variable"] for e in r["detail"]["evidence"]] == ["heat", "rain"]
    assert r["verdict"]["key"] in claim.VERDICTS
    assert any(s["hl"] for s in r["headline"]) and len(r["tiles"]) == 4


def test_hotter_and_drier_has_two_rows():
    _two_rows(run(KHM, HOTTER_DRIER))


def test_hotter_and_drier_on_a_place_has_two_rows():
    r = run(PHNOM_PENH, HOTTER_DRIER)
    _two_rows(r)
    assert {"heat_change_per_decade", "heat_95pct_range", "heat_p", "heat_outcome", "region", "years", "verdict"} <= set(r["facts"])
    assert all(v is None or type(v) in (str, int, bool) for v in r["facts"].values())
    assert [c["title"] for c in r["charts"]] == ["Heat", "Rain"]


def test_revision_1_shows_second_look():
    assert run(PHNOM_PENH, HOTTER_DRIER, revision=1)["notes"][0] == EN["note.second_look"]


def test_revision_0_does_not():
    assert EN["note.second_look"] not in run(PHNOM_PENH, HOTTER_DRIER)["notes"]


def test_snow_in_cambodia_is_nothing():
    assert run(KHM, [{"variable": "snow", "direction": "any"}])["verdict"]["key"] == "claim.nothing"


def test_snow_in_phnom_penh_is_nothing():
    r = run(PHNOM_PENH, [{"variable": "snow", "direction": "any"}])
    assert r["verdict"] == {"key": "claim.nothing", "level": "too_short"}
    assert r["detail"]["evidence"][0]["final"] == "insufficient"
    assert r["detail"]["counts"]["insufficient"] == 1


def test_detail_round_trips_through_claim_detail():
    detail = run(PHNOM_PENH, HOTTER_DRIER)["detail"]
    assert claim.ClaimDetail.model_validate(detail).model_dump(mode="json") == detail


def test_eight_tests_survive_by_their_own_q():
    r = run(PHNOM_PENH, [{"variable": v, "direction": "up"} for v in EIGHT])
    rows = r["detail"]["evidence"]
    assert len(rows) == 8
    live = [e for e in rows if e["outcome"] != "insufficient"]
    qs = stats.bh([e["fit"]["p"] for e in live])
    assert [e["survives"] for e in live] == [q < stats.T.fdr_q for q in qs]


def test_falling_fire_carries_the_doubt_caveat():
    r = run({"kind": "place", "id": "p.jakarta"}, [{"variable": "fire", "direction": "down"}])
    assert r["detail"]["evidence"][0]["caveat"] == "doubt"
    assert any(n.startswith("Fire:") for n in r["notes"])


def test_claim_text_counts_only_the_parts_the_verdict_used():
    r = run({"kind": "place", "id": "p.jakarta"}, [{"variable": "heat", "direction": "up"},
                                                   {"variable": "snow", "direction": "any"}])
    f = r["facts"]
    assert r["verdict"]["key"] == "claim.supported"
    assert [e["final"] for e in r["detail"]["evidence"]] == ["supported", "insufficient"]
    assert (f["n_tests"], f["n_live"], f["n_supported"], f["n_insufficient"]) == (2, 1, 1, 1)
    w = Words("en")
    allowed = set().union(*(number_tokens(str(v)) for v in f.values() if v is not None))
    texts = {a: w.template("claim.supported", a, f) for a in ("student", "policymaker", "researcher")}
    for short, more in texts.values():
        assert number_tokens(short + " " + more) <= allowed
        assert "could not be measured" in short
    assert texts["policymaker"][0].startswith("Every part of this claim that could be measured holds")
    assert texts["researcher"][0].startswith("1 of 1 measurable tests")
    assert number_tokens(r["method"][1]["did"]) == {"1", "0.1"}


def test_a_point_claim_reads_the_live_record():
    net.stub(transport=httpx.MockTransport(fixtures.handler))
    r = run(POINT, HOTTER_DRIER)
    assert r["detail"]["evidence"][0]["series"]["years"][0] == catalog.variable("heat").first_year
    assert r["method"][-1]["title"] == EN["step.live.title"]
    assert r["tiles"][-1]["value"] == EN["word.one_point"]


def test_a_window_shorter_than_reliable_is_dropped():
    r = run(PHNOM_PENH, HOTTER_DRIER, window=[2001, 2005])
    assert r["question"]["window"] is None and r["facts"]["years"] == "2001–2024"


def test_an_unknown_region_is_a_400_on_region():
    r = client.post("/api/run", json={"question": {"kind": "claim", "region": {"kind": "place", "id": "p.atlantis"},
                                                    "tests": HOTTER_DRIER}, "revision": 0})
    assert r.status_code == 400 and r.json()["field"] == "region"


def test_an_unknown_lang_is_a_400_on_lang():
    r = client.post("/api/run", json={"question": {"kind": "claim", "region": PHNOM_PENH, "tests": HOTTER_DRIER},
                                      "lang": "fr"})
    assert r.status_code == 400 and r.json()["field"] == "lang"


def test_api_catalog_lists_kinds_and_their_fields():
    r = client.get("/api/catalog").json()
    assert r["kinds"]["claim"]["fields"] == [{"name": "region", "required": True, "regions": ["country", "place", "point"]},
                                             {"name": "tests", "required": True},
                                             {"name": "window", "required": False}]
    assert len(r["variables"]) == len(catalog.variables())
