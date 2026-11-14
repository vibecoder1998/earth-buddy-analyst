import base64
import json
import re

import httpx
import pytest
from fastapi.testclient import TestClient

from earthbuddy import fixtures, net
from earthbuddy.server import app
from earthbuddy.telegram import EXAMPLES

client = TestClient(app)
SECRET = "s3cret"


@pytest.fixture(autouse=True)
def bot(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(net, "OFFLINE", True)


def send(update: dict, secret: str = SECRET):
    return client.post("/api/telegram", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": secret})


def text_update(text: str) -> dict:
    return {"update_id": 1, "message": {"message_id": 7, "chat": {"id": 42, "type": "private"}, "text": text}}


def test_a_demo_sentence_gets_the_answer_and_a_button_that_reopens_it():
    r = send(text_update("Cambodia is getting hotter and drier"))
    assert r.status_code == 200
    reply = r.json()
    assert (reply["method"], reply["chat_id"], reply["parse_mode"]) == ("sendMessage", 42, "HTML")
    [[button]] = reply["reply_markup"]["inline_keyboard"]
    link = button["url"]
    assert link.startswith("http://testserver/#q=") and "#q=" not in reply["text"]
    code = link.split("#q=")[1]
    body = json.loads(base64.urlsafe_b64decode(code + "=" * (-len(code) % 4)))
    assert body["revision"] == 0 and body["question"]["kind"] == "claim"
    result = client.post("/api/run", json={**body, "lang": "en"}).json()
    plain = re.sub(r"<[^>]+>", "", reply["text"])
    assert "".join(s["t"] for s in result["headline"]) in plain.splitlines()[0]
    assert all(t["label"] in plain and t["value"] in plain for t in result["tiles"])


def test_dynamic_text_is_escaped_for_telegram_html(monkeypatch):
    from earthbuddy import explainer
    real = explainer.explain
    monkeypatch.setattr(explainer, "explain",
                        lambda *a, **k: real(*a, **k).model_copy(update={"short": "a < b & c **d**"}))
    text = send(text_update("Cambodia is getting hotter and drier")).json()["text"]
    assert "a &lt; b &amp; c <b>d</b>" in text


KHMER = re.compile("[\u1780-\u17ff]")


def buttons(reply: dict) -> list[str]:
    return [b["text"] for row in reply["reply_markup"]["keyboard"] for b in row]


@pytest.mark.parametrize("cmd", ["/start", "/help", "/start@EarthBuddyBot"])
def test_start_asks_which_language(cmd):
    assert buttons(send(text_update(cmd)).json()) == ["🇰🇭 ខ្មែរ", "🇬🇧 English"]


@pytest.mark.parametrize("label, lang", [("🇰🇭 ខ្មែរ", "km"), ("🇬🇧 English", "en")])
def test_picking_a_language_greets_in_it_and_offers_its_examples(label, lang):
    reply = send(text_update(label)).json()
    assert bool(KHMER.search(reply["text"])) == (lang == "km")
    assert buttons(reply) == EXAMPLES[lang]


@pytest.mark.parametrize("question", [q for qs in EXAMPLES.values() for q in qs])
def test_every_example_gets_an_answer_with_the_open_button(question):
    net.stub(transport=httpx.MockTransport(fixtures.handler))   # EB_OFFLINE=1 data
    [[button]] = send(text_update(question)).json()["reply_markup"]["inline_keyboard"]
    assert "#q=" in button["url"]


def test_a_khmer_message_the_reader_cannot_place_gets_khmer():
    assert KHMER.search(send(text_update("សួស្តី")).json()["text"])


def test_an_english_message_the_reader_cannot_place_gets_english():
    assert not KHMER.search(send(text_update("hello")).json()["text"])


def test_a_crash_still_gets_a_reply_so_telegram_does_not_resend(monkeypatch):
    from earthbuddy import analyses
    monkeypatch.setattr(analyses, "run", lambda *a, **k: 1 / 0)
    r = send(text_update("Cambodia is getting hotter and drier"))
    assert r.status_code == 200 and r.json()["method"] == "sendMessage"


def test_an_over_long_text_gets_a_friendly_reply():
    r = send(text_update("rain " * 200))
    assert r.status_code == 200 and r.json()["method"] == "sendMessage"


def test_a_non_text_update_gets_an_empty_body():
    r = send({"update_id": 2, "message": {"message_id": 8, "chat": {"id": 42}, "sticker": {"file_id": "x"}}})
    assert (r.status_code, r.json()) == (200, {})


def test_a_wrong_secret_is_forbidden():
    assert send(text_update("/start"), secret="nope").status_code == 403


def test_no_secret_configured_hides_the_route(monkeypatch):
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET")
    assert send(text_update("/start")).status_code == 404
