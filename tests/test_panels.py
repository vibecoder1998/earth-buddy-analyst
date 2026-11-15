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


FIRE_CHARTS = ("seasons", "by_satellite", "all_months", "months", "density", "zones", "provinces", "change_map", "change",
               "cross", "funnel")


def chart(r: dict, name: str) -> dict:
    """A fire chart by its place in the panel. Without province trends the two charts of that section are absent."""
    names = FIRE_CHARTS if len(r["charts"]) == len(FIRE_CHARTS) else [n for n in FIRE_CHARTS if not n.startswith("change")]
    assert len(r["charts"]) == len(names)
    return r["charts"][names.index(name)]


def rows(r: dict) -> dict[str, str]:
    return dict(r["detail"]["rows"])


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
    months, provinces = chart(aqua, "months"), chart(aqua, "provinces")
    assert months["values"][:4] == [34.7, 30.2, 18.7, 6.3] and months["values"][11] == 7.4
    assert (provinces["labels"][0], provinces["values"][0]) == ("Preah Vihear", 2578.9)


def test_fire_result_is_the_shape_the_screen_reads():
    r = fire()
    assert [c["type"] for c in r["charts"]] == ["line", "intervals", "line", "bars", "cells", "bars", "bars", "cells",
                                                "intervals", "intervals", "bars"]
    line, by_satellite, months, provinces = (chart(r, n) for n in ("seasons", "by_satellite", "months", "provinces"))
    assert line["x"] == list(SEASONS) and line["trend"] and [b[0] for b in line["band"]] == list(range(2003, 2023))
    assert [t[0] for t in line["trend"]] == [2003, 2022], "the trend line covers the chosen seasons only"
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
    assert aqua["charts"][0]["compare"] == terra["charts"][0]["y"] and aqua["charts"][0]["labels"] == ["Aqua", "Terra"]
    assert both["charts"][0]["compare"] == aqua["charts"][0]["y"] and both["charts"][0]["labels"] == ["Aqua + Terra", "Aqua"]
    assert any("counted twice" in note for note in both["notes"])
    assert not any("counted twice" in note for note in aqua["notes"])


def test_seasons_after_the_like_for_like_years_carry_a_warning():
    until = FIRES.index.like_for_like_until
    assert any(str(until) in note for note in fire(span=[2010, until + 1])["notes"])
    assert fire(span=[2010, until])["notes"] == []


def test_the_month_share_stops_at_the_last_whole_fire_year():
    last = FIRES.fire_years[1]
    r = fire(span=[2012, last + 1])
    assert f"{last}" in chart(r, "months")["title"] and r["facts"]["months_until"] == last
    assert any(FIRES.index.audit.last in note for note in r["notes"])
    assert not any(FIRES.index.audit.last in note for note in fire(span=[2012, last])["notes"])


def test_zone_lists_only_its_provinces():
    r = fire(zone="ne")
    assert sorted(chart(r, "provinces")["labels"]) == sorted(FIRES.index.zones["ne"].provinces)
    assert r["charts"][0] == fire()["charts"][0], "a zone narrows the province list, not the season counts"
    zones = chart(r, "zones")
    assert zones["labels"][zones["highlight"].index(True)] == "North-East" and sum(zones["highlight"]) == 1


def test_a_span_is_clipped_to_the_record_and_too_short_is_a_400_on_span():
    assert [b[0] for b in fire(span=[1990, 2012])["charts"][0]["band"]] == list(range(2003, 2013))
    assert fire(span=[2014, 2014 + T.min_years])["verdict"]["level"] == "too_short"
    for span in ([2015, 2015 + T.min_years - 2], [1990, 1995]):
        r = client.post("/api/run", json={"question": {"kind": "fire", "span": span}})
        assert r.status_code == 400 and r.json()["field"] == "span", r.text


def test_fire_answers_in_khmer_where_text_exists():
    r = client.post("/api/run", json={"question": {"kind": "fire"}, "lang": "km"}).json()
    assert r["facts"]["place"] == "កម្ពុជា" and chart(r, "provinces")["labels"][0] == "ព្រះវិហារ"


