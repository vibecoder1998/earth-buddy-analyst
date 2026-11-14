import json
import os
import subprocess
import sys

import pytest

from earthbuddy import ROOT, geocode
from earthbuddy.words import Words

ENTRIES = [
    {"name": "Cambodia", "alt_names": [], "iso3": "KHM", "level": 0, "lat": 12.7, "lon": 104.9},
    {"name": "Viet Nam", "alt_names": ["Vietnam"], "iso3": "VNM", "level": 0, "lat": 16.1, "lon": 106.3},
    {"name": "Batdorf", "alt_names": ["Bat Dorf"], "iso3": "KHM", "level": 2, "lat": 13.09, "lon": 103.2},
    {"name": "Batdorf", "alt_names": ["Bat Dorf"], "iso3": "KHM", "level": 1, "lat": 13.03, "lon": 102.99},
    {"name": "Batdorf Kraom", "alt_names": [], "iso3": "KHM", "level": 2, "lat": 13.1, "lon": 103.3},
    {"name": "Sơn La", "alt_names": [], "iso3": "VNM", "level": 1, "lat": 21.3, "lon": 103.9},
    *({"name": f"Banan {i}", "alt_names": [], "iso3": "KHM", "level": 2, "lat": 13.0, "lon": 103.0} for i in range(6)),
]


@pytest.fixture
def gazetteer(tmp_path, monkeypatch):
    path = tmp_path / "gazetteer.json"
    path.write_text(json.dumps(ENTRIES))
    monkeypatch.setattr(geocode, "GAZETTEER", path)
    geocode._gazetteer.cache_clear()
    yield
    geocode._gazetteer.cache_clear()


def test_coordinates_parse():
    [p] = geocode.search(" 11.55 , 104.92 ")
    assert (p.lat, p.lon, p.name) == (11.55, 104.92, "the point 11.55, 104.92")
    assert geocode.search("-33.9,18.4")[0].lat == -33.9
    assert geocode.search("95, 10") == []


def test_a_coordinate_point_opens_a_headline_as_a_name():
    [p] = geocode.search("11.55, 104.92")
    facts = {"place": p.name, "noun": "average air temperature", "direction": "rising",
             "change_per_decade": "0.28 °C", "first_year": 1981}
    assert Words("en").headline("trend.clear", facts)[0].t == "The point 11.55, 104.92's average air temperature is "


def test_catalog_place_is_its_centre():
    [p] = geocode.search("Phnom Penh")
    assert (p.name, p.lat, p.lon) == ("Phnom Penh", 11.5, 104.5)


def test_gazetteer_ranks_exact_then_province_and_names_the_country(gazetteer):
    got = geocode.search("batdorf")
    assert [p.name for p in got] == ["Batdorf, Cambodia", "Batdorf, Cambodia", "Batdorf Kraom, Cambodia"]
    assert (got[0].lat, got[0].lon) == (13.03, 102.99)


def test_gazetteer_ignores_accents_and_matches_alt_names(gazetteer):
    assert [p.name for p in geocode.search("son la")] == ["Sơn La, Viet Nam"]
    assert geocode.search("BAT DORF")[0].name == "Batdorf, Cambodia"


def test_gazetteer_returns_at_most_five(gazetteer):
    assert len(geocode.search("ba")) == 5


def test_unknown_name_returns_empty(gazetteer):
    assert geocode.search("Xyzzyville") == []
    assert geocode.search("   ") == []


def test_battambang_offline():
    p = geocode.search("Battambang")[0]
    assert p.name == "Battambang, Cambodia"
    assert abs(p.lat - 13.1) <= 0.5 and abs(p.lon - 103.2) <= 0.5


def test_offline_on_vercel_refuses_to_start():
    env = {**os.environ, "EB_OFFLINE": "1", "VERCEL": "1"}
    r = subprocess.run([sys.executable, "-c", "import earthbuddy.server"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode != 0 and "EB_OFFLINE=1" in r.stderr and "Vercel" in r.stderr
