"""The Analyze panels (docs/20 to 22): the contract the screen reads, and the tables behind each panel."""
import json

import pytest
from fastapi.testclient import TestClient

from earthbuddy import SOURCES, catalog, reader, series
from earthbuddy.analyses import kinds_meta
from earthbuddy.server import app
from earthbuddy.stats import T

client = TestClient(app)
FIRES = series.fires()
SEASONS = range(FIRES.index.seasons[0], FIRES.index.seasons[1] + 1)
SATELLITES = ("aqua", "terra")


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


# ---- Fire (docs/20) ---------------------------------------------------------------------------------

def fire(**fields) -> dict:
    r = client.post("/api/run", json={"question": {"kind": "fire", **fields}})
    assert r.status_code == 200, r.text
    return r.json()


def percent_per_decade(r: dict) -> float:
    return 100 * r["detail"]["fit"]["slope_per_decade"] / r["detail"]["fit"]["mean"]


def test_default_view_matches_the_branch_reference():
    """fire-watch/data/default_view.json on feat/fire-watch-cambodia: Aqua and Terra, seasons 2003 to 2022."""
    aqua, terra = fire(), fire(satellite="terra")
    assert aqua["question"] == {"kind": "fire", "satellite": "aqua", "zone": "all", "span": [2003, 2022]}
    assert percent_per_decade(aqua) == pytest.approx(-1.1027, abs=1e-3)
    assert percent_per_decade(terra) == pytest.approx(15.1252, abs=1e-3)
    assert aqua["detail"]["fit"]["mean"] == pytest.approx(18854.85) and terra["detail"]["fit"]["mean"] == pytest.approx(8228.8)
    assert aqua["verdict"] == terra["verdict"] == {"key": "trend.unclear", "level": "unclear"}
    months, provinces = aqua["charts"][2], aqua["charts"][3]
    assert months["values"][:4] == [34.7, 30.2, 18.7, 6.3] and months["values"][11] == 7.4
    assert (provinces["labels"][0], provinces["values"][0]) == ("Preah Vihear", 2578.9)


def test_fire_result_is_the_shape_the_screen_reads():
    r = fire()
    assert [c["type"] for c in r["charts"]] == ["line", "intervals", "bars", "bars"]
    line, by_satellite, months, provinces = r["charts"]
    assert line["x"] == list(range(2003, 2023)) and line["trend"] and len(line["band"]) == 20
    assert [row[0] for row in by_satellite["rows"]] == ["Aqua", "Terra", "Aqua + Terra"]
    assert [row[4] for row in by_satellite["rows"]] == [True, False, False]
    assert len(months["labels"]) == 12 and sum(months["values"]) == pytest.approx(100, abs=0.5)
    assert len(provinces["labels"]) == 25 and sum(provinces["highlight"]) == 5
    assert 2 <= len(r["tiles"]) <= 4
    assert set(r["detail"]) == {"fit", "size", "sure", "rows"}
    assert all(len(row) == 2 and all(row) for row in r["detail"]["rows"])
    assert r["investigation"]["scope"]["kind"] == "box" and r["investigation"]["datasets"] == []
    assert r["investigation"]["next"], "follow-ups hand off to Ask questions about fire in Cambodia"
    assert r["notes"] == []


def test_fire_sources_are_registered():
    registry = {s["id"] for s in json.loads(SOURCES.read_text())}
    assert set(FIRES.index.sources) <= registry
    assert [s["id"] for s in fire()["sources"]] == FIRES.index.sources


def test_both_satellites_is_aqua_plus_terra_and_says_so():
    aqua, terra, both = (fire(satellite=s) for s in ("aqua", "terra", "both"))
    assert both["charts"][0]["y"] == [a + t for a, t in zip(aqua["charts"][0]["y"], terra["charts"][0]["y"])]
    assert any("counted twice" in note for note in both["notes"])
    assert not any("counted twice" in note for note in aqua["notes"])


