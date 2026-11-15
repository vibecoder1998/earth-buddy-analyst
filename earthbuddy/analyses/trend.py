"""Trend at a place (docs/06)."""
from pydantic import BaseModel

from .. import catalog, series, stats
from ..stats import T, fmt
from ..types import Decomposition, Fact, Fit, Line, SeasonalCycle, Series, Step, Tile, TrendQ
from ..words import Words
from .base import Finding, Record, Size, Sure, monthly_totals, signal, tested

VERDICTS = ("trend.clear", "trend.likely", "trend.unclear", "trend.too_short")


class TrendDetail(BaseModel):
    fit: Fit
    annual: list[tuple[int, float | None]]
    decomposition: Decomposition | None
    seasonal_cycle: SeasonalCycle | None
    size: Size
    sure: Sure


def trend(q: TrendQ, w: Words) -> Finding:
    v = catalog.variable(q.variable)
    s = series.get_series(q.region, q.variable, q.window)
    core = tested(Record(place=catalog.name(q.region, w.lang), label=v.label(w.lang), noun=v.what(w.lang), unit=v.unit,
                         rel=v.rel, years=s.years, values=s.values, sources=s.sources), w)
    monthly, month_unit = monthly_totals(s, v)
    dec = stats.stl(monthly) if monthly else None
    cyc = stats.seasonal_cycle(monthly) if monthly else None
    facts = core.facts | _season_facts(dec, cyc, w)
    charts: list[Line] = [core.chart]
    if dec is not None:
        x = [int(t[:4]) + round((int(t[5:]) - 0.5) / 12, 3) for t in dec.t]
        charts += [Line(title=w(f"word.part.{p}"), x=x, y=getattr(dec, p), unit=month_unit)
                   for p in ("trend", "seasonal", "residual")]
    if cyc is not None:
        charts.append(_cycle_chart(monthly, cyc, month_unit, w))
    return Finding(
        verdict=core.verdict,
        facts=facts,
        tiles=[*core.tiles, _when_tile(s, cyc is not None, facts, w)],
        charts=charts,
        method=_method(s, monthly is not None, dec is not None, core.steps, facts, w),
        sources=s.sources,
        signals=signal(q.variable, core.fit),
        detail=TrendDetail(fit=core.fit, annual=list(zip(s.years, s.values)), decomposition=dec, seasonal_cycle=cyc,
                           size=core.size, sure=core.sure),
        notes=core.notes,
    )


def _season_facts(dec: Decomposition | None, cyc: SeasonalCycle | None, w: Words) -> dict[str, Fact]:
    facts: dict[str, Fact] = {}
    if cyc is not None:
        facts["peak_month"] = w(f"month.{cyc.peak_month}")
    if dec is not None:
        facts["seasonal_share"] = w("word.percent", n=fmt(dec.variance_share["seasonal"] * 100))
    return facts


def _cycle_chart(monthly: list[tuple[int, int, float]], cyc: SeasonalCycle, unit: str, w: Words) -> Line:
    years = sorted({y for y, _, _ in monthly})
    early, late = years[:T.cycle_years], years[-T.cycle_years:]
    return Line(title=w("word.cycle", early=f"{early[0]}–{early[-1]}", late=f"{late[0]}–{late[-1]}"),
                x=cyc.months, y=cyc.late, compare=cyc.early, unit=unit)


def _when_tile(s: Series, by_month: bool, facts: dict[str, Fact], w: Words) -> Tile:
    if by_month:
        return w.tile("peak_month", str(facts["peak_month"]), cycle_years=T.cycle_years, **facts)
    known = [(x, y) for y, x in zip(s.years, s.values) if x is not None]
    return w.tile("highest_year", str(max(known)[1]), **facts)


def _method(s: Series, point: bool, seasons: bool, tested_steps: list[Step], facts: dict[str, Fact], w: Words) -> list[Step]:
    lo, hi = catalog.years()
    fetched = (w.step("fetched_point", **facts) if point else
               w.step("fetched_area", cells=s.cells, record=f"{lo}–{hi}", **facts))
    ids = (*(("yearly",) if point else ()), *(("seasons",) if seasons else ()))
    return [fetched, *(w.step(i, **facts) for i in ids), *tested_steps]
