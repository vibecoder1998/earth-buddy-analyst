import string

import pytest

from earthbuddy.analyses import ANALYSES
from earthbuddy.types import Seg
from earthbuddy.words import EN, KM, Words

PENDING = {"trend": "EB-08 writes the trend.* words with the trend analysis"}


@pytest.mark.parametrize("kind", [pytest.param(k, marks=pytest.mark.skip(PENDING[k])) if k in PENDING else k
                                  for k in ANALYSES])
def test_every_declared_verdict_has_headline_and_student_templates(kind):
    missing = [f"{key}.{part}" for key in ANALYSES[kind].verdicts
               for part in ("headline", "student.short", "student.more") if f"{key}.{part}" not in EN]
    assert not missing, missing


def test_claim_has_every_audience():
    missing = [f"{key}.{a}.{p}" for key in ANALYSES["claim"].verdicts for a in ("student", "policymaker", "researcher")
               for p in ("short", "more") if f"{key}.{a}.{p}" not in EN]
    assert not missing, missing


def _fields(text: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


def test_km_keys_are_en_keys_with_the_same_placeholders():
    assert all(k in EN and _fields(t) == _fields(EN[k]) for k, t in KM.items())


def test_headline_splits_before_it_fills():
    segs = Words("en").headline("claim.unsupported", {"region": "**Atlantis**"})
    assert segs[0] == Seg(t="Not supported.", hl=True)
    assert segs[1] == Seg(t=" The data for **Atlantis** is not clear enough to back this claim.")


def test_template_falls_back_to_student(monkeypatch):
    monkeypatch.delitem(EN, "claim.nothing.researcher.short")
    w = Words("en")
    assert w.template("claim.nothing", "researcher", {"region": "Phnom Penh"}) == \
        w.template("claim.nothing", "student", {"region": "Phnom Penh"})


def test_khmer_falls_back_to_english():
    assert Words("km")("tile.verdict.label") == EN["tile.verdict.label"]
