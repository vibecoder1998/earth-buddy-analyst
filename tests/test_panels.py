"""The Analyze panels (docs/20 to 22): the contract the screen reads, and the tables behind each panel."""
from earthbuddy import reader
from earthbuddy.analyses import kinds_meta


def test_kinds_meta_says_which_screen_lists_a_kind_and_what_each_select_offers():
    meta = kinds_meta()
    assert {m["screen"] for m in meta.values()} <= {"ask", "analyze"}
    assert meta["trend"]["screen"] == "ask"
    rank = {f["name"]: f.get("choices") for f in meta["rank"]["fields"]}
    assert rank["metric"] == ["change", "level"] and rank["order"] == ["highest", "lowest"]
    assert rank["variable"] is None and rank["top_n"] is None


def test_the_guard_keeps_a_span_the_window_rule_would_drop():
    fields = reader.guard({"kind": "fire", "span": [2019, 2026], "window": [2019, 2026]}, "", "link").fields
    assert fields == {"kind": "fire", "span": [2019, 2026]}
    assert "span" not in reader.guard({"kind": "fire", "span": [2026, 2019]}, "", "link").fields
    assert reader.guard({"kind": "water", "measure": "soil", "satellite": "terra"}, "", "link").fields == {"kind": "water", "measure": "soil"}
