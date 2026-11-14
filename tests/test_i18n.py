import json
import re
import string

import pytest

from earthbuddy import ROOT, catalog, reader
from earthbuddy.analyses import ANALYSES
from earthbuddy import words
from earthbuddy.types import Country, Place

I18N = (ROOT / "web" / "i18n.js").read_text()


def _table(name: str) -> dict[str, str]:
    found = re.search(rf"const {name} = /\*json\*/(.*?)/\*end\*/", I18N, re.S)
    assert found, f"web/i18n.js must hold `const {name} = /*json*/{{...}}/*end*/;`"
    return json.loads(found.group(1))


EN, KM = _table("EN"), _table("KM")


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
