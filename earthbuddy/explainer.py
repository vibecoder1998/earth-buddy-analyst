"""Plain-language text under a result. Templates always work; AI text is shown only if every number checks out."""
import json
import logging

from . import net
from .types import AIFailed, Audience, Explanation, Fact, Lang, Result
from .words import Words, number_tokens

log = logging.getLogger(__name__)

SYSTEM = """You explain one Earth-science result from NASA data to one reader. You get JSON with the headline, the facts, the audience, and the language.

1. Use only numbers that appear in `facts`, written exactly as they appear there. Write every other amount in words, or leave it out.
2. Call a change clear only when `facts.certainty` or `facts.verdict` says it is clear.
3. "Not clear" means the record cannot tell. It does not mean nothing is happening.
4. Never claim a cause.
5. Write `short` in 2 sentences and under 45 words, with **bold** on 2 or 3 verdict words only. Write `more` in 3 to 5 sentences.
6. Write for the given audience, in the given language. A student gets everyday words and no numbers. A policymaker gets what it means for decisions and at most one number. A researcher gets at most 3 sentences in `short`, with the slope, the 95% interval, the test, and p."""

SCHEMA = {
    "type": "object",
    "properties": {"short": {"type": "string"}, "more": {"type": "string"}},
    "required": ["short", "more"],
    "additionalProperties": False,
}


def explain(result: Result, audience: Audience, lang: Lang, ai: bool) -> Explanation:
    short, more = Words(lang).template(result.verdict.key, audience, result.facts)
    template = Explanation(short=short, more=more, via="template")
    if not ai:
        return template
    user = json.dumps({"headline": "".join(s.t for s in result.headline), "facts": result.facts,
                       "audience": audience, "lang": lang}, ensure_ascii=False)
    try:
        reply = net.ask_model(SYSTEM, user, SCHEMA, 1024)
    except AIFailed as e:
        log.info("explainer model failed: %s", e)
        return template
    short, more = reply.get("short"), reply.get("more")
    if not (isinstance(short, str) and isinstance(more, str) and short.strip()):
        log.warning("explainer reply has no short/more text: %r", reply)
        return template
    if not numbers_ok(f"{short}\n{more}", result.facts, _years(result.facts)):
        log.warning("explainer rejected a reply with a number not in facts: %r", reply)
        return template
    return Explanation(short=short, more=more, via="ai")


def numbers_ok(text: str, facts: dict[str, Fact], years: set[int]) -> bool:
    """Every number token in text equals a token inside a fact value, or a year of the result."""
    allowed = {str(y) for y in years}
    for v in facts.values():
        if v is not None and not isinstance(v, bool):
            allowed |= number_tokens(str(v))
    return number_tokens(text) <= allowed


def _years(facts: dict[str, Fact]) -> set[int]:
    first, last = facts.get("first_year"), facts.get("last_year")
    return set(range(first, last + 1)) if isinstance(first, int) and isinstance(last, int) else set()