def test_catalog_tells_the_screen_the_panel_and_its_options():
    meta = client.get("/api/catalog").json()["kinds"]["fire"]
    assert meta["screen"] == "analyze"
    assert {f["name"]: f.get("choices") for f in meta["fields"]} == {
        "satellite": ["aqua", "terra", "both"], "zone": list(FIRES.index.zones), "span": None}
    assert not any(f["required"] for f in meta["fields"])


def test_the_density_map_is_one_hue_of_detections_per_season():
    r = fire(satellite="terra", span=[2005, 2016])
    cells = chart(r, "density")
    assert (cells["scale"], cells["warm_up"], cells["cell_size"], cells["unit"]) == ("level", True, [0.1, 0.1], "detections per season")
    assert all(c[2] > 0 and c[3] is False for c in cells["cells"]) and len(cells["cells"]) <= len(FIRES.cells)
    total = sum(FIRES.seasons["terra"][s] for s in range(2005, 2017))
    assert sum(c[2] for c in cells["cells"]) * 12 == pytest.approx(total, rel=1e-3)


def test_province_change_is_tested_behind_the_gates_and_marked_by_the_false_discovery_rate():
    r = fire()
    change = chart(r, "change")
    assert change["type"] == "intervals" and len(change["rows"]) == 25
    assert [row[1] for row in change["rows"]] == sorted((row[1] for row in change["rows"]), reverse=True)
    marked = {row[0] for row in change["rows"] if row[4]}
    assert marked == {"Stung Treng", "Banteay Meanchey", "Tbong Khmum", "Pailin"}
    assert "of 25 tested" in rows(r)["Provinces changing"] and f"{len(marked)} hold" in rows(r)["Provinces changing"]
    assert sorted(row[0] for row in chart(fire(zone="mk"), "change")["rows"]) == sorted(FIRES.index.zones["mk"].provinces)
    short = fire(span=[2010, 2010 + T.reliable - 2])
    assert [c["type"] for c in short["charts"]].count("intervals") == 2 and len(short["charts"]) == len(FIRE_CHARTS) - 2
    assert any("Province trends need" in n for n in short["notes"])


def test_the_cross_check_is_fixed_and_matches_the_branch():
    """fire_panel.html "compare" on the branch: calendar years 2003 to 2024, percent per decade."""
    for r in (fire(), fire(span=[2010, 2020], satellite="both")):
        cross = chart(r, "cross")
        assert "2003–2024" in cross["title"]
        assert [(row[0], round(row[1], 3)) for row in cross["rows"]] == [
            ("Earth Buddy fire series", 2.178), ("Terra", 3.764), ("Aqua", -2.258)]


def test_every_month_on_file_is_drawn_and_the_audit_is_a_method_step():
    r = fire(satellite="both")
    months = chart(r, "all_months")
    assert len(months["x"]) == 298 and months["x"][0] == pytest.approx(2001 + 10.5 / 12, abs=1e-3)
    assert months["y"][0] is None and months["y"][8] is not None, "Aqua + Terra starts with Aqua, in July 2002"
    assert months["compare"][:8] == [None] * 8 and months["labels"] == ["Aqua + Terra", "Aqua"]
    audit = next(s for s in r["method"] if s["title"] == "Checked against the raw archive")
    assert str(FIRES.index.audit.raw_rows) in audit["did"] and str(FIRES.index.audit.checks) in audit["did"]


# The copied tables against each other: four files, one set of counts.

def test_the_satellite_cards_give_the_branch_second_opinions_and_never_the_level():
    """Reference: the branch's default view, seasons 2003-2022 (fire-watch/data/default_view.json and its panel)."""
    r = fire()
    f, cards = r["facts"], rows(r)
    assert (f["aqua_plain"], f["aqua_lag1"], f["aqua_step_after"], f["aqua_step_p"]) == ("0.922", "−0.044", 2016, "0.876")
    assert (f["terra_plain"], f["terra_step_after"], f["terra_step_p"]) == ("0.230", 2010, "0.290")
    assert float(f["terra_lag1"]) == pytest.approx(0.104, abs=0.005)
    for name in ("Aqua", "Terra", "Aqua + Terra"):
        assert "Second opinions" in cards[f"{name}: the tests in full"]
    assert r["verdict"]["level"] == "unclear" and f["p_value"] == f["aqua_p_value"], "the headline p is main's test"
    assert any("never set the level" in step["why"] for step in r["method"])


