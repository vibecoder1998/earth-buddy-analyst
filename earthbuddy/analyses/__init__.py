"""The registry of question kinds, and the only place a Result is built."""
from .. import net
from ..types import ClaimQ, Lang, Question, QuestionError, Result, TrendQ
from ..words import Words
from . import claim, trend
from .base import Analysis

# The one list of kinds. A new kind: one module, one entry here, one doc. Rows 10-16 add the rest.
ANALYSES: dict[str, Analysis] = {
    "claim": Analysis(ClaimQ, claim.claim, claim.VERDICTS),
    "trend": Analysis(TrendQ, trend.trend, trend.VERDICTS),
}


def run(question: Question, *, revision: int = 0, lang: Lang = "en") -> Result:
    """Question -> Result. Cannot see quote, via, or ai, so AI-off equality holds by construction."""
    entry = ANALYSES.get(question.kind)
    if entry is None:
        raise QuestionError("kind", f"{question.kind} is not built yet")
    w = Words(lang)
    f = entry.fn(question, w)
    if f.verdict.key not in entry.verdicts:
        raise RuntimeError(f"undeclared verdict key {f.verdict.key}")
    notes = list(f.notes)
    if revision > 0:
        notes.insert(0, w("note.second_look"))
    if net.OFFLINE:
        notes.insert(0, w("note.synthetic"))
    return Result(kind=question.kind, question=question, headline=w.headline(f.verdict.key, f.facts),
                  verdict=f.verdict, tiles=f.tiles, facts=f.facts, charts=f.charts, method=f.method,
                  sources=list({(s.dataset, s.param): s for s in f.sources}.values()), notes=notes,
                  detail=f.detail.model_dump(mode="json"))


def kinds_meta() -> dict[str, dict]:
    """For GET /api/catalog: {kind: {"fields": [{"name", "required"}]}}, built kinds only. Replaces a JS FIELDS table."""
    return {k: {"fields": [{"name": n, "required": a.required(n)} for n in a.fields]} for k, a in ANALYSES.items()}
