"""Scan every measure for one region (docs/12)."""
from typing import Literal

from pydantic import BaseModel

from .. import catalog, series, stats
from ..stats import T, fmt, fmt_p
from ..types import Direction, Fact, Fit, Level, QuestionError, ScanQ, Series, Tile, TooShort, VariableId, Verdict
from ..words import Words
from .base import Finding, per_decade

VERDICTS = ("scan.changes", "scan.no_change")
_OBSERVED: dict[str, Direction] = {"rising": "up", "falling": "down", "flat": "any"}


class Row(BaseModel):
    variable: VariableId
    slope_per_decade: float
    lo: float
    hi: float
    unit: str
    p: float
    q: float
    survives: bool
    level: Level
    constant: bool
    observed: Direction


class Skipped(BaseModel):
    variable: VariableId
    reason: Literal["no_series", "too_short"]


class ScanDetail(BaseModel):
    rows: list[Row]
    skipped: list[Skipped]


def scan(q: ScanQ, w: Words) -> Finding:
    vs = catalog.variables()
    got = series.get_many([(q.region, v.id) for v in vs], None, tolerant=True)
    tested: list[tuple[Series, Fit]] = []
    skipped: list[Skipped] = []
    for v, s in zip(vs, got):
        if isinstance(s, QuestionError):
            skipped.append(Skipped(variable=v.id, reason="no_series"))
            continue
        if isinstance(s, Exception):
            raise s
        try:
            tested.append((s, stats.trend_test(s.years, s.values, rel=v.rel)))
        except TooShort:
            skipped.append(Skipped(variable=v.id, reason="too_short"))
    if not tested:
        raise QuestionError("region", "no measure has enough years here")
    qs = stats.bh([fit.p for _, fit in tested])
    rows = sorted((_row(s, fit, q_value) for (s, fit), q_value in zip(tested, qs)), key=lambda r: r.p)
    n_clear = sum(r.survives for r in rows)
    first, last = min(s.years[0] for s, _ in tested), max(s.years[-1] for s, _ in tested)
    facts: dict[str, Fact] = {
        "region": catalog.name(q.region, w.lang), "years": f"{first}–{last}", "first_year": first, "last_year": last,
        "n_clear": n_clear, "n_tested": len(rows), "n_skipped": len(skipped),
        "clear_measures": ", ".join(catalog.variable(r.variable).label(w.lang) for r in rows if r.survives),
        "alpha": fmt(T.alpha), "fdr_q": fmt(T.fdr_q),
    }
    for r in rows:
        facts |= _row_facts(r, w)
    verdict = Verdict(key="scan.changes", level="clear") if n_clear else Verdict(key="scan.no_change", level="unclear")
    return Finding(
        verdict=verdict,
        facts=facts,
        tiles=_tiles(facts, catalog.cells(q.region), w),
        charts=[],
        method=[w.step(s, **facts) for s in ("scan", "scan_fdr")],
        sources=[src for s, _ in tested for src in s.sources],
        detail=ScanDetail(rows=rows, skipped=skipped),
    )


def _row(s: Series, fit: Fit, q_value: float) -> Row:
    value, lo, hi, unit = per_decade(fit, catalog.variable(s.variable))
    return Row(variable=s.variable, slope_per_decade=value, lo=lo, hi=hi, unit=unit, p=fit.p, q=q_value,
               survives=fit.level == "clear" and q_value < T.fdr_q, level=fit.level, constant=fit.constant,
               observed=_OBSERVED[fit.direction])


def _row_facts(r: Row, w: Words) -> dict[str, Fact]:
    k = r.variable
    return {
        f"{k}_change_per_decade": w("word.amount", n=fmt(r.slope_per_decade), unit=r.unit).strip(),
        f"{k}_95pct_range": w("word.range", lo=fmt(r.lo), hi=fmt(r.hi), unit=r.unit).strip(),
        f"{k}_p": fmt_p(r.p),
        f"{k}_q": fmt_p(r.q),
    }


def _tiles(facts: dict[str, Fact], cells: int | None, w: Words) -> list[Tile]:
    return [
        w.tile("clear_count", w("word.n_of", n=facts["n_clear"], total=facts["n_tested"]), **facts),
        w.tile("years", str(facts["years"]), **facts),
        w.tile("cells", str(cells), **facts),
    ]
