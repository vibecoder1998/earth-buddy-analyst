import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from earthbuddy import catalog, geocode, net, reader
from earthbuddy.analyses import ANALYSES
from earthbuddy.server import app
from earthbuddy.types import AIFailed, QuestionError

client = TestClient(app)
PHNOM_PENH = {"kind": "place", "id": "p.phnom-penh"}
HEAT_UP_RAIN_DOWN = [{"variable": "heat", "direction": "up"}, {"variable": "rain", "direction": "down"}]
NULLS = {k: None for k in ("kind", "region_id", "place_name", "window_from", "window_to", "year", "among",
                           "metric", "order")} | {"tests": [], "places": [], "leads": [], "unmapped": []}


@pytest.fixture
def gazetteer(tmp_path, monkeypatch):
    path = tmp_path / "gazetteer.json"
    path.write_text(json.dumps([{"name": "Batdorf", "alt_names": [], "iso3": "KHM", "level": 1,
                                 "lat": 13.03, "lon": 102.99}]))
    monkeypatch.setattr(geocode, "GAZETTEER", path)
    geocode._gazetteer.cache_clear()
    yield
    geocode._gazetteer.cache_clear()


def _model(reply: str):
    calls = []

    def model(system, user, schema, max_tokens):
        calls.append(user)
        return reply
    net.stub(model=model)
    return calls


@pytest.mark.parametrize("text, fields", [
    ("Cambodia is getting hotter and drier",
     {"kind": "claim", "region": {"kind": "country", "iso3": "KHM"}, "tests": HEAT_UP_RAIN_DOWN}),
    ("How is rain changing in Siem Reap?",
     {"kind": "trend", "region": {"kind": "place", "id": "p.siem-reap"}, "variable": "rain"}),
    ("Where around Phnom Penh is it warming?",
     {"kind": "where", "point": {"kind": "point", "lat": 11.5, "lon": 104.5, "name": "Phnom Penh"}, "variable": "heat"}),
    ("Which Southeast Asian capital is warming fastest?",
     {"kind": "rank", "variable": "heat", "among": "southeast_asia_capitals", "top_n": 11}),
    ("What is changing in the Mekong Delta?", {"kind": "scan", "region": {"kind": "place", "id": "p.mekong-delta"}}),
])
def test_demo_sentences_parse_without_edits(text, fields):
    r = reader.read(text, "en", ai=False)
    assert r.draft.fields == fields
    assert r.missing == [] and not r.ai_failed and r.draft.via == "keywords"
    built = fields["kind"] in ANALYSES
    assert (r.question is not None) == built, "kinds without an analysis read into the card but do not run yet"


def test_rank_reads_kind_variable_and_group_now():
    r = reader.read("Top 5 places warming fastest", "en", ai=False)
    assert r.draft.fields == {"kind": "rank", "variable": "heat", "among": "places", "top_n": 5}
    assert r.missing == []


@pytest.mark.parametrize("text, variable", [
    ("Top 10 hottest countries", "heat"),
    ("Which province is hottest?", "heat"),
    ("Which country has the hottest days?", "hottest"),
])
def test_rank_reads_hottest_as_average_heat_unless_a_time_is_named(text, variable):
    assert reader.read(text, "en", ai=False).draft.fields["variable"] == variable


SIEM_REAP = {"kind": "place", "id": "p.siem-reap"}


@pytest.mark.parametrize("kind, kept", [
    ("trend", {"region": SIEM_REAP}),
    ("scan", {"region": SIEM_REAP}),
    ("where", {"point": {"kind": "point", "lat": 13.5, "lon": 103.5, "name": "Siem Reap"}}),
    ("rank", {}),
])
def test_card_kind_switch_through_the_api_fits_a_place_to_the_new_kind(kind, kept):
    draft = {"fields": {"kind": kind, "region": SIEM_REAP, "variable": "heat"}, "via": "form"}
    fields = client.post("/api/read", json={"draft": draft, "lang": "en"}).json()["draft"]["fields"]
    assert {k: v for k, v in fields.items() if k in ("region", "point")} == kept


def test_hotter_and_drier():
    r = reader.read("Cambodia is getting hotter and drier", "en", ai=False)
    assert r.question.model_dump() == {"kind": "claim", "region": {"kind": "country", "iso3": "KHM"},
                                       "tests": HEAT_UP_RAIN_DOWN, "window": None}


def test_hotter_and_drier_on_a_place():
    r = reader.read("Phnom Penh is getting hotter and drier", "en", ai=False)
    assert r.question.model_dump() == {"kind": "claim", "region": PHNOM_PENH, "tests": HEAT_UP_RAIN_DOWN, "window": None}


def test_a_shared_direction_word_follows_the_named_variable():
    tests = reader.read_keywords("Soil in Siem Reap is getting drier", "en")["tests"]
    assert tests == [{"variable": "soil", "direction": "down"}]


def test_ukraine_is_not_rain():
    r = reader.read("Is it raining less in Ukraine?", "en", ai=False)
    assert r.draft.fields == {"kind": "trend", "region": {"kind": "country", "iso3": "UKR"}, "variable": "rain"}