def test_the_summary_gives_the_branch_shares():
    f = fire()["facts"]
    assert (f["peak_share"], f["season_share"], f["top_share"], f["rest_share"]) == ("91%", "98%", "52%", "47.7%")
    assert f["top_list"].startswith("Preah Vihear 13.7% (2579 per season), Stung Treng 11.3% (2121 per season)")
    assert (f["cross_rho"], f["cross_ratio"]) == ("0.95", "1.01")
    assert (f["cross_catalog_plain"], f["cross_terra_prewhitened"], f["cross_aqua_plain"]) == ("0.866", "0.695", "0.735")


def test_the_funnel_and_the_archive_rows_are_counted_from_the_tables():
    """Reference: fire-watch/data/pipeline_audit.json and raw_audit.json on the branch."""
    r = fire()
    funnel = chart(r, "funnel")
    assert funnel["values"] == [717185, 678839, 647193, 629913, 588197]
    f = r["facts"]
    assert (f["kept_aqua"], f["kept_terra"], f["raw_aqua"], f["raw_terra"]) == (447469, 199724, 485352, 231833)
    assert (f["months_on_file"], f["months_expected"], f["season_rows_share"], f["unused_rows"]) == (298, 298, "97.3%", 115)
    assert f["kept_aqua"] + f["kept_terra"] == f["clean_rows"]


def test_the_shading_marks_the_later_seasons_and_the_chosen_ones():
    r = fire(span=[2010, 2024])
    assert r["charts"][0]["spans"] == [[2023, 2026]] and "2022" in r["charts"][0]["span_label"]
    lo, hi = chart(r, "all_months")["spans"][0]
    assert lo == pytest.approx(2009 + 10.5 / 12, abs=1e-3) and hi == pytest.approx(2024 + 3.5 / 12, abs=1e-3)


def test_the_trend_map_puts_each_tested_province_at_its_centre():
    r = fire()
    cells, change = chart(r, "change_map"), chart(r, "change")
    assert cells["scale"] == "change" and len(cells["cells"]) == 25
    centre = catalog.centre(next(m for m in catalog.group("cambodia_provinces").members if m.name.startswith("Preah Vihear")))
    assert [centre.lat, centre.lon] in [c[:2] for c in cells["cells"]]
    assert sum(c[3] for c in cells["cells"]) == sum(row[4] for row in change["rows"])
    assert sorted(c[2] for c in cells["cells"]) == sorted(round(row[1], 1) for row in change["rows"])


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
    assert [c["type"] for c in r["charts"]] == ["line", "line", "intervals", "intervals", "line", "line"]
    yearly, months, parts, cycle, seasons, ratio = r["charts"]
    assert yearly["x"] == list(range(2001, 2025)) and yearly["trend"] and len(yearly["band"]) == 24
    assert len(months["x"]) == 288 and months["x"][0] == pytest.approx(2001.042, abs=1e-3)
    assert months["trend"] == [[x + 0.5, y] for x, y in yearly["trend"]], "the Sen line of the yearly means, at mid-year"
    assert len(months["spans"]) == 25 and months["spans"][1] == [pytest.approx(2001 + 10.5 / 12, abs=1e-3), pytest.approx(2002 + 3.5 / 12, abs=1e-3)]
    assert seasons["labels"] == ["Wet season, May to October", "Dry season, November to April"] and len(seasons["y"]) == 24
    assert [row[0] for row in parts["rows"]] == ["Whole year", "Dry season, November to April", "Wet season, May to October"]
    assert [row[4] for row in parts["rows"]] == [True, False, False]
    assert [row[0] for row in cycle["rows"]][:2] == ["January", "February"] and len(cycle["rows"]) == 12
    assert all(lo <= v <= hi for _, v, lo, hi, _ in cycle["rows"]) and sum(row[4] for row in cycle["rows"]) == 1
    assert set(r["detail"]) == {"fit", "size", "sure", "rows"} and all(len(row) == 2 and all(row) for row in r["detail"]["rows"])
    assert r["investigation"]["scope"]["kind"] == "box" and r["investigation"]["datasets"] == []
    assert [s["id"] for s in r["sources"]][:2] == ["imerg-monthly", "giovanni"], "the chosen series first"
    assert {s["id"] for s in r["sources"]} >= {"merra2-lnd-monthly", "merra2-slv-monthly", "modis-mcd14ml"}, "the fixed rows read these"


