import base64
from array import array
import json
from typing import get_args
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

from earthbuddy import ROOT, analyses, net, reader, voice
from earthbuddy.server import app
from earthbuddy.types import Explanation, Lang, Result

client = TestClient(app)
KEY = "test-key"
CLIP = {"audio": base64.b64encode(b"\x1aE\xdf\xa3 fake webm").decode(), "mime": "audio/webm", "lang": "en"}
WAV = httpx.Response(200, content=b"RIFF wav bytes", headers={"content-type": "audio/wav"})


class Kiri:
    """A stubbed KiriTTS: answers from a queue and records every request."""

    def __init__(self, *replies: httpx.Response):
        self.replies, self.seen = list(replies), []
        net.stub(transport=httpx.MockTransport(self._answer))

    def _answer(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        return self.replies.pop(0)


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setattr(net, "OFFLINE", False)
    monkeypatch.setenv("KIRITTS_API_KEY", KEY)


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.setattr(net, "OFFLINE", False)
    monkeypatch.delenv("KIRITTS_API_KEY", raising=False)


@pytest.fixture
def result():
    question = reader.read("How is rain changing in Siem Reap?", "en").question
    return analyses.run(question).model_dump(mode="json")


def _explain(result, lang="en") -> dict:
    r = client.post("/api/explain", json={"result": result, "lang": lang})
    assert r.status_code == 200
    return r.json()


def test_voices_has_one_row_per_lang():
    assert set(voice.VOICES) == set(get_args(Lang))


def test_spoken_answer_is_the_short_then_every_tile_made_speakable(key, result):
    x = _explain(result)
    assert KEY not in x["audio"]
    kiri = Kiri(WAV)
    r = client.get(x["audio"])
    assert r.status_code == 200 and r.content == b"RIFF wav bytes" and r.headers["content-type"] == "audio/wav"
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
    [req] = kiri.seen
    assert req.url == "https://api.kiritts.com/v1/audio/speech"
    assert req.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(req.content)
    assert body | {"input": ""} == {"model": "kiritts", "input": "", "voice": "Maly", "speed": 1.0,
                                     "response_format": "wav", "stream_format": "audio"}
    spoken = body["input"]
    assert spoken.startswith(x["short"].replace("**", "") + " ")
    assert "**" not in spoken and "−" not in spoken and "–" not in spoken
    assert "minus 160 millimetres per year" in spoken
    assert "2001 to 2024" in spoken
    assert "95 percent range" in spoken
    assert all(f"{t['label']}: " in spoken for t in result["tiles"])


def test_khmer_keeps_units_but_reads_the_minus_and_the_year_span(key):
    assert voice._speakable("−160 mm/yr, 2001–2024", "km") == "ដក 160 mm/yr, 2001 ដល់ 2024"


def test_a_changed_text_is_refused_before_any_call(key, result):
    url = urlsplit(_explain(result)["audio"])
    q = {k: v[0] for k, v in parse_qs(url.query).items()}
    kiri = Kiri()
    r = client.get(url.path, params={**q, "t": q["t"] + " Also, it is snowing."})
    assert r.status_code == 400 and r.json()["field"] == "sig"
    assert client.get(url.path, params={**q, "lang": "km"}).json()["field"] == "sig"
    assert kiri.seen == []


def test_a_speech_reply_that_is_not_audio_is_down(key, result):
    Kiri(httpx.Response(200, json={"oops": True}))
    r = client.get(_explain(result)["audio"])
    assert r.status_code == 503 and r.json() == {"error": "voice is not available", "kind": "voice", "reason": "down"}
    assert "cache-control" not in r.headers


@pytest.mark.parametrize("lang, hint, place", [("en", b"en", "Siem Reap"), ("km", b"km-KH", "សៀមរាប")])
def test_hear_sends_model_hint_prompt_and_file(key, lang, hint, place):
    kiri = Kiri(httpx.Response(200, json={"text": "  How is rain changing in Siem Reap?  "}))
    r = client.post("/api/hear", json={**CLIP, "lang": lang})
    assert r.status_code == 200 and r.json() == {"text": "How is rain changing in Siem Reap?"}
    [req] = kiri.seen
    assert req.url == "https://api.kiritts.com/v1/audio/transcriptions"
    form = req.content
    assert b'name="model"\r\n\r\nkiristt\r\n' in form
    assert b'name="language"\r\n\r\n' + hint + b"\r\n" in form
    assert place.encode() in form.split(b'name="prompt"')[1]
    assert b'filename="clip.webm"\r\nContent-Type: audio/webm\r\n\r\n\x1aE\xdf\xa3 fake webm' in form


@pytest.mark.parametrize("reply", [{"text": ""}, {}, {"text": None}])
def test_an_empty_transcript_is_an_empty_text(key, reply):
    Kiri(httpx.Response(200, json=reply))
    r = client.post("/api/hear", json=CLIP)
    assert r.status_code == 200 and r.json() == {"text": ""}


@pytest.mark.parametrize("change, field", [
    ({"mime": "audio/mpeg"}, "mime"),
    ({"audio": "not base64!"}, "audio"),
    ({"audio": ""}, "audio"),
    ({"audio": base64.b64encode(b"x" * (voice.MAX_CLIP_BYTES + 1)).decode()}, "audio"),
])
def test_a_bad_clip_is_a_400_naming_the_field(key, change, field):
    kiri = Kiri()
    r = client.post("/api/hear", json={**CLIP, **change})
    assert r.status_code == 400 and r.json()["field"] == field
    assert kiri.seen == []


@pytest.mark.parametrize("statuses, reason", [([429], "limit"), ([401], "off"), ([403], "off"), ([500, 500], "down")])
def test_kiritts_errors_map_to_a_reason(key, statuses, reason):
    kiri = Kiri(*(httpx.Response(s) for s in statuses))
    r = client.post("/api/hear", json=CLIP)
    assert r.status_code == 503 and r.json()["reason"] == reason
    assert len(kiri.seen) == len(statuses)


def test_one_5xx_is_retried(key):
    kiri = Kiri(httpx.Response(502), httpx.Response(200, json={"text": "Is Phnom Penh getting hotter?"}))
    assert client.post("/api/hear", json=CLIP).json() == {"text": "Is Phnom Penh getting hotter?"}
    assert len(kiri.seen) == 2


def test_without_a_key_voice_is_off_and_silent(no_key, result):
    assert client.get("/api/status").json()["voice"] == {"available": False, "clip_s": voice.CLIP_S,
                                                         "mimes": ["audio/webm", "audio/mp4", "audio/ogg", "audio/wav"]}
    x = _explain(result)
    assert x["audio"] is None
    r = client.post("/api/hear", json=CLIP)
    assert r.status_code == 503 and r.json()["reason"] == "off"


def test_voiced_is_identity_without_a_key(no_key, result):
    e = Explanation(short="It is **not clear**.", more="More.", via="template")
    assert voice.voiced(e, "en", Result.model_validate(result).tiles) is e


def test_the_text_answer_is_the_same_with_and_without_a_key(monkeypatch, no_key, result):
    without = _explain(result)
    monkeypatch.setenv("KIRITTS_API_KEY", KEY)
    with_key = _explain(result)
    assert {k: without[k] for k in ("short", "more", "via")} == {k: with_key[k] for k in ("short", "more", "via")}
    assert with_key["audio"].startswith("/api/say?")


def test_offline_mode_turns_voice_off(monkeypatch, key):
    monkeypatch.setattr(net, "OFFLINE", True)
    assert client.get("/api/status").json()["voice"]["available"] is False


def test_readme_names_kiritts_for_speech_only():
    ai_use = (ROOT / "README.md").read_text().split("## AI use", 1)[1]
    assert "KiriTTS" in ai_use and "speech to text" in ai_use and "text to speech" in ai_use


def _wav(rate: int, samples: list[int]) -> bytes:
    head = (b"RIFF" + (0xFFFFFFFF).to_bytes(4, "little") + b"WAVEfmt " + (16).to_bytes(4, "little") + b"\x01\x00\x01\x00"
            + rate.to_bytes(4, "little") + (2 * rate).to_bytes(4, "little") + b"\x02\x00\x10\x00data" + (0xFFFFFFFF).to_bytes(4, "little"))
    return head + array("h", samples).tobytes()


def test_spoken_wav_reaches_the_browser_at_16_khz_whatever_the_chunking(key, result):
    url = _explain(result)["audio"]
    wav = _wav(48_000, [3, 6, 9, -3, -6, -9, 30, 0, 0, 7])
    Kiri(httpx.Response(200, content=wav, headers={"content-type": "audio/wav"}))
    out = client.get(url).content
    assert int.from_bytes(out[24:28], "little") == 16_000 and int.from_bytes(out[28:32], "little") == 32_000
    assert array("h", out[44:]).tolist() == [6, -6, 10]
    assert b"".join(voice._downsampled(iter([wav[:7], wav[7:50], wav[50:51], wav[51:]]))) == out