def test_seasons_after_the_like_for_like_years_carry_a_warning():
    until = FIRES.index.like_for_like_until
    assert any(str(until) in note for note in fire(span=[2010, until + 1])["notes"])
    assert fire(span=[2010, until])["notes"] == []


def test_the_month_share_stops_at_the_last_whole_fire_year():
    last = FIRES.fire_years[1]
    r = fire(span=[2012, last + 1])
    assert f"{last}" in r["charts"][2]["title"] and r["facts"]["months_until"] == last
    assert any(FIRES.index.audit.last in note for note in r["notes"])
    assert not any(FIRES.index.audit.last in note for note in fire(span=[2012, last])["notes"])


def test_zone_lists_only_its_provinces():
    r = fire(zone="ne")
    assert sorted(r["charts"][3]["labels"]) == sorted(FIRES.index.zones["ne"].provinces)
    assert r["charts"][0] == fire()["charts"][0], "a zone narrows the province list, not the season counts"


def test_a_span_is_clipped_to_the_record_and_too_short_is_a_400_on_span():
    assert fire(span=[1990, 2012])["charts"][0]["x"] == list(range(2003, 2013))
    assert fire(span=[2014, 2014 + T.min_years])["verdict"]["level"] == "too_short"
    for span in ([2015, 2015 + T.min_years - 2], [1990, 1995]):
        r = client.post("/api/run", json={"question": {"kind": "fire", "span": span}})
        assert r.status_code == 400 and r.json()["field"] == "span", r.text


def test_fire_answers_in_khmer_where_text_exists():
    r = client.post("/api/run", json={"question": {"kind": "fire"}, "lang": "km"}).json()
    assert r["facts"]["place"] == "កម្ពុជា" and r["charts"][3]["labels"][0] == "ព្រះវិហារ"


def test_catalog_tells_the_screen_the_panel_and_its_options():
    meta = client.get("/api/catalog").json()["kinds"]["fire"]
    assert meta["screen"] == "analyze"
    assert {f["name"]: f.get("choices") for f in meta["fields"]} == {
        "satellite": ["aqua", "terra", "both"], "zone": list(FIRES.index.zones), "span": None}
    assert not any(f["required"] for f in meta["fields"])


# The copied tables against each other: four files, one set of counts.

def test_a_season_is_november_to_april_named_by_the_year_it_ends():
    assert FIRES.index.season_months == [11, 12, 1, 2, 3, 4]
    for sat in SATELLITES:
        for s in SEASONS:
            months = [(s - 1, 11), (s - 1, 12), (s, 1), (s, 2), (s, 3), (s, 4)]
            assert sum(FIRES.months[sat].get(m, 0) for m in months) == FIRES.seasons[sat][s], (sat, s)


def test_the_first_season_offered_is_the_first_both_satellites_cover_whole():
    assert list(SEASONS) == list(range(2003, 2027))
    assert all(set(FIRES.seasons[sat]) == set(SEASONS) for sat in SATELLITES)
    assert FIRES.fire_years == (2003, 2025)


def test_province_counts_add_up_to_the_season_totals():
    for sat in SATELLITES:
        for s in SEASONS:
            assert sum(p.get(s, 0) for p in FIRES.provinces[sat].values()) == FIRES.seasons[sat][s], (sat, s)


def test_density_squares_add_up_to_the_season_totals():
    for sat in SATELLITES:
        for s in SEASONS:
            assert len(FIRES.cell_counts[sat][s]) == len(FIRES.cells)
            assert sum(FIRES.cell_counts[sat][s]) == FIRES.seasons[sat][s], (sat, s)


def test_provinces_are_the_catalog_group_and_zones_split_them():
    group = {m.name.split(",")[0] for m in catalog.group("cambodia_provinces").members}
    assert len(group) == 25
    assert all(set(FIRES.provinces[sat]) == group for sat in SATELLITES)
    zones = FIRES.index.zones
    assert set(zones["all"].provinces) == group
    parts = [p for key, z in zones.items() if key != "all" for p in z.provinces]
    assert sorted(parts) == sorted(group)
