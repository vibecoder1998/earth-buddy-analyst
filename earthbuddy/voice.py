"""KiriTTS speech in and out. It carries speech only and never supplies a number, a place name, or a source."""
import functools
import hashlib
import hmac
import json
import os
import re
from typing import NamedTuple, get_args
from urllib.parse import urlencode

from . import catalog, net
from .types import Clip, ClipMime, DataSourceError, Explanation, Lang, QuestionError, Tile, VoiceFailed, VoiceReason

API = "https://api.kiritts.com/v1"
CLIP_S = 20
MAX_CLIP_BYTES = 3_000_000    # base64 grows it to 4 MB, under Vercel's 4.5 MB request body limit
MAX_INPUT = 4096              # KiriTTS speech input limit, in characters


class Voice(NamedTuple):
    name: str
    hint: str | None            # None = KiriTTS detects the language
    speed: float = 1.0


VOICES: dict[Lang, Voice] = {"en": Voice("Maly", "en"), "km": Voice("Maly", "km-KH")}
REASONS: dict[int, VoiceReason] = {401: "off", 403: "off", 429: "limit"}

# Symbols a speech engine reads badly. Units stay as written in Khmer, where the templates spell them.
SAY: dict[Lang, dict[str, str]] = {
    "en": {"minus": "minus ", "to": " to ", "°C": " degrees Celsius", "mm/yr": " millimetres per year", "%": " percent"},
    "km": {"minus": "ដក ", "to": " ដល់ "},
}


class Speech(NamedTuple):
    audio: bytes
    mime: str


def _key() -> str:
    return "" if net.OFFLINE else os.environ.get("KIRITTS_API_KEY", "")


def status() -> dict:
    return {"available": bool(_key()), "clip_s": CLIP_S, "mimes": list(get_args(ClipMime))}


def hear(clip: Clip) -> str:
    """The transcript, or "" when nothing was heard. Raises VoiceFailed."""
    if len(clip.audio) > MAX_CLIP_BYTES:
        raise QuestionError("audio", "the recording is too long")
    hint = VOICES[clip.lang].hint
    data = {"model": "kiristt", "prompt": _prompt(clip.lang), "response_format": "json"} | ({"language": hint} if hint else {})
    r = _post("audio/transcriptions", data=data, files={"file": (f"clip.{clip.mime.split('/')[1]}", clip.audio, clip.mime)})
    try:
        out = json.loads(r.body)
    except ValueError:
        raise VoiceFailed("down") from None
    text = out.get("text") if isinstance(out, dict) else None
    return text.strip() if isinstance(text, str) else ""


def voiced(e: Explanation, lang: Lang, tiles: list[Tile]) -> Explanation:
    """Sets e.audio to a signed /api/say URL for the short answer and the code-made tiles. e unchanged when voice is off."""
    key = _key()
    if not key:
        return e
    text = spoken(e.short, tiles, lang)
    return e.model_copy(update={"audio": "/api/say?" + urlencode({"t": text, "lang": lang, "sig": _sign(key, text, lang)})})


def say(text: str, lang: Lang, sig: str) -> Speech:
    """A bad sig raises QuestionError("sig") before any network call."""
    key = _key()
    if not key:
        raise VoiceFailed("off")
    if not hmac.compare_digest(sig, _sign(key, text, lang)):
        raise QuestionError("sig", "the speech link is not signed")
    v = VOICES[lang]
    r = _post("audio/speech", json={"model": "kiritts", "input": text, "voice": v.name, "speed": v.speed,
                                    "response_format": "mp3"})
    if not r.content_type.startswith("audio/"):
        raise VoiceFailed("down")
    return Speech(r.body, r.content_type)


def spoken(short: str, tiles: list[Tile], lang: Lang) -> str:
    parts = [short.replace("**", "")] + [f"{t.label}: {t.value}." + (f" {t.note}" if t.note else "") for t in tiles]
    return _speakable(" ".join(parts), lang)[:MAX_INPUT]


def _speakable(text: str, lang: Lang) -> str:
    words = SAY[lang]
    text = re.sub(r"(\d{4})\u2013(\d{4})", lambda m: f"{m[1]}{words['to']}{m[2]}", text)
    text = text.replace("\u2212", words["minus"])
    for symbol in ("°C", "mm/yr", "%"):
        if symbol in words:
            text = re.sub(r"\s*" + re.escape(symbol), words[symbol], text)
    return text


def _sign(key: str, text: str, lang: Lang) -> str:
    v = VOICES[lang]
    msg = "\n".join([lang, v.name, str(v.speed), text]).encode()
    return hmac.new(key.encode(), msg, hashlib.sha256).hexdigest()


@functools.cache
def _prompt(lang: Lang) -> str:
    """Place names from the catalog, so the transcript spells them the way the reader finds them."""
    return ", ".join(p.name(lang) for p in catalog.load().places)


def _post(path: str, **kw) -> net.Posted:
    key = _key()
    if not key:
        raise VoiceFailed("off")
    try:
        return net.post(f"{API}/{path}", headers={"Authorization": f"Bearer {key}"}, **kw)
    except DataSourceError as e:
        raise VoiceFailed(REASONS.get(e.status, "down")) from None
