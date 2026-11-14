"""Telegram update -> one sendMessage reply, returned as the webhook's response body.
A voice message is the one outbound call: its file, fetched with the bot token, then KiriTTS for the words."""
import base64
import functools
import html
import json
import logging
import os
import re

from . import analyses, explainer, net, reader, voice
from .types import Clip, DataSourceError, Lang, QuestionError, Result, VoiceFailed
from .words import Words

log = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)   # its INFO line prints the request URL, which holds the bot token
escape = functools.partial(html.escape, quote=False)   # Telegram HTML needs only < > & escaped
API = "https://api.telegram.org"
EMOJI = {"clear": "🟢", "likely": "🟡", "unclear": "⚪", "too_short": "⏳"}
LANG_BUTTONS: dict[str, Lang] = {"🇰🇭 ខ្មែរ": "km", "🇬🇧 English": "en"}
# Each one answers offline; tests/test_telegram.py runs them all.
EXAMPLES: dict[Lang, list[str]] = {
    "en": ["Cambodia is getting hotter and drier", "Is Phnom Penh getting hotter?",
           "How is rain changing in Siem Reap?", "Where around Phnom Penh is it warming?",
           "Which Cambodian province is warming fastest?", "Which Southeast Asian capital is warming fastest?",
           "What is changing in the Mekong Delta?"],
    "km": ["តើ ភ្នំពេញ កំពុងក្តៅជាងមុនឬទេ?", "តើបរិមាណទឹកភ្លៀងនៅ សៀមរាប បានប្រែប្រួលយ៉ាងដូចម្តេច?",
           "តើតំបន់ណាជុំវិញ ភ្នំពេញ កំពុងឡើងកម្តៅ?", "តើខេត្តណានៃប្រទេសកម្ពុជា កំពុងឡើងកម្តៅលឿនបំផុត?"],
}


def answer(update: dict, base_url: str) -> dict | None:
    """None for an update with no text or voice message (edits, joins, stickers)."""
    message = update.get("message")
    if not isinstance(message, dict) or (chat_id := (message.get("chat") or {}).get("id")) is None:
        return None
    if isinstance(message.get("text"), str):
        reply = _reply(message["text"], base_url)
    elif isinstance(message.get("voice"), dict):
        reply = _voice(message, base_url)
    else:
        return None
    return {"method": "sendMessage", "chat_id": chat_id, "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True}, **reply}


def _voice(message: dict, base_url: str) -> dict:
    """The transcript answered as typed text, under a line that shows what was heard."""
    v = message["voice"]
    lang: Lang = "km" if str((message.get("from") or {}).get("language_code", "")).startswith("km") else "en"
    w = Words(lang)
    if (v.get("duration") or 0) > voice.CLIP_S or (v.get("file_size") or 0) > voice.MAX_CLIP_BYTES:
        return _plain(w("telegram.voice_long", clip_s=voice.CLIP_S))
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token or not voice.status()["available"]:
        return _plain(w("telegram.voice_off"))
    try:
        audio = _download(token, v["file_id"])
        heard = voice.hear(Clip(audio=base64.b64encode(audio).decode(), mime="audio/ogg", lang=lang))
    except QuestionError:
        return _plain(w("telegram.voice_long", clip_s=voice.CLIP_S))
    except VoiceFailed as e:
        return _plain(w(f"telegram.voice_{e.reason}"))
    except Exception as e:   # every Telegram file URL holds the bot token, so log the error type only
        log.error("telegram voice file failed: %s", type(e).__name__)
        return _plain(w("telegram.voice_off"))
    if not heard:
        return _plain(w("telegram.voice_empty"))
    reply = _reply(heard, base_url)
    return {**reply, "text": f"🎤 <i>{escape(heard)}</i>\n\n{reply['text']}"}


def _download(token: str, file_id: str) -> bytes:
    found = json.loads(net.post(f"{API}/bot{token}/getFile", headers={}, json={"file_id": file_id}).body)
    return net.get(f"{API}/file/bot{token}/{found['result']['file_path']}").body


def _plain(text: str) -> dict:
    return {"text": escape(text)}


def _keyboard(rows: list[list[str]], **opts) -> dict:
    return {"reply_markup": {"keyboard": [[{"text": t} for t in row] for row in rows], **opts}}


def _reply(text: str, base_url: str) -> dict:
    if text.split("@", 1)[0].strip() in ("/start", "/help"):
        return {**_plain(Words("en")("telegram.choose")),
                **_keyboard([list(LANG_BUTTONS)], resize_keyboard=True, one_time_keyboard=True)}
    if text in LANG_BUTTONS:
        lang = LANG_BUTTONS[text]
        return {**_plain(Words(lang)("telegram.help")),
                **_keyboard([[q] for q in EXAMPLES[lang]], resize_keyboard=True)}
    lang: Lang = "km" if any("ក" <= ch <= "៿" for ch in text) else "en"
    w = Words(lang)
    try:
        read = reader.read(text, lang)
        if read.question is None:
            return _plain(w("telegram.missing", missing=", ".join(w(f"word.field.{m}") for m in read.missing)))
        result = analyses.run(read.question, lang=lang)
    except QuestionError:
        return _plain(w("telegram.bad_question", max_text=reader.MAX_TEXT))
    except DataSourceError:
        return _plain(w("telegram.source_down"))
    except Exception:
        log.exception("telegram question failed: %r", text)   # a 500 makes Telegram resend the same update
        return _plain(w("telegram.bad_question", max_text=reader.MAX_TEXT))
    return _format(result, explainer.explain(result, "student", lang, net.ai_available()).short, base_url, w)


def _format(result: Result, short: str, base_url: str, w: Words) -> dict:
    body = json.dumps({"question": result.question.model_dump(mode="json"), "revision": 0})
    code = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    headline = "".join(f"<b>{escape(s.t)}</b>" if s.hl else escape(s.t) for s in result.headline)
    text = "\n".join([
        f"{EMOJI[result.verdict.level]} {headline}", "",
        re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(short)), "",
        *(f"• <b>{escape(t.label)}</b>  {escape(t.value)}" for t in result.tiles), "",
        f"<blockquote expandable><b>{escape(w('telegram.sources'))}</b>",
        "\n".join(f"• {escape(s.name)}" for s in result.sources) + "</blockquote>",
    ])
    button = {"text": w("telegram.open"), "url": f"{base_url}#q={code}"}
    return {"text": text, "reply_markup": {"inline_keyboard": [[button]]}}