def test_rain_is_read_in_raining_but_not_in_ukraine():
    assert reader.read_keywords("Ukraine is a nation", "en")["tests"] == []
    assert reader.read_keywords("Is it raining less in Ukraine?", "en")["tests"] == [{"variable": "rain", "direction": "any"}]


def test_khmer_claim_on_cambodia():
    r = reader.read("កម្ពុជាកាន់តែក្តៅឡើង", "km", ai=False)
    assert r.question.model_dump() == {"kind": "claim", "region": {"kind": "country", "iso3": "KHM"},
                                       "tests": [{"variable": "heat", "direction": "up"}], "window": None}


def test_khmer_claim_and_khmer_digits_on_a_place():
    r = reader.read("ភ្នំពេញកាន់តែក្តៅឡើងចាប់តាំងពីឆ្នាំ២០១០", "km", ai=False)
    assert r.question.model_dump() == {"kind": "claim", "region": PHNOM_PENH,
                                       "tests": [{"variable": "heat", "direction": "up"}], "window": (2010, 2024)}


def test_windows():
    assert reader.read("Phnom Penh is getting hotter from 2005 to 2020", "en", False).draft.fields["window"] == [2005, 2020]
    assert "window" not in reader.read("Phnom Penh is getting hotter between 2001 and 2005", "en", False).draft.fields
    assert "window" not in reader.read("Phnom Penh is getting hotter since 1970", "en", False).draft.fields


def test_guard_drops_digit_lead_unknown_variable_ninth_test_and_clamps_revision():
    ids = [v.id for v in catalog.variables()][:9]
    raw = {"kind": "claim", "region": PHNOM_PENH, "revision": 500,
           "tests": [{"variable": "nope", "direction": "up"}, *({"variable": v, "direction": "up"} for v in ids)],
           "leads": ["sea level", "3 floods", "x" * 81, "crop yields", "typhoons", "fifth"],
           "unmapped": ["១០ words"]}
    d = reader.guard(raw, "q", "form")
    assert [t["variable"] for t in d.fields["tests"]] == ids[:8]
    assert d.leads == ["sea level", "crop yields", "typhoons"]
    assert d.unmapped == []
    assert d.revision == 99
    assert reader.guard(raw, "q", "ai").revision == 0, "a model reply cannot claim a revision"
    assert reader.guard("not a dict", "q", "link").fields == {"kind": "trend"}


def test_reread_through_the_api_drops_unknown_variable_and_clamps_revision():
    draft = {"fields": {"kind": "claim", "region": PHNOM_PENH,
                        "tests": [{"variable": "nope", "direction": "up"}, {"variable": "heat", "direction": "up"}]},
             "quote": "x", "via": "form", "revision": 500}
    r = client.post("/api/read", json={"draft": draft, "lang": "en"}).json()
    assert r["draft"]["fields"]["tests"] == [{"variable": "heat", "direction": "up"}]
    assert r["draft"]["revision"] == 99 and r["draft"]["via"] == "form"


def test_card_kind_switch_keeps_what_the_new_kind_uses():
    r = reader.reread({"fields": {"kind": "where", "region": PHNOM_PENH, "tests": HEAT_UP_RAIN_DOWN}}, "en")
    assert r.draft.fields == {"kind": "where", "point": {"kind": "point", "lat": 11.5, "lon": 104.5, "name": "Phnom Penh"},
                              "variable": "heat"}


def test_question_from_names_the_missing_field():
    q, revision = reader.question_from({"question": {"kind": "trend", "region": PHNOM_PENH, "variable": "heat"},
                                        "revision": 3})
    assert (q.kind, revision) == ("trend", 3)
    with pytest.raises(QuestionError) as e:
        reader.question_from({"question": {"kind": "trend", "region": PHNOM_PENH, "variable": "nope"}})
    assert e.value.field == "variable"


def test_bad_model_json_falls_back_to_keywords():
    _model("{not json")
    text = "Phnom Penh is getting hotter and drier"
    r = reader.read(text, "en", ai=True)
    assert r.ai_failed and r.draft.via == "keywords"
    assert r.question == reader.read(text, "en", ai=False).question


