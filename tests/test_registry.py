from typing import get_args

from earthbuddy.analyses import ANALYSES, kinds_meta
from earthbuddy.reader import FILL
from earthbuddy.types import Kind, Question


def _members():
    return {get_args(m.model_fields["kind"].annotation)[0]: m for m in get_args(get_args(Question)[0])}


def test_kind_literal_matches_question_union():
    assert set(get_args(Kind)) == set(_members())


def test_every_built_kind_is_a_known_kind_with_its_own_model():
    for kind, entry in ANALYSES.items():
        assert kind in get_args(Kind)
        assert entry.question is _members()[kind]


def test_guard_has_one_filler_per_field_name():
    names = {f for m in _members().values() for f in m.model_fields if f != "kind"}
    assert set(FILL) == names


def test_kinds_meta_lists_fields_in_declaration_order():
    assert [f["name"] for f in kinds_meta()["claim"]["fields"]] == ["region", "tests", "window"]
    assert {f["name"]: f["required"] for f in kinds_meta()["claim"]["fields"]} == {"region": True, "tests": True, "window": False}
