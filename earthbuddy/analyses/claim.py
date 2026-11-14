"""Claim check (docs/05)."""
import math
from typing import get_args

from pydantic import BaseModel

from .. import catalog, series, stats
from ..catalog import VariableInfo
from ..stats import T, fmt, fmt_p
from ..types import ClaimQ, Direction, Fact, Fit, Outcome, Point, Series, Tile, VariableId, Verdict
from ..words import Words
from .base import Finding, fit_or_none, line_chart, per_decade

VERDICTS = ("claim.supported", "claim.opposed", "claim.mixed", "claim.step", "claim.unsupported", "claim.nothing")


class Evidence(BaseModel):
    variable: VariableId
    direction: Direction
    series: Series
    fit: Fit | None
    outcome: Outcome          # before the multiple-test check
    survives: bool            # q < T.fdr_q across this claim's tests
    final: Outcome            # after the check
    break_year: int | None    # Pettitt year when p < T.pettitt_p
    caveat: str | None        # "doubt" when the variable's doubt direction matches a clear trend


class ClaimDetail(BaseModel):
    evidence: list[Evidence]
    counts: dict[str, int]


def claim(q: ClaimQ, w: Words) -> Finding:
    vs = [catalog.variable(t.variable) for t in q.tests]
    got = series.get_many([(q.region, t.variable) for t in q.tests], q.window)
    fits = [fit_or_none(s, v.rel) for s, v in zip(got, vs)]
    outcomes = [stats.test_claim(f, t.direction, s.years, s.values) for f, t, s in zip(fits, q.tests, got)]
    scored = stats.claim_verdict([(o, f.p if f else math.nan) for o, f in zip(outcomes, fits)])
    evidence = [
        Evidence(variable=t.variable, direction=t.direction, series=s, fit=f, outcome=o, survives=keep, final=final,
                 break_year=_break_year(f, s), caveat=_caveat(f, v))
        for t, s, f, o, keep, final, v in zip(q.tests, got, fits, outcomes, scored.survives, scored.final, vs)
    ]
    counts = {o: scored.final.count(o) for o in get_args(Outcome)}
    first, last = min(s.years[0] for s in got), max(s.years[-1] for s in got)
    facts: dict[str, Fact] = {
        "region": catalog.name(q.region, w.lang), "years": f"{first}–{last}", "first_year": first, "last_year": last,
        "verdict": w(f"word.{scored.verdict.key}"), "n_tests": len(q.tests),
        **{f"n_{o}": n for o, n in counts.items()},
        "alpha": fmt(T.alpha), "fdr_q": fmt(T.fdr_q), "ci_pct": fmt(T.ci * 100),
        "step_false_fire": fmt(T.step_false_fire * 100),
    }
    for e, v in zip(evidence, vs):
        facts |= _test_facts(e, v, w)
    return Finding(
        verdict=scored.verdict,
        facts=facts,
        tiles=_tiles(scored.verdict, facts, got[0].cells, w),
        charts=[line_chart(e.series, e.fit, v, v.label(w.lang), e.break_year) for e, v in zip(evidence, vs)],
        method=[w.step(s, **facts) for s in ("trend", "fdr", "jump", *(("live",) if isinstance(q.region, Point) else ()))],
        sources=[src for s in got for src in s.sources],
        detail=ClaimDetail(evidence=evidence, counts=counts),
        notes=[_doubt_note(v, w) for e, v in zip(evidence, vs) if e.caveat],
    )


def _break_year(fit: Fit | None, s: Series) -> int | None:
    if fit is None or fit.constant:
        return None
    year, p = stats.pettitt(s.years, s.values)
    return year if p < T.pettitt_p else None


def _caveat(fit: Fit | None, v: VariableInfo) -> str | None:
    doubted = {"up": "rising", "down": "falling"}.get(v.doubt or "")
    return "doubt" if fit is not None and fit.level == "clear" and fit.direction == doubted else None


def _test_facts(e: Evidence, v: VariableInfo, w: Words) -> dict[str, Fact]:
    k = e.variable
    out: dict[str, Fact] = {f"{k}_outcome": w(f"word.outcome.{e.final}")}
    if e.fit is None:
        return out | {f"{k}_change_per_decade": None, f"{k}_95pct_range": None, f"{k}_p": None}
    value, lo, hi, unit = per_decade(e.fit, v)
    return out | {
        f"{k}_change_per_decade": w("word.amount", n=fmt(value), unit=unit).strip(),
        f"{k}_95pct_range": w("word.range", lo=fmt(lo), hi=fmt(hi), unit=unit).strip(),
        f"{k}_p": fmt_p(e.fit.p),
    }


def _tiles(verdict: Verdict, facts: dict[str, Fact], cells: int | None, w: Words) -> list[Tile]:
    where = w.tile("point", w("word.one_point"), **facts) if cells is None else w.tile("cells", str(cells), **facts)
    return [
        w.tile("verdict", w(f"word.{verdict.key}"), **facts),
        w.tile("parts", w("word.n_of", n=facts["n_supported"], total=facts["n_tests"]), **facts),
        w.tile("years", str(facts["years"]), **facts),
        where,
    ]


def _doubt_note(v: VariableInfo, w: Words) -> str:
    said = v.caveats.get(w.lang) or v.caveats.get("en", [])
    return " ".join([w("note.doubt", label=v.label(w.lang)), *said])
