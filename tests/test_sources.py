import json
import re

import pytest
from fastapi.testclient import TestClient

from earthbuddy import ROOT, SOURCES, analyses, catalog, net, reader
from earthbuddy.server import app

ACKNOWLEDGEMENT_ONLY = {"power", "gibs-bluemarble"}
ALLOWED_HOSTS = {"nasa-power.s3.amazonaws.com", "api.anthropic.com", "doi.org"}
URL = re.compile(r"https?://([A-Za-z0-9.-]+)")


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
    files = [p for d in ("earthbuddy", "web") for p in (ROOT / d).rglob("*") if p.suffix in {".py", ".html", ".js", ".css"}]
    bad = [f"{p.relative_to(ROOT)}: {host}" for p in files for host in URL.findall(p.read_text())
           if not (host.endswith(".nasa.gov") or host in ALLOWED_HOSTS)]
    assert not bad, bad


def test_api_sources_serves_the_registry():
    r = TestClient(app).get("/api/sources")
    assert r.status_code == 200
    assert [s["id"] for s in r.json()] == [s["id"] for s in json.loads(SOURCES.read_text())]


def test_net_refuses_an_unregistered_source():
    with pytest.raises(ValueError, match="unregistered"):
        net.get_json("https://power.larc.nasa.gov/api", ttl_days=1, source="unregistered")


@pytest.mark.parametrize("text", [
    pytest.param("Cambodia is getting hotter and drier",
                 marks=pytest.mark.skipif(not catalog.load().countries,
                                          reason="EB-03 phase B: data/catalog.json has no country regions yet")),
    "Phnom Penh is getting hotter and drier",
    "How is rain changing in Siem Reap?",
])
def test_every_result_source_is_a_registry_entry(text):
    question = reader.read(text, "en", ai=False).question
    registry = [s.model_dump(exclude={"cached"}) for s in catalog.sources()]
    sources = analyses.run(question).sources
    assert sources and all(s.model_dump(exclude={"cached"}) in registry for s in sources)