def test_the_two_rain_records_part_after_2016():
    """Branch: MERRA-2 / GPM goes from 0.70 to 0.94 after 2016, Pettitt p 0.003."""
    for measure in ("imerg", "m2rain"):
        ratio = water(measure=measure)["charts"][-1]
        assert ratio["mark_year"] == 2017
        (a0, a1, before), (b0, b1, after) = ratio["means"]
        assert (a0, a1, b0, b1) == (2001, 2016, 2017, 2024)
        assert (round(before, 2), round(after, 2)) == (0.70, 0.94)
    assert water(measure="soil")["charts"][-1] == ratio, "the two rain records are compared beside every series"


def test_a_step_is_named_only_where_the_chosen_years_hold_one():
    stepped = water(measure="m2rain")
    assert stepped["charts"][0]["mark_year"] == 2018 and any("jumps around 2018" in n for n in stepped["notes"])
    assert not any("jumps" in n for n in water(measure="imerg")["notes"])
    early = water(measure="m2rain", span=[2001, 2014])
    assert early["charts"][0]["mark_year"] is None and not any("jumps" in n for n in early["notes"])


def test_parts_of_the_year_that_disagree_carry_a_note():
    wet = water(measure="wet")
    levels = [row[1].rsplit(", ", 1)[-1] for row in wet["detail"]["rows"] if row[0].startswith(("Whole year", "Dry", "Wet season"))]
    assert len(levels) == 3 and len(set(levels)) > 1 and any("parts of the year disagree" in n for n in wet["notes"])
    assert not any("parts of the year disagree" in n for n in water(measure="t2m")["notes"])


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
    assert [c["type"] for c in r["charts"]] == ["line", "line", "intervals", "bars", "line", "intervals", "line", "scatter"]
    dry, months, cycle, fire_months, year, parts, whole, scatter = r["charts"]
    assert len(months["spans"]) == 20 and months["spans"][0] == [pytest.approx(2002 + 10.5 / 12, abs=1e-3), pytest.approx(2003 + 3.5 / 12, abs=1e-3)]
    assert len(cycle["rows"]) == 12 and fire_months["labels"][fire_months["highlight"].index(True)] == "January"
    assert whole["x"] == list(range(2001, 2025)) and whole == haze(span=[2010, 2020])["charts"][6], "fixed, whatever the span"
    assert dry["x"] == list(range(2003, 2023)) and dry["trend"] and len(dry["band"]) == 20
    assert len(months["x"]) == 240 and months["x"][0] == pytest.approx(2002 + 10.5 / 12, abs=1e-3)
    assert year["x"] == list(range(1, 13)) and year["labels"] == ["Black carbon (soot), MERRA-2 model", "Aqua fire detections"]
    assert sum(year["y"]) == pytest.approx(1200) and sum(year["compare"]) == pytest.approx(1200)
    assert [row[4] for row in parts["rows"]] == [False, True, False]
    assert [p[2] for p in scatter["points"]] == [str(s) for s in range(2003, 2023)]
    assert [p[1] for p in scatter["points"]] == [FIRES.seasons["aqua"][s] for s in range(2003, 2023)]
    assert [s["id"] for s in r["sources"]][:5] == ["merra2-aer-monthly", "giovanni", *FIRES.index.sources]
    assert {s["id"] for s in r["sources"]} >= {"imerg-monthly", "merra2-lnd-monthly"}, "the jump limit reads every Giovanni series"
    assert r["investigation"]["scope"]["kind"] == "box" and r["investigation"]["datasets"] == []
    assert all(len(row) == 2 and all(row) for row in r["detail"]["rows"])


