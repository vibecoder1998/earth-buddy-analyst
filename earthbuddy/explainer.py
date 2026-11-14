"""Plain-language text under a result. Templates always work; AI text is shown only if every number checks out."""
from .types import Audience, Explanation, Fact, Lang, Result


def explain(result: Result, audience: Audience, lang: Lang, ai: bool) -> Explanation:
    # TODO row 9:
    # short, more = Words(lang).template(result.verdict.key, audience, result.facts)
    # if not (ai and net.ai_available()): return template
    # try reply = net.ask_model(SYSTEM, json.dumps({headline, facts, audience, lang}), SCHEMA, 1024) except AIFailed: template
    # numbers_ok(reply short + more, facts, _years(result)) ? via "ai" : log and template
    raise NotImplementedError


def numbers_ok(text: str, facts: dict[str, Fact], years: set[int]) -> bool:
    """Every number token in text equals a token inside a fact value, or a year of the result."""
    raise NotImplementedError