AWS_CREDENTIALS = ("AWS_BEARER_TOKEN_BEDROCK", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")


@pytest.mark.parametrize("env, available", [
    ({}, False),
    ({"AWS_ACCESS_KEY_ID": "id-not-real"}, False),
    ({"AWS_SECRET_ACCESS_KEY": "secret-not-real"}, False),
    ({"AWS_ACCESS_KEY_ID": "id-not-real", "AWS_SECRET_ACCESS_KEY": "secret-not-real"}, True),
    ({"AWS_BEARER_TOKEN_BEDROCK": "token-not-real"}, True),
])
def test_ai_is_available_only_with_aws_credentials(monkeypatch, env, available):
    monkeypatch.setattr(net, "OFFLINE", False)
    for k in AWS_CREDENTIALS:
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert net.ai_available() is available


def test_the_model_client_targets_bedrock_in_sydney(monkeypatch):
    monkeypatch.delenv("EB_AWS_REGION", raising=False)
    net._anthropic.cache_clear()
    try:
        assert str(net._anthropic().base_url).startswith("https://bedrock-runtime.ap-southeast-2.amazonaws.com")
    finally:
        net._anthropic.cache_clear()


def test_no_key_falls_back_without_a_network_call(monkeypatch):
    for k in AWS_CREDENTIALS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(net, "_model", None)
    r = reader.read("Phnom Penh is getting hotter", "en", ai=True)
    assert r.ai_failed and r.question is not None


def test_ai_and_keyword_drafts_give_same_question():
    text = "Phnom Penh is getting hotter and drier"
    calls = _model(json.dumps(NULLS | {"kind": "claim", "region_id": "p.phnom-penh", "tests": HEAT_UP_RAIN_DOWN}))
    a = reader.read(f"<sentence>{text}</sentence>", "en", ai=True)
    k = reader.read(text, "en", ai=False)
    assert calls == [f'<sentence lang="en">{text}</sentence>']
    assert (a.draft.via, k.draft.via, a.ai_failed) == ("ai", "keywords", False)
    assert a.question == k.question and a.question is not None


def test_ask_model_sends_the_documented_call_and_treats_refusal_as_failure(monkeypatch):
    sent = []
    reply = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text='{"kind": null}')])
    fake = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: sent.append(kw) or reply))
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-token-not-real")
    monkeypatch.delenv("EB_MODEL", raising=False)
    monkeypatch.setattr(net, "OFFLINE", False)
    monkeypatch.setattr(net, "_model", None)
    monkeypatch.setattr(net, "_anthropic", lambda: fake)
    assert net.ask_model("SYS", "hi", {"type": "object"}, 2048) == {"kind": None}
    [kw] = sent
    assert kw["model"] == "au.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert kw["system"] == [{"type": "text", "text": "SYS", "cache_control": {"type": "ephemeral"}}]
    assert kw["output_config"] == {"format": {"type": "json_schema", "schema": {"type": "object"}}}
    for stop in ("refusal", "max_tokens"):
        reply.stop_reason = stop
        with pytest.raises(AIFailed):
            net.ask_model("SYS", "hi", {"type": "object"}, 2048)


def test_a_signing_failure_becomes_ai_failed(monkeypatch):
    def create(**kw):
        raise RuntimeError("could not resolve AWS credentials")
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "test-token-not-real")
    monkeypatch.setattr(net, "OFFLINE", False)
    monkeypatch.setattr(net, "_model", None)
    monkeypatch.setattr(net, "_anthropic", lambda: SimpleNamespace(messages=SimpleNamespace(create=create)))
    with pytest.raises(AIFailed):
        net.ask_model("SYS", "hi", {"type": "object"}, 2048)


def test_schema_is_closed_nullable_and_stable():
    s = reader.schema()
    assert s["additionalProperties"] is False and s["required"] == list(s["properties"])
    assert set(s["properties"]) == set(NULLS)
    assert {"type": "null"} in s["properties"]["region_id"]["anyOf"]
    assert reader.system() is reader.system()


def test_text_limits():
    with pytest.raises(QuestionError):
        reader.read("   ", "en", ai=False)
    r = client.post("/api/read", json={"text": "x" * 601, "lang": "en", "ai": False})
    assert r.status_code == 400 and r.json()["field"] == "text"


def test_api_read_returns_the_question():
    r = client.post("/api/read", json={"text": "Phnom Penh is getting hotter and drier", "lang": "en", "ai": False})
    assert r.status_code == 200
    body = r.json()
    assert body["question"] == {"kind": "claim", "region": PHNOM_PENH, "tests": HEAT_UP_RAIN_DOWN, "window": None}
    assert body["missing"] == [] and body["ai_failed"] is False


def test_unknown_place_name_goes_through_the_gazetteer(gazetteer):
    r = reader.read("How is rain changing in Batdorf?", "en", ai=False)
    assert r.question.model_dump()["region"] == {"kind": "point", "lat": 13.03, "lon": 102.99, "name": "Batdorf, KHM"}
    r = reader.read("How is rain changing in Atlantis?", "en", ai=False)
    assert r.missing == ["region"] and r.draft.unmapped == ["Atlantis"]


def test_api_geocode():
    assert client.get("/api/geocode", params={"q": "11.55, 104.92"}).json()["results"][0]["lat"] == 11.55
    assert client.get("/api/geocode", params={"q": "Phnom Penh"}).json()["results"][0]["name"] == "Phnom Penh"
    assert client.get("/api/geocode", params={"q": ""}).status_code == 400


def test_the_longer_keyword_names_the_variable():
    tests = lambda text: [t["variable"] for t in reader.read_keywords(text, "en")["tests"]]
    assert tests("Is wet-bulb heat rising in Cambodia?") == ["wetbulb"]
    assert tests("Is the sea getting warmer around Cambodia?") == ["sst"]  # "warmer" inside an sst keyword is not heat
    assert tests("Is it snowing less in Japan?") == ["snowfall"]
    assert tests("Is Spain getting more direct sunlight?") == ["dni"]
