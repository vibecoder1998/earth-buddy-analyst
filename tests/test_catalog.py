import json
from pathlib import Path

import pytest

from earthbuddy import catalog
from earthbuddy.catalog import DATA
from earthbuddy.types import Country, Place, QuestionError

def test_counts():
    c = catalog.load()
    assert (len(c.variables), len(c.places)) == (27, 43)
    assert len(c.countries) >= 200
    assert {g.id for g in c.groups} == {"southeast_asia_capitals", "cambodia_provinces", "countries", "places"}


def test_series_lengths_match_years():
    lo, hi = catalog.years()
    for v in catalog.variables():
        f = json.loads((DATA / "v" / f"{v.id}.json").read_text())
        assert tuple(f["years"]) == (lo, hi), v.id
        assert {len(s) for s in f["regions"].values()} == {hi - lo + 1}, v.id
        assert {p.id for p in catalog.load().places} <= set(f["regions"]), v.id


def test_variable_source_ids_in_registry():
    registry = {s.id for s in catalog.sources()}
    assert all(set(v.source.ids) <= registry for v in catalog.variables())


def test_point_params_and_first_years():
    aerosol = catalog.variable("aerosol")
    assert (aerosol.point_param, aerosol.first_year) == ("AOD_55_ADJ", 2001)
    assert "ceres-syn1deg" in aerosol.source.ids
    assert (catalog.variable("heat").first_year, catalog.variable("sun").first_year) == (1981, 1984)
    assert catalog.variable("fire").point_param is None


def test_find_region_phnom_penh_offline():
    assert catalog.find_region("is it hot in phnom penh", "en") == Place(id="p.phnom-penh")
    assert catalog.find_region("ក្តៅនៅភ្នំពេញទេ", "km") == Place(id="p.phnom-penh")
    assert catalog.find_region("phnom penhx", "en") is None


def test_khmer_falls_back_to_english():
    places = catalog.group("places")
    assert places.name.km is None
    assert places.name("km") == places.name("en")
    assert catalog.name(Place(id="p.phnom-penh"), "km") == "ភ្នំពេញ"


def test_regional_values_unknown_region_is_a_question_error():
    assert len(catalog.regional_values("heat", Place(id="p.phnom-penh"))) == 24
    with pytest.raises(QuestionError) as e:
        catalog.regional_values("heat", Place(id="p.atlantis"))
    assert e.value.field == "region"


def test_audit_claims_use_spec_keys():
    claims = catalog.audit()["claims"]
    assert len(claims) == 8
    assert all("known_before" in c and "knownBefore" not in c for c in claims)


def test_find_region_country():
    assert catalog.find_region("ukraine rain", "en") == Country(iso3="UKR")
    assert catalog.name(Country(iso3="KHM"), "km") == "កម្ពុជា"


def test_cambodia_has_25_province_entries():
    gazetteer = json.loads((DATA / "gazetteer.json").read_text())
    assert sum(e["iso3"] == "KHM" and e["level"] == 1 for e in gazetteer) == 25
    members = catalog.group("cambodia_provinces").members
    assert len(members) == 25
    assert all(10 <= m.lat <= 15 and 102 <= m.lon <= 108 for m in members)


def test_khm_heat_within_0_2_of_snapshot():
    snapshot = Path.home() / "earth-buddy-claimdesk-snapshot" / "data" / "v" / "heat.json"
    old = json.loads(snapshot.read_text())["regions"]["KHM"]
    new = catalog.regional_values("heat", Country(iso3="KHM"))
    assert max(abs(a - b) for a, b in zip(new, old)) <= 0.2


def test_find_region_longest_match_wins_across_places_and_countries():
    assert catalog.find_region("dr congo rain", "en") == Country(iso3="COD")
    assert catalog.find_region("western sahara heat", "en") == Country(iso3="ESH")
    assert catalog.find_region("is it hot in phnom penh", "en") == Place(id="p.phnom-penh")
    assert catalog.find_region("ukraine rain", "en") == Country(iso3="UKR")


def test_group_members_match_sedac_and_common_spellings():
    assert catalog.find_region("rain in ratanak kiri", "en").name == "Ratanakiri, Cambodia"
    assert catalog.find_region("heat in naypyidaw", "en").name == "Nay Pyi Taw, Myanmar"


def test_provinces_sit_in_distinct_merra2_cells():
    def cell(m):
        return round(m.lat / 0.5), round(m.lon / 0.625)

    members = {m.name.split(",")[0]: m for m in catalog.group("cambodia_provinces").members}
    shared = {}
    for name, m in members.items():
        shared.setdefault(cell(m), []).append(name)
    assert [sorted(n) for n in shared.values() if len(n) > 1] == [["Kandal", "Phnom Penh"]]
    assert cell(members["Kampong Cham"]) != cell(members["Tbong Khmum"])
    gazetteer = json.loads((DATA / "gazetteer.json").read_text())
    assert [e["name"] for e in gazetteer if e.get("composed")] == ["Tbong Khmum"]


@pytest.mark.skip(reason="EB-05: summary.json needs stats.trend_test")
def test_summary_has_every_regional_variable():
    summary = json.loads((DATA / "summary.json").read_text())
    assert {v.id for v in catalog.variables() if v.regional} <= set(summary)
