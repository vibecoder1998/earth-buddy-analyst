import re

import pytest
from fastapi.testclient import TestClient

from earthbuddy.server import app

client = TestClient(app)
STEPS = [s for c in client.get("/api/cases").json()["cases"] for s in c["steps"]]


def test_fire_watch_cambodia_has_four_steps():
    cases = client.get("/api/cases").json()["cases"]
    assert [(c["id"], len(c["steps"])) for c in cases] == [("fire-watch-cambodia", 4)]


@pytest.mark.parametrize("lang", ["en", "km"])
@pytest.mark.parametrize("step", STEPS, ids=lambda s: s["ask"]["en"])
def test_every_step_runs_with_no_network(step, lang):
    r = client.post("/api/run", json={"question": step["question"], "revision": 0, "lang": lang})
    assert r.status_code == 200, r.text
    assert r.json()["question"] == step["question"]


def test_every_text_is_in_both_languages_with_no_number():
    texts = [t for c in client.get("/api/cases").json()["cases"]
             for pair in (c["title"], c["note"], *(s["ask"] for s in c["steps"])) for t in (pair["en"], pair["km"])]
    assert all(t.strip() and not re.search(r"\d", t) for t in texts), texts
