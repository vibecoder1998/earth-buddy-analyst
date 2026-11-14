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


TOKEN = "123456:bot-token-secret"
HEARD = "Is Phnom Penh getting hotter?"


def voice_update(duration: int = 3, language_code: str = "en-US") -> dict:
    return {"update_id": 3, "message": {"message_id": 9, "chat": {"id": 42, "type": "private"},
                                        "from": {"id": 5, "language_code": language_code},
                                        "voice": {"file_id": "F1", "duration": duration, "mime_type": "audio/ogg"}}}


@pytest.fixture
def voice_on(monkeypatch):
    """voice._key() reads KIRITTS_API_KEY only when net.OFFLINE is False. Clearing AWS keeps AI off."""
    monkeypatch.setattr(net, "OFFLINE", False)
    for k in ("AWS_BEARER_TOKEN_BEDROCK", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("KIRITTS_API_KEY", "kiri-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)


def hearing(text: str = HEARD, get_file: httpx.Response | None = None, kiri: httpx.Response | None = None) -> list[str]:
    """Stubs Telegram, KiriTTS, and synthetic NASA data. Returns the Telegram and KiriTTS URLs called."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.url.host in ("api.telegram.org", "api.kiritts.com"):
            seen.append(url)
        if url == f"https://api.telegram.org/bot{TOKEN}/getFile":
            assert json.loads(request.content) == {"file_id": "F1"}
            return get_file or httpx.Response(200, json={"ok": True, "result": {"file_path": "voice/f1.oga"}})
        if url == f"https://api.telegram.org/file/bot{TOKEN}/voice/f1.oga":
            return httpx.Response(200, content=b"OggS fake opus")
        if url == "https://api.kiritts.com/v1/audio/transcriptions":
            assert b"OggS fake opus" in request.content
            return kiri or httpx.Response(200, json={"text": text})
        return fixtures.handler(request)

    net.stub(transport=httpx.MockTransport(handler))
    return seen


def test_a_voice_message_is_answered_like_the_typed_transcript(voice_on):
    hearing()
    reply = send(voice_update()).json()
    assert reply["text"].startswith(f"🎤 <i>{HEARD}</i>\n\n")
    [[button]] = reply["reply_markup"]["inline_keyboard"]
    assert "#q=" in button["url"]
    typed = send(text_update(HEARD)).json()
    assert reply["text"].endswith(typed["text"]) and reply["reply_markup"] == typed["reply_markup"]


def test_a_khmer_transcript_gets_a_khmer_answer(voice_on):
    hearing(EXAMPLES["km"][0])
    reply = send(voice_update(language_code="km")).json()
    assert "inline_keyboard" in reply["reply_markup"]
    assert KHMER.search(reply["text"].split("\n\n", 1)[1])


def test_a_long_voice_message_is_refused_before_any_call(voice_on):
    reply = send(voice_update(duration=60)).json()   # the sealed transport fails the test on any call
    assert "20 seconds" in reply["text"]


def test_no_bot_token_means_voice_is_not_available(voice_on, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
    assert send(voice_update()).json()["text"] == "Voice is not available. Please type your question."


def test_kiritts_out_of_credit_gets_the_limit_reply(voice_on):
    hearing(kiri=httpx.Response(429))
    assert "credit" in send(voice_update()).json()["text"]


def test_nothing_heard_asks_again(voice_on):
    hearing("")
    assert send(voice_update()).json()["text"] == "I could not hear a question. Please try again or type it."


def test_a_telegram_failure_never_shows_the_token(voice_on, caplog):
    seen = hearing(get_file=httpx.Response(500))
    r = send(voice_update())
    assert r.status_code == 200
    assert r.json()["text"] == "Voice is not available. Please type your question."
    assert len(seen) == 2   # one retry, then a friendly reply
    assert TOKEN not in r.text and TOKEN not in caplog.text