def test_the_fire_satellite_changes_only_the_fire_side():
    aqua, both = haze(), haze(satellite="both")
    assert aqua["charts"][0] == both["charts"][0] and aqua["verdict"] == both["verdict"]
    assert [p[1] for p in both["charts"][-1]["points"]] == [
        FIRES.seasons["aqua"][s] + FIRES.seasons["terra"][s] for s in range(2003, 2023)]
    assert any("counted twice" in n for n in both["notes"]) and not any("counted twice" in n for n in aqua["notes"])


def test_haze_seasons_stop_where_the_aerosol_files_do():
    r = haze(span=[2015, 2026])
    assert r["charts"][0]["x"][-1] == 2024 and any("2022" in n for n in r["notes"])
    for span in ([2018, 2024], [1990, 2002]):
        bad = client.post("/api/run", json={"question": {"kind": "haze", "span": span}})
        assert bad.status_code == 400 and bad.json()["field"] == "span", bad.text



# ---- Second opinions and the fixed whole-record cards (docs/03, docs/21, docs/22) -------------------------------

# The branch's robustness card, whole record 2001-2024: plain, pre-whitened, Hamed-Rao, Yue-Wang, seasonal, anomalies,
# then how many of the six fall under 0.05 (fire-watch/tools/water_template.html reads them from build_fire_watch.py).
ROBUST = {
    "imerg": ((0.8233, 0.8327, 0.8233, 0.4766, 0.9486, 0.6343), 0),
    "m2rain": ((0.0445, 0.0083, 0.1361, 0.0053, 0.0093, 0.0010), 5),
    "soil": ((0.0445, 0.0037, 0.1589, 0.0079, 0.0, 0.0), 5),
    "t2m": ((0.9013, 0.8741, 0.9013, 0.7694, 0.6416, 0.8644), 0),
    "wet": ((0.0012, 0.0, 0.0012, 0.0, 0.0, 0.0), 6),
}


@pytest.mark.parametrize("measure", ROBUST)
def test_the_six_second_opinions_match_the_branch_and_set_no_level(measure):
    ps, found = ROBUST[measure]
    m = series.monthly(measure)
    years, values = series.season_means(m.values, list(range(1, 13)), (2001, 2024))
    got = stats.second_opinions(values, m.values)
    assert list(got[:6]) == pytest.approx(ps, abs=5e-4) and got.found == found
    r = water(measure=measure, span=[2005, 2020])
    f = r["facts"]
    assert (f["whole_found"], f["whole_of"], f["whole_first"], f["whole_last"]) == (found, 6, 2001, 2024), "fixed, whatever the span"
    assert r["verdict"]["level"] == stats.trend_test(*series.season_means(m.values, list(range(1, 13)), (2005, 2020)),
                                                     rel=m.info.rel).level, "the level is the headline test's alone"
    six = rows(r)["Robustness, whole record 2001–2024 (fixed)"]
    assert "second opinions" in six and ("of 6 tests" in six or "the 6 tests" in six or "All 6 tests" in six)


