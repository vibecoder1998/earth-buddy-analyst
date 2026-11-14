from fastapi.testclient import TestClient

from earthbuddy.server import app

client = TestClient(app)


def test_status_reports_ai_as_boolean():
    r = client.get("/api/status")
    assert r.status_code == 200
    assert isinstance(r.json()["ai_available"], bool)


def test_index_has_title_and_no_store():
    r = client.get("/")
    assert r.status_code == 200 and "<title>Earth Buddy</title>" in r.text
    assert r.headers["cache-control"] == "no-store"


def test_data_dir_is_not_served():
    assert client.get("/data/cache.sqlite").status_code == 404
