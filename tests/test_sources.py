import json
import re

import pytest
from fastapi.testclient import TestClient

from earthbuddy import ROOT, SOURCES, analyses, catalog, net, reader
from earthbuddy.server import app

ACKNOWLEDGEMENT_ONLY = {"power", "gibs-bluemarble"}
NON_DATA_HOSTS = {"api.anthropic.com", "doi.org"}
SCHEME_URL = re.compile(r"\b(?:https?|wss?):?//([a-z0-9.-]*)", re.I)
BARE_URL = re.compile(r"(?<![:/\w])//([a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,})\b", re.I)
REMOVED = (b"naturalearth", b"nominatim", b"open-meteo", b"openstreetmap")


def bad_hosts(text: str) -> list[str]:
    hosts = SCHEME_URL.findall(text) + BARE_URL.findall(text)
    return [h or "<built at run time>" for h in hosts if not (net.is_data_host(h) or h.lower() in NON_DATA_HOSTS)]


def files_under(*dirs: str):
    return [p for d in dirs for p in (ROOT / d).rglob("*") if p.is_file() and "__pycache__" not in p.parts]


def test_every_agency_is_allowed():
    bad = [(s.id, s.agency) for s in catalog.sources() if s.agency not in catalog.ALLOWED_AGENCIES]
    assert not bad, bad


def test_ids_are_unique():
    ids = [s.id for s in catalog.sources()]
    assert len(ids) == len(set(ids))


def test_every_entry_has_citation_and_doi_or_acknowledgement():
    bad = [s.id for s in catalog.sources() if not s.citation or not (s.doi or s.id in ACKNOWLEDGEMENT_ONLY)]
    assert not bad, bad


def test_acknowledgements_quote_the_provider_text():
    doc = (ROOT / "docs" / "16-data-sources.md").read_text()
    by_id = {s.id: s for s in catalog.sources()}
    assert all(f'"{by_id[i].citation}"' in doc for i in ACKNOWLEDGEMENT_ONLY)


def test_no_url_outside_allowed_hosts():
    bad = []
    for p in files_under("earthbuddy", "web"):
        try:
            text = p.read_text()
        except UnicodeDecodeError:
            continue
        bad += [f"{p.relative_to(ROOT)}: {host}" for host in bad_hosts(text)]
    assert not bad, bad


@pytest.mark.parametrize("planted", [
    'f"https://{host}/api"',
    '"https://" + "nominatim.openstreetmap.org"',
    'src="//tile.openstreetmap.org/1/2/3.png"',
    'HTTPS://API.OPEN-METEO.COM/v1',
    'new WebSocket("wss://example.com/live")',
    'url("https//evil.example.com/x.svg")',
])
def test_host_scan_catches_planted_urls(planted):
    assert bad_hosts(planted)


@pytest.mark.parametrize("fine", [
    "https://power.larc.nasa.gov/api", "HTTPS://GIBS.EARTHDATA.NASA.GOV/wmts", "https://doi.org/10.5067/x",
    "//nasa-power.s3.amazonaws.com/zarr", "years // 10", "# comment // not a url",
])
def test_host_scan_passes_allowed_urls(fine):
    assert not bad_hosts(fine)


def test_no_removed_provider_in_code_data_or_web():
    bad = [f"{p.relative_to(ROOT)}: {w.decode()}" for p in files_under("earthbuddy", "web", "data", "tools")
           for w in REMOVED if w in p.read_bytes().lower()]
    assert not bad, bad


def test_api_sources_serves_the_registry():
    r = TestClient(app).get("/api/sources")
    assert r.status_code == 200
    assert [s["id"] for s in r.json()] == [s["id"] for s in json.loads(SOURCES.read_text())]


def test_net_refuses_an_unregistered_source():
    with pytest.raises(ValueError, match="'unregistered' is not in data/sources.json"):
        net.get_json("https://power.larc.nasa.gov/api", ttl_days=1, source="unregistered")


@pytest.mark.parametrize("url", [
    "https://api.open-meteo.com/v1/forecast", "https://doi.org/10.5067/x", "https://power.larc.nasa.gov.evil.com/api",
    "https://evil.com/?h=power.larc.nasa.gov", "https://user@evil.com",
])
def test_net_refuses_a_host_outside_the_data_hosts(url):
    with pytest.raises(ValueError, match="is not on an allowed data host"):
        net.get_json(url, ttl_days=1, source="power")


@pytest.mark.parametrize("text", [
    "Cambodia is getting hotter and drier", "Phnom Penh is getting hotter and drier",
])
def test_every_result_source_is_a_registry_entry(text):
    question = reader.read(text, "en", ai=False).question
    registry = [s.model_dump(exclude={"cached"}) for s in catalog.sources()]
    sources = analyses.run(question).sources
    assert sources and all(s.model_dump(exclude={"cached"}) in registry for s in sources)
