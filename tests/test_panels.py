"""The Analyze panels (docs/20 to 22): the contract the screen reads, and the tables behind each panel."""
import json

import pytest
from fastapi.testclient import TestClient

from earthbuddy import SOURCES, catalog, reader, series, stats
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
    assert [c["type"] for c in r["charts"]] == ["line", "intervals", "bars", "bars", "cells", "intervals", "intervals", "line"]
    line, by_satellite, months, provinces, *_ = r["charts"]
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


def test_the_density_map_is_one_hue_of_detections_per_season():
    r = fire(satellite="terra", span=[2005, 2016])
    cells = r["charts"][4]
    assert (cells["scale"], cells["warm_up"], cells["cell_size"], cells["unit"]) == ("level", True, [0.1, 0.1], "detections per season")
    assert all(c[2] > 0 and c[3] is False for c in cells["cells"]) and len(cells["cells"]) <= len(FIRES.cells)
    total = sum(FIRES.seasons["terra"][s] for s in range(2005, 2017))
    assert sum(c[2] for c in cells["cells"]) * 12 == pytest.approx(total, rel=1e-3)


def test_province_change_is_tested_behind_the_gates_and_marked_by_the_false_discovery_rate():
    r = fire()
    change = r["charts"][5]
    assert change["type"] == "intervals" and len(change["rows"]) == 25
    assert [row[1] for row in change["rows"]] == sorted((row[1] for row in change["rows"]), reverse=True)
    marked = {row[0] for row in change["rows"] if row[4]}
    assert marked == {"Stung Treng", "Banteay Meanchey", "Tbong Khmum", "Pailin"}
    assert f"{len(marked)} of 25 tested" in dict(r["detail"]["rows"])["Provinces changing"]
    assert sorted(row[0] for row in fire(zone="mk")["charts"][5]["rows"]) == sorted(FIRES.index.zones["mk"].provinces)
    short = fire(span=[2010, 2010 + T.reliable - 2])
    assert [c["type"] for c in short["charts"]].count("intervals") == 2
    assert any("Province trends need" in n for n in short["notes"])


def test_the_cross_check_is_fixed_and_matches_the_branch():
    """fire_panel.html "compare" on the branch: calendar years 2003 to 2024, percent per decade."""
    for r in (fire(), fire(span=[2010, 2020], satellite="both")):
        cross = r["charts"][6]
        assert "2003–2024" in cross["title"]
        assert [(row[0], round(row[1], 3)) for row in cross["rows"]] == [
            ("Earth Buddy fire series", 2.178), ("Terra", 3.764), ("Aqua", -2.258)]


def test_every_month_on_file_is_drawn_and_the_audit_is_a_method_step():
    r = fire(satellite="both")
    months = r["charts"][7]
    assert len(months["x"]) == 298 and months["x"][0] == pytest.approx(2001 + 10.5 / 12, abs=1e-3)
    audit = next(s for s in r["method"] if s["title"] == "Checked against the raw archive")
    assert str(FIRES.index.audit.raw_rows) in audit["did"] and str(FIRES.index.audit.checks) in audit["did"]


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


# ---- Monthly Giovanni series, shared by Haze and Water (docs/21, docs/22) --------------------------

GIOVANNI = json.loads((catalog.DATA / "giovanni" / "index.json").read_text())


def test_each_measure_choice_has_one_manifest_entry_with_registered_sources():
    registry = {s["id"] for s in json.loads(SOURCES.read_text())}
    meta = kinds_meta()
    for kind in ("haze", "water"):
        if kind not in meta:
            continue
        offered = next(f["choices"] for f in meta[kind]["fields"] if f["name"] == "measure")
        assert sorted(offered) == sorted(e["measure"]["id"] for e in GIOVANNI if e["measure"]["panel"] == kind)
    assert all(set(e["sources"]) <= registry for e in GIOVANNI)


# ---- Water (docs/22) --------------------------------------------------------------------------------

def water(**fields) -> dict:
    r = client.post("/api/run", json={"question": {"kind": "water", **fields}})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("measure, per_decade, unit", [
    ("imerg", 1.03, "%"), ("m2rain", 11.29, "%"), ("soil", 4.09, "%"), ("t2m", -0.012, "°C"), ("wet", 0.506, "°C")])
