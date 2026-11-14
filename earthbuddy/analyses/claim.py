"""Claim check (docs/05). Row 6."""
from pydantic import BaseModel

from ..types import ClaimQ, Direction, Fit, Outcome, Series, VariableId
from ..words import Words
from .base import Finding

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
    # TODO row 6:
    # got = series.get_many([(q.region, t.variable) for t in q.tests], q.window)
    # fits = [fit_or_none(s, v.rel)]; outcomes = [stats.test_claim(...)]
    # scored = stats.claim_verdict([(o, f.p if f else nan)]); Evidence rows with scored.survives / scored.final,
    #   break_year from stats.pettitt, caveat from v.doubt
    # facts: region, years, first_year, last_year, verdict, n_tests, n_supported...; per test
    #   <id>_change_per_decade, <id>_95pct_range, <id>_p, <id>_outcome — every number via fmt / fmt_p
    # tiles: verdict, parts matching, years, cells (or "one point"); charts: one line_chart per test with break year
    # method: trend test, false-discovery check, step check (+ "live POWER, longer record" for a Point)
    raise NotImplementedError
