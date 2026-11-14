"""Trend at a place (docs/06)."""
from typing import Literal

from pydantic import BaseModel

from .. import catalog, series, stats
from ..catalog import VariableInfo
from ..stats import T, fmt, fmt_level, fmt_p
from ..types import Decomposition, Fact, Fit, Line, SeasonalCycle, Series, Step, Tile, TrendQ, Verdict
from ..words import Words
from .base import Finding, line_chart, monthly_totals

VERDICTS = ("trend.clear", "trend.likely", "trend.unclear", "trend.too_short")


class Size(BaseModel):
    word: Literal["small", "moderate", "large", "none"]
    years: float | None


class Sure(BaseModel):
    word: Literal["clearly", "probably", "cant_tell"]
    coin: str


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
    fit = stats.trend_test(s.years, s.values, rel=v.rel)
    monthly, month_unit = monthly_totals(s, v)
    dec = stats.stl(monthly) if monthly else None
    cyc = stats.seasonal_cycle(monthly) if monthly else None
    size_word, size_years = stats.size(fit)
    sure_word, heads = stats.coin(fit.p)
    coin = w("word.coin_none" if heads is None else "word.coin_one" if heads == 1 else "word.coin", n=heads)
    facts = _facts(q, v, s, fit, size_word, coin, w) | _season_facts(dec, cyc, w)
    charts: list[Line] = [line_chart(s, fit, v, v.label(w.lang))]
    if dec is not None:
        x = [int(t[:4]) + round((int(t[5:]) - 0.5) / 12, 3) for t in dec.t]
        charts += [Line(title=w(f"word.part.{p}"), x=x, y=getattr(dec, p), unit=month_unit)
                   for p in ("trend", "seasonal", "residual")]
    if cyc is not None:
        charts.append(_cycle_chart(monthly, cyc, month_unit, w))
    return Finding(
        verdict=Verdict(key=f"trend.{fit.level}", level=fit.level),
        facts=facts,
        tiles=_tiles(s, cyc is not None, facts, w),
        charts=charts,
        method=_method(s, monthly is not None, dec is not None, facts, w),
        sources=s.sources,
        detail=TrendDetail(fit=fit, annual=list(zip(s.years, s.values)), decomposition=dec, seasonal_cycle=cyc,
                           size=Size(word=size_word, years=None if size_word == "none" else size_years),
                           sure=Sure(word=sure_word, coin=coin)),
    )


def _facts(q: TrendQ, v: VariableInfo, s: Series, fit: Fit, size_word: str, coin: str, w: Words) -> dict[str, Fact]:
    def amount(x: float | str) -> str:
        return w("word.amount", n=x if isinstance(x, str) else fmt(x), unit=v.unit).strip()

    facts: dict[str, Fact] = {
        "place": catalog.name(q.region, w.lang), "variable": v.label(w.lang), "noun": v.what(w.lang), "unit": v.unit,
        "period": f"{fit.first_year}–{fit.last_year}", "first_year": fit.first_year, "last_year": fit.last_year,
        "n_years": fit.n, "direction": w(f"word.direction.{fit.direction}"),
        "change_per_decade": amount(fit.slope_per_decade),
        "change_per_decade_95pct_range": w("word.range", lo=fmt(fit.lo_per_decade), hi=fmt(fit.hi_per_decade),
                                           unit=v.unit).strip(),
        "total_change": amount(fit.total_change), "average": amount(fmt_level(fit.mean)), "p_value": fmt_p(fit.p),
        "certainty": w(f"word.level.{fit.level}"), "coin": coin, "typical_swing": amount(fit.swing),
        "size_word": w(f"word.size.{size_word}"), "test": w(f"word.test.{fit.test}"),
        "data_source": s.sources[0].name,
        "alpha": fmt(T.alpha), "likely": fmt(T.likely), "reliable": T.reliable, "ci_pct": fmt(T.ci * 100),
    }
    if fit.percent_change is not None:
        facts["percent_change"] = w("word.percent", n=fmt(fit.percent_change))
    return facts


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


def _tiles(s: Series, by_month: bool, facts: dict[str, Fact], w: Words) -> list[Tile]:
    if by_month:
        when = w.tile("peak_month", str(facts["peak_month"]), cycle_years=T.cycle_years, **facts)
    else:
        known = [(x, y) for y, x in zip(s.years, s.values) if x is not None]
        when = w.tile("highest_year", str(max(known)[1]), **facts)
    return [
        w.tile("change", str(facts["change_per_decade"]), **facts),
        w.tile("sure", str(facts["certainty"]).capitalize(), **facts),
        when,
    ]


def _method(s: Series, point: bool, seasons: bool, facts: dict[str, Fact], w: Words) -> list[Step]:
    lo, hi = catalog.years()
    fetched = (w.step("fetched_point", **facts) if point else
               w.step("fetched_area", cells=s.cells, record=f"{lo}–{hi}", **facts))
    ids = (*(("yearly",) if point else ()), *(("seasons",) if seasons else ()), "sen", "size", "tested", "not_clear")
    return [fetched, *(w.step(i, **facts) for i in ids)]