def test_water_whole_record_matches_the_branch_slopes(measure, per_decade, unit):
    """fire-watch/README.md on feat/fire-watch-cambodia: GPM +1.0%, MERRA-2 rain +11.3%, soil +4.1%, air -0.01 C, wet-bulb +0.51 C."""
    r = water(measure=measure)
    fit = r["detail"]["fit"]
    assert (fit["first_year"], fit["last_year"], fit["n"]) == (2001, 2024, 24)
    got = 100 * fit["slope_per_decade"] / fit["mean"] if unit == "%" else fit["slope_per_decade"]
    assert got == pytest.approx(per_decade, abs=0.005)
    assert r["charts"][2]["unit"] == f"{unit} per decade"


def test_water_result_is_the_shape_the_screen_reads():
    r = water()
    assert r["question"] == {"kind": "water", "measure": "imerg", "span": [2001, 2024]}
    assert [c["type"] for c in r["charts"]] == ["line", "line", "intervals", "intervals", "line"]
    yearly, months, parts, cycle, ratio = r["charts"]
    assert yearly["x"] == list(range(2001, 2025)) and yearly["trend"] and len(yearly["band"]) == 24
    assert len(months["x"]) == 288 and months["x"][0] == pytest.approx(2001.042, abs=1e-3)
    assert [row[0] for row in parts["rows"]] == ["Whole year", "Dry season, November to April", "Wet season, May to October"]
    assert [row[4] for row in parts["rows"]] == [True, False, False]
    assert [row[0] for row in cycle["rows"]][:2] == ["January", "February"] and len(cycle["rows"]) == 12
    assert all(lo <= v <= hi for _, v, lo, hi, _ in cycle["rows"]) and sum(row[4] for row in cycle["rows"]) == 1
    assert set(r["detail"]) == {"fit", "size", "sure", "rows"} and all(len(row) == 2 and all(row) for row in r["detail"]["rows"])
    assert r["investigation"]["scope"]["kind"] == "box" and r["investigation"]["datasets"] == []
    assert [s["id"] for s in r["sources"]] == ["imerg-monthly", "giovanni"]


def test_the_two_rain_records_part_after_2016():
    """Branch: MERRA-2 / GPM goes from 0.70 to 0.94 after 2016, Pettitt p 0.003."""
    for measure in ("imerg", "m2rain"):
        ratio = water(measure=measure)["charts"][-1]
        assert ratio["mark_year"] == 2017
        (a0, a1, before), (b0, b1, after) = ratio["means"]
        assert (a0, a1, b0, b1) == (2001, 2016, 2017, 2024)
        assert (round(before, 2), round(after, 2)) == (0.70, 0.94)
    assert [c["type"] for c in water(measure="soil")["charts"]] == ["line", "line", "intervals", "intervals"]


def test_a_step_is_named_only_where_the_chosen_years_hold_one():
    stepped = water(measure="m2rain")
    assert stepped["charts"][0]["mark_year"] == 2018 and any("jumps around 2018" in n for n in stepped["notes"])
    assert not any("jumps" in n for n in water(measure="imerg")["notes"])
    early = water(measure="m2rain", span=[2001, 2014])
    assert early["charts"][0]["mark_year"] is None and not any("jumps" in n for n in early["notes"])


def test_parts_of_the_year_that_disagree_carry_a_note():
    wet = water(measure="wet")
    levels = [row[1].rsplit(", ", 1)[-1] for row in wet["detail"]["rows"] if row[0].startswith(("Whole", "Dry", "Wet"))]
    assert len(set(levels)) > 1 and any("parts of the year disagree" in n for n in wet["notes"])
    assert not any("disagree" in n for n in water(measure="t2m")["notes"])


def test_a_water_span_is_clipped_to_the_files_and_too_short_is_a_400_on_span():
    assert water(span=[1990, 2010])["charts"][0]["x"] == list(range(2001, 2011))
    for span in ([2018, 2024], [2030, 2040]):
        r = client.post("/api/run", json={"question": {"kind": "water", "span": span}})
        assert r.status_code == 400 and r.json()["field"] == "span", r.text


