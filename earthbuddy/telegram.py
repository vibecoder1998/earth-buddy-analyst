"""Telegram update -> one sendMessage reply, returned as the webhook's response body. No outbound HTTP."""
import base64
import json

from . import analyses, explainer, net, reader
from .types import DataSourceError, Lang, QuestionError, Result
from .words import Words


def answer(update: dict, base_url: str) -> dict | None:
    """None for an update with no text message (edits, joins, stickers)."""
    message = update.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("text"), str):
        return None
    chat_id = (message.get("chat") or {}).get("id")
    if chat_id is None:
        return None
    return {"method": "sendMessage", "chat_id": chat_id, "text": _reply(message["text"], base_url)}


def _reply(text: str, base_url: str) -> str:
    lang: Lang = "km" if any("ក" <= ch <= "៿" for ch in text) else "en"
    w = Words(lang)
    if text.split(maxsplit=1)[:1] in (["/start"], ["/help"]):
        return w("telegram.help")
    try:
        read = reader.read(text, lang, ai=net.ai_available())
        if read.question is None:
            return w("telegram.missing", missing=", ".join(read.missing))
        result = analyses.run(read.question, lang=lang)
    except QuestionError:
        return w("telegram.bad_question", max_text=reader.MAX_TEXT)
    except DataSourceError:
        return w("telegram.source_down")
    return _format(result, explainer.explain(result, "student", lang, net.ai_available()).short, base_url, w)


def _format(result: Result, short: str, base_url: str, w: Words) -> str:
    body = json.dumps({"question": result.question.model_dump(mode="json"), "revision": 0})
    code = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    return "\n".join([
        "".join(s.t for s in result.headline), "", short.replace("**", ""), "",
        *(f"{t.label}: {t.value}" for t in result.tiles), "",
        w("telegram.sources"), *(f"- {s.name}" for s in result.sources), "",
        f"{base_url}#q={code}",
    ])
