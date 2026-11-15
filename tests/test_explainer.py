import json
import logging
import re
import string

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from earthbuddy import analyses, explainer, fixtures, net
from earthbuddy.analyses import ANALYSES
from earthbuddy.server import app
from earthbuddy.types import AIFailed, ClaimQ, Explanation, Question
from earthbuddy.words import EN, HAS_DIGIT, number_tokens

client = TestClient(app)
KHM = ClaimQ(kind="claim", region={"kind": "country", "iso3": "KHM"},
             tests=[{"variable": "heat", "direction": "up"}, {"variable": "rain", "direction": "down"}])
WORD_FACTS = {"region", "place", "noun", "direction", "unmeasured", "clear_measures", "change", "bearing", "ranked_by", "word", "x_noun", "y_noun"}


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
    e = explainer.explain(khm, "policymaker", "en", ai=True)
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


KHM_REGION = {"kind": "country", "iso3": "KHM"}
POINT = {"kind": "point", "lat": 11.55, "lon": 104.92, "name": "Phnom Penh"}
ONE_PER_KIND = {
    "claim": {"kind": "claim", "region": KHM_REGION, "tests": [{"variable": "heat", "direction": "up"}]},
    "trend": {"kind": "trend", "region": KHM_REGION, "variable": "rain"},
    "where": {"kind": "where", "point": POINT, "variable": "heat"},
    "baseline": {"kind": "baseline", "point": POINT, "variable": "heat"},
    "rank": {"kind": "rank", "variable": "heat", "among": "southeast_asia_capitals"},
    "extremes": {"kind": "extremes", "region": KHM_REGION, "variable": "heat"},
    "relate": {"kind": "relate", "region": KHM_REGION, "x": "heat", "y": "rain"},
    "scan": {"kind": "scan", "region": {"kind": "place", "id": "p.phnom-penh"}},   # KHM's rain range ends at 95 by chance
    "fire": {"kind": "fire"},
    "haze": {"kind": "haze"},
    "water": {"kind": "water"},
}
KHMER_REPLY = {"short": "កម្ពុជា **មិនច្បាស់** ថាក្តៅជាង ឬស្ងួតជាងទេ។",
               "more": "ទិន្នន័យ NASA និង p-value មិនអាចប្រាប់បានថាវាកំពុងប្រែប្រួលនោះទេ។"}


def _run(kind: str):
    net.stub(transport=httpx.MockTransport(fixtures.handler))
    return analyses.run(TypeAdapter(Question).validate_python(ONE_PER_KIND[kind]))


def test_one_question_per_kind():
    assert ONE_PER_KIND.keys() == ANALYSES.keys()


@pytest.mark.parametrize("kind", ["scan", "where"])
def test_a_reply_that_names_the_95_percent_range_is_used(kind):
    _model({"short": "The **95% range** shows how sure the slope is.", "more": "See the chart."})
    assert explainer.explain(_run(kind), "researcher", "en", ai=True).via == "ai"


@pytest.mark.parametrize("kind", ONE_PER_KIND)
def test_the_percent_in_a_fact_name_is_itself_a_fact(kind):
    result = _run(kind)
    for n in {m for k in result.facts for m in re.findall(r"(\d+)pct", k)}:
        _model({"short": f"The **{n}% range** is shown.", "more": "See the chart."})
        assert explainer.explain(result, "researcher", "en", ai=True).via == "ai", f"{kind} facts name {n}% but do not hold it"


def test_a_negative_fact_may_be_written_as_its_size(khm):
    assert khm.facts["heat_change_per_decade"] == "−0.13 °C"
    _model({"short": "Heat **fell by 0.13 °C** every ten years.", "more": "That is not clear."})
    assert explainer.explain(khm, "researcher", "en", ai=True).via == "ai"
    _model({"short": "Heat **fell by 0.14 °C** every ten years.", "more": "That is not clear."})
    assert explainer.explain(khm, "researcher", "en", ai=True).via == "template"


@pytest.mark.parametrize("audience", ["student", "policymaker", "researcher"])
def test_every_model_sees_the_headline_and_every_fact(khm, audience):
    calls = _model({"short": "x", "more": "y"})
    explainer.explain(khm, audience, "en", ai=True)
    sent = json.loads(calls[0])
    assert sent["facts"] == khm.facts and sent["headline"] == "".join(s.t for s in khm.headline)


def test_a_student_reply_is_used_only_without_a_number(khm):
    _model({"short": "Cambodia is **not clearly** hotter.", "more": "The record cannot tell."})
    assert explainer.explain(khm, "student", "en", ai=True).via == "ai"
    _model({"short": f"Cambodia is **not clearly** hotter, p-value {khm.facts['rain_p']}.", "more": "The record cannot tell."})
    assert explainer.explain(khm, "student", "en", ai=True).via == "template"


def test_a_student_reply_may_name_the_years_of_the_record(khm):
    first, last = khm.facts["first_year"], khm.facts["last_year"]
    _model({"short": "Cambodia is **not clearly** hotter.", "more": f"The record runs from {first} to {last}."})
    assert explainer.explain(khm, "student", "en", ai=True).via == "ai"
    _model({"short": "Cambodia is **not clearly** hotter.", "more": f"The record starts in {first - 1}."})
    assert explainer.explain(khm, "student", "en", ai=True).via == "template"


def test_each_audience_reads_only_its_own_rule(khm):
    systems = {}

    def fake(system, user, schema, max_tokens):
        systems[json.loads(user)["audience"]] = system
        return json.dumps({"short": "x", "more": "y"})
    net.stub(model=fake)
    for audience in explainer.BRIEFS:
        explainer.explain(khm, audience, "en", ai=True)
    for audience, system in systems.items():
        assert [a for a, b in explainer.BRIEFS.items() if b.rule in system] == [audience]


def test_khmer_needs_a_khmer_reply(khm):
    _model({"short": "Cambodia is **not clearly** hotter.", "more": "The record cannot tell."})
    assert explainer.explain(khm, "student", "km", ai=True).via == "template"
    _model(KHMER_REPLY)
    assert explainer.explain(khm, "student", "km", ai=True) == Explanation(**KHMER_REPLY, via="ai")


def test_the_self_hosted_model_writes_english_only_unless_told(khm, monkeypatch):
    monkeypatch.setenv("EB_LLM", "selfhosted")
    calls = _model(KHMER_REPLY)
    assert explainer.explain(khm, "student", "km", ai=True).via == "template" and calls == []
    assert net.model_writes("en") and not net.model_writes("km")
    monkeypatch.setenv("EB_LLM_LANGS", "en,km")
    assert explainer.explain(khm, "student", "km", ai=True).via == "ai" and len(calls) == 1


def test_bedrock_writes_khmer_and_an_unknown_provider_writes_nothing(monkeypatch):
    assert net.model_writes("km") and net.model_writes("en")
    monkeypatch.setenv("EB_LLM", "pirate")
    assert not net.model_writes("en")


def test_bold_is_kept_on_the_first_three_spans_only(khm):
    _model({"short": "**One** and **two** and **three** and **four** and **five** and **six**.",
            "more": "The record **cannot** tell."})
    e = explainer.explain(khm, "student", "en", ai=True)
    assert e.short == "**One** and **two** and **three** and four and five and six."
    assert e.more == "The record **cannot** tell."


def test_explain_rejects_a_result_whose_facts_cannot_fill_the_template(khm):
    result = khm.model_dump(mode="json") | {"facts": {}}
    r = client.post("/api/explain", json={"result": result, "audience": "student", "lang": "en"})
    assert r.status_code == 400 and r.json()["kind"] == "request" and r.json()["field"] == "result"