# ---- Haze (docs/21) ---------------------------------------------------------------------------------

def haze(**fields) -> dict:
    r = client.post("/api/run", json={"question": {"kind": "haze", **fields}})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("measure, per_decade", [("bc", -6.40), ("pm25", -1.91), ("aod", -7.23)])
def test_aerosol_series_reproduce_the_branch_whole_record_slopes(measure, per_decade):
    """fire-watch/README.md: black carbon -6.4%, PM2.5 -1.9%, AOD -7.2% per decade, yearly means 2001 to 2024.
    The panel's span starts at the first fire season, so this reads the series it is built on."""
    m = series.monthly(measure)
    fit = stats.trend_test(*series.season_means(m.values, list(range(1, 13)), (2001, 2024)), rel=True)
    assert 100 * fit.slope_per_decade / fit.mean == pytest.approx(per_decade, abs=0.005)


@pytest.mark.parametrize("measure, rho", [("bc", "0.56"), ("pm25", "0.75"), ("aod", "0.71")])
def test_haze_default_view_matches_the_branch_links_to_fire(measure, rho):
    """fire-watch/data/default_view.json and README: Aqua seasons 2003 to 2022, Spearman season by season."""
    f = haze(measure=measure)["facts"]
    assert (f["season_rho_raw"], f["n_link_seasons"], f["n_link_months"]) == (rho, 20, 240)
    if measure == "bc":
        assert f["month_rho_raw"] == "0.71" and f["peak_month"] == "January" and f["low_month"] == "July"


def test_haze_result_is_the_shape_the_screen_reads():
    r = haze()
    assert r["question"] == {"kind": "haze", "measure": "bc", "satellite": "aqua", "span": [2003, 2022]}
    assert [c["type"] for c in r["charts"]] == ["line", "line", "line", "intervals", "scatter"]
    dry, months, year, parts, scatter = r["charts"]
    assert dry["x"] == list(range(2003, 2023)) and dry["trend"] and len(dry["band"]) == 20
    assert len(months["x"]) == 240 and months["x"][0] == pytest.approx(2002 + 10.5 / 12, abs=1e-3)
    assert year["x"] == list(range(1, 13)) and year["labels"] == ["Black carbon (soot), MERRA-2 model", "Aqua fire detections"]
    assert sum(year["y"]) == pytest.approx(1200) and sum(year["compare"]) == pytest.approx(1200)
    assert [row[4] for row in parts["rows"]] == [False, True, False]
    assert [p[2] for p in scatter["points"]] == [str(s) for s in range(2003, 2023)]
    assert [p[1] for p in scatter["points"]] == [FIRES.seasons["aqua"][s] for s in range(2003, 2023)]
    assert [s["id"] for s in r["sources"]] == ["merra2-aer-monthly", "giovanni", *FIRES.index.sources]
    assert r["investigation"]["scope"]["kind"] == "box" and r["investigation"]["datasets"] == []
    assert all(len(row) == 2 and all(row) for row in r["detail"]["rows"])


def test_the_fire_satellite_changes_only_the_fire_side():
    aqua, both = haze(), haze(satellite="both")
    assert aqua["charts"][0] == both["charts"][0] and aqua["verdict"] == both["verdict"]
    assert [p[1] for p in both["charts"][4]["points"]] == [
        FIRES.seasons["aqua"][s] + FIRES.seasons["terra"][s] for s in range(2003, 2023)]
    assert any("counted twice" in n for n in both["notes"]) and not any("counted twice" in n for n in aqua["notes"])


def test_haze_seasons_stop_where_the_aerosol_files_do():
    r = haze(span=[2015, 2026])
    assert r["charts"][0]["x"][-1] == 2024 and any("2022" in n for n in r["notes"])
    for span in ([2018, 2024], [1990, 2002]):
        bad = client.post("/api/run", json={"question": {"kind": "haze", "span": span}})
        assert bad.status_code == 400 and bad.json()["field"] == "span", bad.text

