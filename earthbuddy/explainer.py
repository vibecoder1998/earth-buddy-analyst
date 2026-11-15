"""Plain-language text under a result. Templates always work; AI text is shown only if every number checks out."""
import itertools
import json
import logging
import re
from typing import NamedTuple

from . import net
from .types import AIFailed, Audience, Explanation, Fact, Lang, QuestionError, Result
from .words import Words, mostly_khmer, number_tokens

log = logging.getLogger(__name__)

SYSTEM = """You explain one Earth-science result from NASA data to one reader. You get JSON with the headline, the facts, the audience, and the language.

1. Use only numbers that appear in `facts`, written exactly as they appear there. Write every other amount in words, or leave it out.
2. Call a change clear only when `facts.certainty` or `facts.verdict` says it is clear.
3. "Not clear" means the record cannot tell. It does not mean nothing is happening.
4. Never claim a cause.
5. Write `short` in 2 sentences and under 45 words, with **bold** on 2 or 3 verdict words only. Write `more` in 3 to 5 sentences.
6. Write for the given audience, in the given language."""


class Brief(NamedTuple):
    rule: str        # the one audience line of the prompt
    numbers: bool    # False: the model gets only the facts that hold no number


BRIEFS: dict[Audience, Brief] = {
    "student": Brief("A student gets everyday words and no numbers. Write no digits at all.", False),
    "policymaker": Brief("A policymaker gets what it means for decisions and at most one number.", True),
    "researcher": Brief("A researcher gets at most 3 sentences in `short`, with the slope, the 95% interval, the test, and p.", True),
}
BOLD_MAX = 3

SCHEMA = {
    "type": "object",
    "properties": {"short": {"type": "string"}, "more": {"type": "string"}},
    "required": ["short", "more"],
    "additionalProperties": False,
}


def explain(result: Result, audience: Audience, lang: Lang, ai: bool) -> Explanation:
    try:
        short, more = Words(lang).template(result.verdict.key, audience, result.facts)
    except KeyError as e:
        raise QuestionError("result", f"the result cannot fill its template: {e}") from None
    template = Explanation(short=short, more=more, via="template")
    if not ai or not net.model_writes(lang):
        return template
    brief = BRIEFS[audience]
    shown = result.facts if brief.numbers else {
        k: v for k, v in result.facts.items() if isinstance(v, str) and v and not number_tokens(v)}
    headline = "".join(s.t for s in result.headline)
    sent = {"headline": headline} if brief.numbers or not number_tokens(headline) else {}
    user = json.dumps(sent | {"facts": shown, "audience": audience, "lang": lang}, ensure_ascii=False)
    try:
        reply = net.ask_model(f"{SYSTEM} {brief.rule}", user, SCHEMA, 1024)
    except AIFailed as e:
        log.info("explainer model failed: %s", e)
        return template
    short, more = reply.get("short"), reply.get("more")
    if not (isinstance(short, str) and isinstance(more, str) and short.strip()):
        log.warning("explainer reply has no short/more text: %r", reply)
        return template
    if lang == "km" and not mostly_khmer(f"{short}\n{more}"):
        log.warning("explainer rejected a Khmer reply not written in Khmer: %r", reply)
        return template
    if not numbers_ok(f"{short}\n{more}", shown, _years(result.facts) if brief.numbers else set()):
        log.warning("explainer rejected a reply with a number not in facts: %r", reply)
        return template
    return Explanation(short=_trim_bold(short), more=_trim_bold(more), via="ai")


def numbers_ok(text: str, facts: dict[str, Fact], years: set[int]) -> bool:
    """Every number token in text equals a token inside a fact value, or a year of the result.
    A negative fact also allows its size: "fell by 25%" is right for −25%. The sign never guarded direction."""
    allowed = {str(y) for y in years}
    for v in facts.values():
        if v is not None and not isinstance(v, bool):
            allowed |= number_tokens(str(v))
    allowed |= {t.lstrip("-") for t in allowed}
    return number_tokens(text) <= allowed


def _trim_bold(text: str) -> str:
    n = itertools.count()
    return re.sub(r"\*\*(.+?)\*\*", lambda m: m[0] if next(n) < BOLD_MAX else m[1], text)


def _years(facts: dict[str, Fact]) -> set[int]:
    first, last = facts.get("first_year"), facts.get("last_year")
    return set(range(first, last + 1)) if isinstance(first, int) and isinstance(last, int) else set()
