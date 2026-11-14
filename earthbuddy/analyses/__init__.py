"""The registry of question kinds, and the only place a Result is built."""
from .. import net
from ..types import ClaimQ, Lang, Question, QuestionError, RankQ, Result, ScanQ, TrendQ, WhereQ
from ..words import Words
from . import claim, rank, scan, trend, where
from .base import Analysis

# The one list of kinds. A new kind: one module, one entry here, one doc. Rows 10-16 add the rest.
ANALYSES: dict[str, Analysis] = {
    "claim": Analysis(ClaimQ, claim.claim, claim.VERDICTS),
    "trend": Analysis(TrendQ, trend.trend, trend.VERDICTS),
    "scan": Analysis(ScanQ, scan.scan, scan.VERDICTS),
    "where": Analysis(WhereQ, where.where, where.VERDICTS),
    "rank": Analysis(RankQ, rank.rank, rank.VERDICTS),
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
    return Result(kind=question.kind, question=question, headline=w.headline(f.verdict.key, f.facts),
                  verdict=f.verdict, tiles=f.tiles, facts=f.facts, charts=f.charts, method=f.method,
                  sources=list({s.id: s for s in f.sources}.values()), notes=notes,
                  detail=f.detail.model_dump(mode="json"))


def kinds_meta() -> dict[str, dict]:
    """For GET /api/catalog: {kind: {"fields": [{"name", "required", "regions"?}]}}, built kinds only.
    Replaces a JS FIELDS table. "regions" lists the region kinds a region or point field accepts."""
    return {k: {"fields": [{"name": n, "required": a.required(n),
                            **({"regions": a.region_kinds(n)} if n in ("region", "point") else {})} for n in a.fields]}
            for k, a in ANALYSES.items()}
