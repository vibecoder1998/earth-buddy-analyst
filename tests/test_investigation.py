"""The investigation block (docs/19): every line is labelled, every number is traceable, every follow-up runs."""
import json
import re

import httpx
import pytest
from fastapi.testclient import TestClient

from earthbuddy import ROOT, analyses, catalog, fixtures, net, reader
from earthbuddy.server import app
from earthbuddy.stats import T
from earthbuddy.types import TrendQ
from earthbuddy.words import number_tokens

client = TestClient(app)
KHM = {"kind": "country", "iso3": "KHM"}
CITY = {"kind": "place", "id": "p.phnom-penh"}
POINT = {"kind": "point", "lat": 11.55, "lon": 104.92, "name": "Phnom Penh"}
BASES = {"measured", "interpretation", "hypothesis", "guidance"}
KHMER = re.compile(r"[ក-៿]")

# One question per kind, and the picture its analysis must choose (None: no picture fits, so none is drawn).
QUESTIONS = {
    "claim": ({"kind": "claim", "region": CITY, "tests": [{"variable": "heat", "direction": "up"}]}, "line"),
    "trend": ({"kind": "trend", "region": KHM, "variable": "rain"}, "line"),
    "relate": ({"kind": "relate", "region": KHM, "x": "heat", "y": "rain"}, "scatter"),
    "rank": ({"kind": "rank", "variable": "heat", "among": "southeast_asia_capitals"}, "intervals"),
    "where": ({"kind": "where", "point": POINT, "variable": "heat"}, "cells"),
    "baseline": ({"kind": "baseline", "point": POINT, "variable": "heat"}, "line"),
    "extremes": ({"kind": "extremes", "region": CITY, "variable": "heat"}, "line"),
    "scan": ({"kind": "scan", "region": KHM}, None),
    "fire": ({"kind": "fire"}, "line"),
    "haze": ({"kind": "haze"}, "line"),
    "water": ({"kind": "water"}, "line"),
}


@pytest.fixture(autouse=True)
def synthetic_power():
    net.stub(transport=httpx.MockTransport(fixtures.handler))


def run(question: dict, lang: str = "en") -> dict:
    r = client.post("/api/run", json={"question": question, "lang": lang})
    assert r.status_code == 200, r.text
    return r.json()


def test_one_question_per_kind():
    assert QUESTIONS.keys() == analyses.ANALYSES.keys()


@pytest.mark.parametrize("kind", QUESTIONS)
def test_the_analysis_chooses_the_picture(kind):
    question, chart = QUESTIONS[kind]
    charts = run(question)["charts"]
    assert (charts[0]["type"] if charts else None) == chart


def test_a_before_and_after_question_draws_both_period_averages():
    assert len(run(QUESTIONS["baseline"][0])["charts"][0]["means"]) == 2


@pytest.mark.parametrize("kind", QUESTIONS)
def test_every_line_says_what_kind_of_claim_it_is(kind):
    r = run(QUESTIONS[kind][0])
    inv = r["investigation"]
    lines = inv["why"] + inv["impact"] + inv["guidance"]
    assert {s["basis"] for s in lines} <= BASES and all(s["text"].strip() for s in lines)
    assert inv["why"][0] == {"basis": "measured", "text": "".join(s["t"] for s in r["headline"])}
    assert [s["basis"] for s in lines].count("measured") == 1, "only the headline is a measurement"
    assert {s["basis"] for s in inv["guidance"]} == {"guidance"}
    assert "measured" not in {s["basis"] for s in inv["impact"]}, "a possible impact is never an observed one"


@pytest.mark.parametrize("kind", QUESTIONS)
def test_validation_names_the_status_and_the_method(kind):
    rows = run(QUESTIONS[kind][0])["investigation"]["validation"]
    ids = [row["id"] for row in rows]
    assert ids[0] in ("status", "level") and ids[1] == "method"
    assert all(row["label"] and row["value"] and row["help"] for row in rows)


@pytest.mark.parametrize("kind", QUESTIONS)
def test_every_number_in_the_investigation_comes_from_the_facts(kind):
    r = run(QUESTIONS[kind][0])
    inv, facts = r["investigation"], r["facts"]
    first, last = facts["first_year"], facts["last_year"]
    allowed = {str(y) for y in range(first, last + 1)} | {str(last - first + 1), str(T.climate_years)}
    for value in facts.values():
        if value is not None and not isinstance(value, bool):
            allowed |= number_tokens(str(value))
    text = " ".join([row["value"] for row in inv["validation"]] + inv["limits"]
                    + [s["text"] for s in inv["why"] + inv["impact"] + inv["guidance"]])
    assert number_tokens(text) <= allowed, number_tokens(text) - allowed


@pytest.mark.parametrize("kind", QUESTIONS)
def test_every_dataset_cites_sources_the_result_lists(kind):
    r = run(QUESTIONS[kind][0])
    listed = {s["id"] for s in r["sources"]}
    asked = {v for v in (r["question"].get(k) for k in ("variable", "x", "y")) if v}
    asked |= {t["variable"] for t in r["question"].get("tests", [])}
    datasets = r["investigation"]["datasets"]
    assert {d["variable"] for d in datasets} == asked
    assert all(d["sources"] and set(d["sources"]) <= listed for d in datasets)
    assert all(d["parameter"] and d["resolution"] and d["coverage"] and d["processing"] for d in datasets)


