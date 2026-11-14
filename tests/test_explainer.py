import json
import logging
import string

import pytest
from fastapi.testclient import TestClient

from earthbuddy import analyses, explainer, net
from earthbuddy.analyses import ANALYSES
from earthbuddy.server import app
from earthbuddy.types import AIFailed, ClaimQ
from earthbuddy.words import EN, HAS_DIGIT

client = TestClient(app)
KHM = ClaimQ(kind="claim", region={"kind": "country", "iso3": "KHM"},
             tests=[{"variable": "heat", "direction": "up"}, {"variable": "rain", "direction": "down"}])
WORD_FACTS = {"region", "place", "noun", "direction", "unmeasured", "clear_measures", "change", "bearing", "ranked_by"}


@pytest.fixture
def khm():
    return analyses.run(KHM)


def _model(reply) -> list[str]:
    calls = []

    def fake(system, user, schema, max_tokens):
        calls.append(user)
        return reply if isinstance(reply, str) else json.dumps(reply)
    net.stub(model=fake)
    return calls


@pytest.mark.parametrize("key", [k for a in ANALYSES.values() for k in a.verdicts])
def test_every_verdict_key_has_an_english_student_template(key):
    short, more = EN[f"{key}.student.short"], EN[f"{key}.student.more"]
    assert short and more
    assert {f for _, f, _, _ in string.Formatter().parse(short) if f} <= WORD_FACTS, "a student short uses no numbers"


def test_khm_student_answer_has_no_numbers(khm):
    e = explainer.explain(khm, "student", "en", ai=False)
    assert e.via == "template"
    assert not HAS_DIGIT.search(e.short)
    assert e.short.count(". ") + 1 == 2


def test_khm_researcher_names_slope_interval_test_and_p(khm):
    short = explainer.explain(khm, "researcher", "en", ai=False).short
    assert khm.facts["heat_change_per_decade"] in short and khm.facts["heat_95pct_range"] in short
    assert "Mann-Kendall" in short and khm.facts["rain_p"] in short


def test_rejects_0_3_when_facts_hold_0_28():
    assert not explainer.numbers_ok("about 0.3 °C", {"change": "0.28 °C"}, set())


def test_accepts_0_28():
    assert explainer.numbers_ok("about 0.28 °C every ten years", {"change": "0.28 °C"}, set())


def test_accepts_khmer_digits_and_years():
    assert explainer.numbers_ok("០.២៨ since 2003", {"change": "0.28 °C"}, {2003})
    assert not explainer.numbers_ok("since 2030", {"change": "0.28 °C"}, {2003})


def test_minus_sign_counts():
    assert not explainer.numbers_ok("-0.13 °C", {"change": "0.13 °C"}, set())
    assert explainer.numbers_ok("-0.13 °C", {"change": "−0.13 °C"}, set())


def test_invented_number_falls_back_to_template(khm, caplog):
    calls = _model({"short": "Cambodia warmed about 0.3 °C.", "more": "Really."})
    with caplog.at_level(logging.WARNING, logger="earthbuddy.explainer"):
        e = explainer.explain(khm, "student", "en", ai=True)
    assert len(calls) == 1
    assert e == explainer.explain(khm, "student", "en", ai=False)
    assert "about 0.3" in caplog.text


def test_checked_ai_text_is_used(khm):
    calls = _model({"short": "Cambodia is **not clearly** hotter or drier.", "more": f"Rain p-value {khm.facts['rain_p']}."})
    e = explainer.explain(khm, "student", "en", ai=True)
    assert e.via == "ai" and e.short.startswith("Cambodia")
    assert json.loads(calls[0])["facts"] == khm.facts


@pytest.mark.parametrize("reply", ["not json", {"short": 3, "more": "x"}, {"more": "x"}])
def test_bad_reply_falls_back_to_template(khm, reply):
    _model(reply)
    assert explainer.explain(khm, "student", "en", ai=True).via == "template"


def test_model_failure_falls_back_to_template(khm):
    def fail(*_):
        raise AIFailed("timeout")
    net.stub(model=fail)
    assert explainer.explain(khm, "student", "en", ai=True).via == "template"


def test_ai_off_makes_no_model_call(khm):
    r = client.post("/api/explain", json={"result": khm.model_dump(mode="json"), "audience": "policymaker",
                                          "lang": "en", "ai": False})
    assert r.status_code == 200
    assert r.json()["via"] == "template"
    assert r.json()["short"].startswith("The data for Cambodia")


def test_explain_rejects_a_bad_audience(khm):
    r = client.post("/api/explain", json={"result": khm.model_dump(mode="json"), "audience": "pirate"})
    assert r.status_code == 400 and r.json()["field"] == "audience"
