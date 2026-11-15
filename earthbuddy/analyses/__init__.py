"""The registry of question kinds, and the only place a Result is built."""
from .. import net
from ..types import (BaselineQ, ClaimQ, ExtremesQ, FireQ, Lang, Question, QuestionError, RankQ, RelateQ, Result, ScanQ,
                     TrendQ, WhereQ)
from ..words import Words
from . import baseline, claim, extremes, fire, rank, relate, scan, trend, where
from .base import Analysis
from .investigate import investigate

# The one list of kinds. A new kind: one module, one entry here, one doc.
ANALYSES: dict[str, Analysis] = {
    "claim": Analysis(ClaimQ, claim.claim, claim.VERDICTS),
    "trend": Analysis(TrendQ, trend.trend, trend.VERDICTS),
    "scan": Analysis(ScanQ, scan.scan, scan.VERDICTS),
    "where": Analysis(WhereQ, where.where, where.VERDICTS),
    "rank": Analysis(RankQ, rank.rank, rank.VERDICTS),
    "baseline": Analysis(BaselineQ, baseline.baseline, baseline.VERDICTS),
    "extremes": Analysis(ExtremesQ, extremes.extremes, extremes.VERDICTS),
    "relate": Analysis(RelateQ, relate.relate, relate.VERDICTS),
    "fire": Analysis(FireQ, fire.fire, trend.VERDICTS, screen="analyze"),
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
    if net.OFFLINE:
        notes.insert(0, w("note.synthetic"))
    if revision > 0:
        notes.insert(0, w("note.second_look"))
    headline = w.headline(f.verdict.key, f.facts)
    return Result(kind=question.kind, question=question, headline=headline,
                  verdict=f.verdict, tiles=f.tiles, facts=f.facts, charts=f.charts, method=f.method,
                  sources=list({s.id: s for s in f.sources}.values()), notes=notes,
                  detail=f.detail.model_dump(mode="json"), investigation=investigate(question, f, headline, w))


def kinds_meta() -> dict[str, dict]:
    """For GET /api/catalog: {kind: {"screen", "fields": [{"name", "required", "regions"?, "choices"?}]}}, built
    kinds only. Replaces a JS FIELDS table. "screen" says which screen lists the kind. "regions" lists the region
    kinds a region or point field accepts. "choices" lists a Literal field's values, so no select is typed twice."""
    return {k: {"screen": a.screen,
                "fields": [{"name": n, "required": a.required(n),
                            **({"regions": a.region_kinds(n)} if n in ("region", "point") else {}),
                            **({"choices": c} if (c := a.choices(n)) else {})} for n in a.fields]}
            for k, a in ANALYSES.items()}
