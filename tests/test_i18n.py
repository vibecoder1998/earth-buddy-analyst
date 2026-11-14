import json
import re
import string

import httpx
import pytest
from fastapi.testclient import TestClient

from earthbuddy import ROOT, catalog, fixtures, net, reader
from earthbuddy.analyses import ANALYSES
from earthbuddy import words
from earthbuddy.server import app
from earthbuddy.types import Country, Place

I18N = (ROOT / "web" / "i18n.js").read_text()


def _table(name: str) -> dict[str, str]:
    found = re.search(rf"const {name} = /\*json\*/(.*?)/\*end\*/", I18N, re.S)
    assert found, f"web/i18n.js must hold `const {name} = /*json*/{{...}}/*end*/;`"
    return json.loads(found.group(1))


EN, KM = _table("EN"), _table("KM")
NON_ASCII_DIGIT = re.compile(r"(?![0-9])\d")


def _js_vars(text: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", text))


def _py_fields(text: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


def test_en_and_km_same_keys_and_placeholders():
    assert KM.keys() == EN.keys(), EN.keys() ^ KM.keys()
    differ = [k for k in EN if _js_vars(EN[k]) != _js_vars(KM[k])]
    assert not differ, differ


def test_words_km_keys_subset_of_en_with_same_placeholders():
    assert words.KM.keys() <= words.EN.keys(), words.KM.keys() - words.EN.keys()
    differ = [k for k, text in words.KM.items() if _py_fields(text) != _py_fields(words.EN[k])]
    assert not differ, differ


def test_every_headline_and_student_template_is_in_khmer():
    keys = [f"{v}.{part}" for a in ANALYSES.values() for v in a.verdicts
            for part in ("headline", "student.short", "student.more")]
    assert not [k for k in keys if k not in words.KM]


def test_an_untranslated_audience_falls_back_to_the_khmer_student_text_not_english():
    km, facts = words.Words("km"), {"region": "កម្ពុជា"}
    assert "claim.nothing.researcher.short" not in words.KM
    assert km.template("claim.nothing", "researcher", facts) == km.template("claim.nothing", "student", facts)


@pytest.mark.parametrize("key", [k for k in EN if k.startswith("chip.")])
def test_translated_chips_give_same_question(key):
    home = {lang: f"{catalog.name(Place(id='p.phnom-penh'), lang)}, {catalog.name(Country(iso3='KHM'), lang)}"
            for lang in ("en", "km")}
    en = reader.read(EN[key].replace("{place}", home["en"]), "en", ai=False)
    km = reader.read(KM[key].replace("{place}", home["km"]), "km", ai=False)
    assert km.draft.fields == en.draft.fields
    assert (km.question, km.missing) == (en.question, en.missing)


@pytest.mark.parametrize("en, km", [
    ("Is Phnom Penh hotter than in the 1980s?", "តើភ្នំពេញក្តៅជាងកាលពីទសវត្សរ៍ឆ្នាំ 1980 ឬទេ?"),
    ("Was 2024 a record year for heat in Phnom Penh?", "តើឆ្នាំ 2024 ជាឆ្នាំកំណត់ត្រាកម្តៅនៅភ្នំពេញឬទេ?"),
    ("Is rain linked to fire in Cambodia?", "តើភ្លៀង និងភ្លើងនៅកម្ពុជា ទាក់ទងគ្នាឬទេ?"),
])
def test_khmer_baseline_extremes_relate_read_like_english(en, km):
    a, b = reader.read(en, "en", ai=False), reader.read(km, "km", ai=False)
    assert a.question is not None and b.draft.fields == a.draft.fields


def test_khmer_baseline_names_the_place_in_khmer():
    net.stub(transport=httpx.MockTransport(fixtures.handler))
    question = reader.read("តើភ្នំពេញក្តៅជាងកាលពីទសវត្សរ៍ឆ្នាំ 1980 ឬទេ?", "km", ai=False).question
    r = TestClient(app).post("/api/run", json={"question": question.model_dump(), "lang": "km"})
    assert r.status_code == 200, r.text
    assert r.json()["facts"]["place"] == "ភ្នំពេញ"


def _khmer_strings(x) -> list[str]:
    if isinstance(x, dict):
        return [s for k, v in x.items() for s in ([v] if k == "km" and isinstance(v, str) else _khmer_strings(v))]
    return [s for v in x for s in _khmer_strings(v)] if isinstance(x, list) else []


def test_khmer_text_has_only_ascii_digits():
    texts = [*KM.values(), *words.KM.values()]
    for path in sorted((ROOT / "data").glob("*.json")):
        texts += _khmer_strings(json.loads(path.read_text()))
    assert not [t for t in texts if NON_ASCII_DIGIT.search(t)]


def test_khmer_where_chip_names_the_place_in_khmer():
    net.stub(transport=httpx.MockTransport(fixtures.handler))
    home = f"{catalog.name(Place(id='p.phnom-penh'), 'km')}, {catalog.name(Country(iso3='KHM'), 'km')}"
    question = reader.read(KM["chip.where"].replace("{place}", home), "km", ai=False).question
    r = TestClient(app).post("/api/run", json={"question": question.model_dump(), "lang": "km"})
    assert r.status_code == 200, r.text
    place = r.json()["facts"]["place"]
    assert place == "ភ្នំពេញ" and not re.search("[A-Za-z]", place)
    assert place in "".join(seg["t"] for seg in r.json()["headline"])
