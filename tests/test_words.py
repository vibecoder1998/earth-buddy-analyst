import pytest

from earthbuddy.analyses import ANALYSES
from earthbuddy.types import Seg
from earthbuddy.words import EN, KM, Words

@pytest.mark.parametrize("kind", ANALYSES)
def test_every_declared_verdict_has_headline_and_every_audience(kind):
    parts = ["headline", *(f"{a}.{p}" for a in ("student", "policymaker", "researcher") for p in ("short", "more"))]
    missing = [f"{key}.{part}" for key in ANALYSES[kind].verdicts for part in parts if f"{key}.{part}" not in EN]
    assert not missing, missing


def test_headline_splits_before_it_fills():
    segs = Words("en").headline("claim.unsupported", {"region": "**Atlantis**"})
    assert segs[0] == Seg(t="Not supported.", hl=True)
    assert segs[1] == Seg(t=" The data for **Atlantis** is not clear enough to back this claim.")


def test_template_falls_back_to_student(monkeypatch):
    monkeypatch.delitem(EN, "claim.nothing.researcher.short")
    w = Words("en")
    assert w.template("claim.nothing", "researcher", {"region": "Phnom Penh"}) == \
        w.template("claim.nothing", "student", {"region": "Phnom Penh"})


def test_khmer_falls_back_to_english(monkeypatch):
    assert Words("km")("tile.verdict.label") == KM["tile.verdict.label"]
    monkeypatch.delitem(KM, "tile.verdict.label")
    assert Words("km")("tile.verdict.label") == EN["tile.verdict.label"]