@pytest.mark.parametrize("kind", ["claim", "trend", "relate", "rank", "extremes"])
def test_every_follow_up_is_a_new_question_that_runs(kind):
    r = run(QUESTIONS[kind][0])
    follow_ups = r["investigation"]["next"]
    assert follow_ups and len({f["id"] for f in follow_ups}) == len(follow_ups)
    for f in follow_ups:
        assert f["question"]["kind"] != kind and f["label"]
        question, _ = reader.question_from({"question": f["question"]})
        assert question.model_dump(mode="json") == f["question"]
    assert run(follow_ups[0]["question"])["investigation"]


def test_no_clear_change_offers_no_impacts_and_says_so():
    r = run(QUESTIONS["trend"][0])
    assert r["verdict"]["level"] == "unclear"
    inv = r["investigation"]
    assert "hypothesis" not in {s["basis"] for s in inv["impact"]}
    assert any("no trend to plan around" in s["text"] for s in inv["impact"])
    assert inv["validation"][0]["value"] == "Not clear: not statistically significant"
    assert {"p_value", "change_per_decade_95pct_range", "sample"} <= {row["id"] for row in inv["validation"]}


def test_a_clear_change_lists_possible_impacts_as_hypotheses_for_that_place():
    r = run({"kind": "trend", "region": POINT, "variable": "heat"})
    assert r["verdict"]["level"] == "clear"
    impact = r["investigation"]["impact"]
    lead = next(i for i, s in enumerate(impact) if "Phnom Penh" in s["text"])
    assert impact[lead]["basis"] == "interpretation" and "None of them was measured here" in impact[lead]["text"]
    assert impact[lead + 1:] and {s["basis"] for s in impact[lead + 1:]} == {"hypothesis"}


def test_too_few_years_is_reported_as_untestable():
    asked = TrendQ(kind="trend", region=catalog.Country(iso3="KHM"), variable="rain", window=(2016, 2024))
    r = analyses.run(asked).model_dump(mode="json")
    inv = r["investigation"]
    assert r["verdict"]["level"] == "too_short"
    assert inv["validation"][0]["value"] == "Too few years to test"
    assert "No conclusion can be drawn yet" in inv["why"][1]["text"]
    assert "hypothesis" not in {s["basis"] for s in inv["impact"]}


def test_a_short_record_is_not_called_a_climate_trend():
    limits = run(QUESTIONS["trend"][0])["investigation"]["limits"]
    assert any("not a long-term climate trend" in line for line in limits)
    long_record = run({"kind": "trend", "region": POINT, "variable": "heat"})
    assert long_record["facts"]["n_years"] >= T.climate_years
    assert not any("climate trend" in line for line in long_record["investigation"]["limits"])


def test_air_temperature_and_surface_temperature_are_told_apart():
    air = run({"kind": "trend", "region": KHM, "variable": "heat"})["investigation"]["limits"]
    skin = run({"kind": "trend", "region": KHM, "variable": "skin"})["investigation"]["limits"]
    assert any("not the land surface temperature" in line for line in air)
    assert any("not the air temperature" in line for line in skin)


def test_a_link_is_never_explained_as_a_cause():
    why = run(QUESTIONS["relate"][0])["investigation"]["why"]
    assert any("does not show that one causes the other" in s["text"] for s in why)
    assert "hypothesis" not in {s["basis"] for s in why}


def test_a_year_far_from_the_trend_is_not_called_a_significance_test():
    first = run(QUESTIONS["extremes"][0])["investigation"]["validation"][0]
    assert first["id"] == "level" and "not a significance test" in first["help"]


def test_scope_never_claims_finer_detail_than_the_grid():
    area = run(QUESTIONS["trend"][0])["investigation"]["scope"]
    point = run({"kind": "trend", "region": POINT, "variable": "heat"})["investigation"]["scope"]
    assert (area["kind"], point["kind"]) == ("country", "point")
    assert str(catalog.cells(catalog.Country(iso3="KHM"))) in area["text"]
    assert "cannot show differences inside" in area["limit"] and "cannot show differences inside" in point["limit"]


def test_khmer_investigation_is_in_khmer():
    inv = run(QUESTIONS["trend"][0], "km")["investigation"]
    texts = [inv["scope"]["text"], inv["scope"]["limit"], *inv["limits"]]
    texts += [s["text"] for s in inv["why"] + inv["impact"] + inv["guidance"]]
    texts += [x for row in inv["validation"] for x in (row["label"], row["help"])]
    texts += [f["label"] for f in inv["next"]] + [d["processing"] for d in inv["datasets"]]
    assert not [t for t in texts if not KHMER.search(t)]


def _strings(node) -> list[dict]:
    if isinstance(node, dict):
        return [node] if "en" in node else [s for v in node.values() for s in _strings(v)]
    return [s for v in node for s in _strings(v)] if isinstance(node, list) else []


def test_context_covers_the_catalog_in_both_languages_without_numbers():
    context = json.loads((ROOT / "data" / "context.json").read_text())
    ids = {v.id for v in catalog.variables()}
    assert {t for v in catalog.variables() for t in v.topics[:1]} <= context["topics"].keys()
    assert context["variables"].keys() <= ids
    assert {r for t in context["topics"].values() for r in t["related"]} <= ids
    assert {v["like"] for v in context["variables"].values() if "like" in v} <= context["variables"].keys()
    lines = _strings({k: v for k, v in context.items() if k != "note"})
    assert lines and all(line.get("en") and KHMER.search(line.get("km", "")) for line in lines)
    assert not [line for line in lines if re.search(r"\d", line["en"] + line["km"])]
    for v in catalog.variables():
        catalog.context(v.id)