def test_the_water_panel_gives_the_branch_fixed_figures():
    """Branch case tabs C3 to C6: three of five series under 0.05 on the plain test, r 0.93 between the rain records,
    and the month-to-month links +0.68 / +0.28, -0.57 / -0.50 and -0.61 / -0.21 over 264 months."""
    r = water(measure="soil", span=[2008, 2020])
    f, table = r["facts"], rows(r)
    assert (f["series_under"], f["series"], f["rain_r"], f["rain_months"]) == (3, 5, "0.93", 288)
    assert (f["model_steps"], f["model_series"], f["steps_first"], f["steps_last"], f["satellite_step_p"]) == (4, 7, 2016, 2017, "0.993")
    assert (f["all_m2rain_step_after"], f["all_m2rain_step_p"], f["all_wet_step_p"], f["all_t2m_step_p"]) == (2017, "0.012", "0.002", "0.648")
    assert (f["all_imerg_plain"], f["all_wet_plain"], f["all_t2m_plain"]) == ("0.823", "0.001", "0.901")
    links = [v for k, v in table.items() if k.startswith("Month to month (fixed)")]
    assert [v.split(".")[0] + v.split(":")[-1] for v in links] == [
        "Pearson r 0 0.28.", "Pearson r −0 −0.5.", "Pearson r −0 −0.21."]
    assert "r 0.68 over 288 months" in links[0] and "r −0.57 over 288" in links[1] and "r −0.61 over 264 months, 2003–2024" in links[2]
    assert sum(k.startswith("File check") for k in table) == 5 and all(
        "288 of 288 months present, 0 fill values, 0 repeated dates" in v for k, v in table.items() if k.startswith("File check"))
    assert sum(k.startswith("What is measured") for k in table) == 5
    wet_season = water(measure="soil")["charts"][4]["y"]
    assert (round(wet_season[0], 1), round(wet_season[21], 1), round(min(wet_season), 1)) == (76.8, 86.8, 63.6), "branch case tab C5"
    wet_bulb = water(measure="wet")["charts"][0]["y"]
    assert (round(wet_bulb[0], 2), round(wet_bulb[-1], 2), round(wet_bulb[21], 2)) == (22.1, 22.54, 22.76), "branch case tab C8"
    soot = haze()["charts"][6]["y"]
    assert (round(soot[0], 3), round(soot[3], 3), round(soot[-1], 3)) == (0.703, 1.115, 0.727), "branch case tabs C2 and C6"
    whole = water(measure="imerg")["facts"]
    assert (whole["ratio_before_share"], whole["ratio_after_share"], whole["sel_seasonal"], whole["sel_anomalies"]) == ("70%", "94%", "0.949", "0.634")
    assert any("jumps after 2016" in n for n in water(measure="soil")["notes"]), "a model series that steps where the satellite rain does not"
    assert not any("jumps after" in n for n in water(measure="soil", span=[2001, 2014])["notes"] + water(measure="imerg")["notes"])


@pytest.mark.parametrize("measure, plain, seasonal, anomalies, after, step_p", [
    ("bc", "0.008", "0.243", "0.093", 2008, "0.059"), ("pm25", "0.264", "0.221", "0.349", 2016, "0.403"),
    ("aod", "0.087", "< 0.001", "< 0.001", 2016, "0.009")])
def test_the_whole_year_aerosol_card_is_fixed_and_matches_the_branch(measure, plain, seasonal, anomalies, after, step_p):
    f = haze(measure=measure, span=[2008, 2020])["facts"]
    assert (f["whole_plain"], f["whole_seasonal"], f["whole_anomalies"], f["whole_step_after"], f["whole_step_p"]) == (
        plain, seasonal, anomalies, after, step_p)
    assert (f["whole_first"], f["whole_last"], f["whole_n"]) == (2001, 2024, 24)


def test_the_plain_fire_links_and_the_whole_record_level_match_the_branch():
    """fire-watch/data/default_view.json: rho 0.7108, 0.2726 (n 240) and 0.5564 (p 0.0108, n 20); case tab C2: 0.79, 1.45, 0.39, 3.7 times."""
    f = haze()["facts"]
    assert (f["plain_raw_rho"], f["plain_anom_rho"], f["plain_season_rho"], f["plain_season_p"]) == ("0.71", "0.27", "0.56", "0.011")
    assert (f["n_months"], f["n_link_seasons"], f["fire_trend_p"]) == (240, 20, "0.928")
    assert (f["record_mean"], f["record_peak"], f["record_low"], f["record_ratio"]) == ("0.788 µg/m³", "1.45 µg/m³", "0.394 µg/m³", "3.7")
    assert (f["record_dry"], f["record_wet"], f["record_peak_month"], f["record_low_month"]) == ("1.08 µg/m³", "0.500 µg/m³", "January", "July")
    assert "PM" not in haze()["investigation"]["limits"][3] and "not a station measurement" in haze(measure="pm25")["investigation"]["limits"][3]


def test_new_panel_text_is_khmer_in_khmer():
    for kind in ("fire", "haze", "water"):
        r = client.post("/api/run", json={"question": {"kind": kind}, "lang": "km"}).json()
        text = " ".join(v for _, v in r["detail"]["rows"]) + " ".join(r["investigation"]["limits"] + r["notes"])
        assert "Second opinions" not in text and "every ten years" not in text and "whole record" not in text
