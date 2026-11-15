import re

from fastapi.testclient import TestClient

from earthbuddy.server import app

client = TestClient(app)


def test_status_reports_ai_as_boolean():
    r = client.get("/api/status")
    assert r.status_code == 200
    assert isinstance(r.json()["ai_available"], bool)


def test_index_has_title_and_no_store():
    for path in ("/", "/index.html"):
        r = client.get(path)
        assert r.status_code == 200 and "<title>Earth Buddy</title>" in r.text
        assert r.headers["cache-control"] == "no-store"


def test_data_dir_is_not_served():
    assert client.get("/data/cache.sqlite").status_code == 404


def test_every_asset_the_page_links_is_served():
    paths = re.findall(r'(?:href|src)="(/[^/"][^"]*)"', client.get("/").text)
    assert "/favicon.svg" in paths
    assert "/favicon.png" in paths
    assert all(client.get(p).status_code == 200 for p in paths), paths
