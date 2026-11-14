import json

import pytest

from earthbuddy import analyses, catalog, net, reader

HOTTER_DRIER = [{"variable": "heat", "direction": "up"}, {"variable": "rain", "direction": "down"}]
NULLS = {k: None for k in ("kind", "region_id", "place_name", "window_from", "window_to", "year", "among",
                           "metric", "order")} | {"tests": [], "places": [], "leads": [], "unmapped": []}


def _model(reply: dict) -> None:
    net.stub(model=lambda system, user, schema, max_tokens: json.dumps(reply))


@pytest.mark.parametrize("region_id, text", [
    pytest.param("KHM", "Cambodia is getting hotter and drier",
                 marks=pytest.mark.skipif(not catalog.load().countries,
                                          reason="EB-03 phase B: data/catalog.json has no country regions yet")),
    ("p.phnom-penh", "Phnom Penh is getting hotter and drier"),
])
def test_quote_and_via_never_change_a_result(region_id, text):
    _model(NULLS | {"kind": "claim", "region_id": region_id, "tests": HOTTER_DRIER})
    a = reader.read(f"  {text}!", "en", ai=True)
    k = reader.read(text, "en", ai=False)
    assert (a.draft.via, k.draft.via, a.ai_failed) == ("ai", "keywords", False)
    assert a.draft.quote != k.draft.quote
    assert analyses.run(a.question) == analyses.run(k.question)
