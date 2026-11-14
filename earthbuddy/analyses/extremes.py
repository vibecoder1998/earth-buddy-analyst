"""Record years and unusual years, measured from the trend line (docs/10)."""
import datetime
from typing import Literal

from pydantic import BaseModel

from .. import catalog, series, stats
from ..catalog import VariableInfo
from ..stats import T, fmt, fmt_level, fmt_p, fmt_pair
from ..types import ExtremesQ, Fact, Fit, Intervals, Level, QuestionError, Series, Step, Tile, TooShort, Verdict
from ..words import Words
from .base import Finding, line_chart, monthly_totals, per_decade

VERDICTS = ("extremes.record_high", "extremes.record_low", "extremes.unusual", "extremes.ordinary")
Word = Literal["ordinary", "unusual", "exceptional"]
LEVEL: dict[Word, Level] = {"exceptional": "clear", "unusual": "likely", "ordinary": "unclear"}


class YearValue(BaseModel):
    year: int
    value: float


class Focus(BaseModel):
    year: int
    value: float
    rank_high: int
    rank_low: int
    deviation: float
    times_normal: float
    word: Word


class Tail(BaseModel):
    count: int
    chance: float


class Clustering(BaseModel):
    top_k: int
    window: int
    highest: Tail
    lowest: Tail


class MonthTrend(BaseModel):
    month: int
    slope_per_decade: float
    lo: float
    hi: float
    p: float
    q: float
    clear: bool


class Timing(BaseModel):
    centre_day: float
    shift_days_per_decade: float
    p: float


class ExtremesDetail(BaseModel):
    highest: list[YearValue]
    lowest: list[YearValue]
    focus: Focus
    clustering: Clustering
    months: list[MonthTrend] | None
    timing: Timing | None


def extremes(q: ExtremesQ, w: Words) -> Finding:
    v = catalog.variable(q.variable)
    s = series.get_series(q.region, q.variable, q.window)
    known = [(y, x) for y, x in zip(s.years, s.values) if x is not None]
    if len(known) < T.reliable:
        raise QuestionError("window", f"extremes needs {T.reliable} years with data, found {len(known)}")
    fit = stats.trend_test(s.years, s.values, rel=v.rel)
    by_value = sorted(known, key=lambda yx: yx[1], reverse=True)
    focus = _focus(q.year or known[-1][0], dict(known), fit)
    c = stats.clustering(*map(list, zip(*known)))
    cluster = Clustering(top_k=c.top_k, window=c.window, highest=Tail(count=c.high[0], chance=c.high[1]),
                         lowest=Tail(count=c.low[0], chance=c.low[1]))
    monthly, month_unit = monthly_totals(s, v)
    months = _months(monthly, v) if monthly else None
    timing = _timing(monthly) if monthly and v.per_day and v.aggregate == "sum" else None
    detail = ExtremesDetail(highest=[YearValue(year=y, value=x) for y, x in by_value[:T.extremes_listed]],
                            lowest=[YearValue(year=y, value=x) for y, x in by_value[::-1][:T.extremes_listed]],
                            focus=focus, clustering=cluster, months=months, timing=timing)
    facts = _facts(q, v, s, fit, detail, len(known), w)
    key = ("extremes.record_high" if focus.rank_high == 1 else "extremes.record_low" if focus.rank_low == 1 else
           "extremes.ordinary" if focus.word == "ordinary" else "extremes.unusual")
    charts = [line_chart(s, fit, v, v.label(w.lang), focus.year, w("word.focus_year"))]
    if months:
        charts.append(Intervals(title=w("word.months_chart", variable=v.label(w.lang)),
                                rows=[(w(f"month.{m.month}"), m.slope_per_decade, m.lo, m.hi, m.clear) for m in months],
                                unit=w("word.per_decade", unit=month_unit)))
    return Finding(
        verdict=Verdict(key=key, level=LEVEL[focus.word]),
        facts=facts,
        tiles=_tiles(facts, w),
        charts=charts,
        method=_method(s, detail, facts, w),
        sources=s.sources,
        detail=detail,
    )


def _focus(year: int, values: dict[int, float], fit: Fit) -> Focus:
    if year not in values:
        raise QuestionError("year", f"no value for {year}; the record runs {min(values)} to {max(values)}")
    x = values[year]
    times = stats.times_normal(fit, year, x)
    return Focus(year=year, value=x, rank_high=1 + sum(o > x for o in values.values()),
                 rank_low=1 + sum(o < x for o in values.values()), deviation=x - stats.sen_at(fit, year),
                 times_normal=times, word=stats.unusual_word(times))


def _months(monthly: list[tuple[int, int, float]], v: VariableInfo) -> list[MonthTrend] | None:
    fits: list[tuple[int, Fit]] = []
    for m in range(1, 13):
        pairs = [(y, x) for y, mo, x in monthly if mo == m]
        try:
            fits.append((m, stats.trend_test([y for y, _ in pairs], [x for _, x in pairs], rel=v.rel)))
        except TooShort:
            pass
    if not fits:
        return None
    qs = stats.bh([f.p for _, f in fits])
    return [MonthTrend(month=m, slope_per_decade=f.slope_per_decade, lo=f.lo_per_decade, hi=f.hi_per_decade, p=f.p,
                       q=q, clear=f.level == "clear" and q < T.fdr_q) for (m, f), q in zip(fits, qs)]


def _timing(monthly: list[tuple[int, int, float]]) -> Timing | None:
    got = stats.season_centre(monthly)
    if got is None:
        return None
    years, days, centre, _ = got
    fit = stats.trend_test(years, days)
    return Timing(centre_day=centre, shift_days_per_decade=fit.slope_per_decade, p=fit.p)


def _facts(q: ExtremesQ, v: VariableInfo, s: Series, fit: Fit, d: ExtremesDetail, n: int, w: Words) -> dict[str, Fact]:
    def amount(x: float | str, num=fmt) -> str:
        return w("word.amount", n=x if isinstance(x, str) else num(x), unit=v.unit).strip()

    f, c = d.focus, d.clustering
    slope, _, _, slope_unit = per_decade(fit, v)
    high, low = d.highest[0], d.lowest[0]
    trend_value, year_value = fmt_pair(f.value - f.deviation, f.value)
    cluster = ("high" if c.highest.chance < T.alpha else "low" if c.lowest.chance < T.alpha else "none")
    facts: dict[str, Fact] = {
        "place": catalog.name(q.region, w.lang), "variable": v.label(w.lang), "noun": v.what(w.lang), "unit": v.unit,
        "period": f"{s.years[0]}–{s.years[-1]}", "first_year": s.years[0], "last_year": s.years[-1], "n_years": n,
        "year": f.year, "year_value": amount(year_value), "trend_value": amount(trend_value),
        "deviation": amount(f.deviation), "times_normal": fmt(f.times_normal), "swings": fmt(abs(f.times_normal)),
        "typical_swing": amount(fit.swing),
        "word": w(f"word.extreme.{f.word}"), "rank_high": f.rank_high, "rank_low": f.rank_low,
        "side": w("word.side.above" if f.deviation >= 0 else "word.side.below"),
        "highest_year": high.year, "highest_value": amount(high.value, fmt_level),
        "lowest_year": low.year, "lowest_value": amount(low.value, fmt_level),
        "top_k": c.top_k, "cluster_window": c.window,
        "high_count": c.highest.count, "high_chance": fmt_p(c.highest.chance),
        "low_count": c.lowest.count, "low_chance": fmt_p(c.lowest.chance),
        "change_per_decade": w("word.amount", n=fmt(slope), unit=w("word.per_decade", unit=slope_unit)).strip(),
        "data_source": s.sources[0].name,
        "unusual": T.unusual, "exceptional": T.exceptional, "alpha": fmt(T.alpha), "fdr_q": fmt(T.fdr_q),
    }
    facts["cluster"] = w(f"word.cluster.{cluster}", **facts)
    if d.months is not None:
        clear = [w(f"month.{m.month}") for m in d.months if m.clear]
        facts |= {"n_months": len(d.months), "n_clear_months": len(clear),
                  "clear_months": ", ".join(clear) or w("word.none")}
    if d.timing is not None:
        day = datetime.date(2001, 1, 1) + datetime.timedelta(days=round(d.timing.centre_day))
        facts |= {"season_centre": w("word.date", day=day.day, month=w(f"month.{day.month}")),
                  "season_shift": w("word.days_per_decade", n=fmt(d.timing.shift_days_per_decade)),
                  "season_p": fmt_p(d.timing.p)}
    return facts


def _tiles(facts: dict[str, Fact], w: Words) -> list[Tile]:
    return [
        w.tile("focus", str(facts["word"]).capitalize(), **facts),
        w.tile("focus_rank", w("word.n_of", n=facts["rank_high"], total=facts["n_years"]), **facts),
        w.tile("highest_year", str(facts["highest_year"]), **facts),
        w.tile("clustering", w("word.n_of", n=facts["high_count"], total=facts["top_k"]), **facts),
    ]


def _method(s: Series, d: ExtremesDetail, facts: dict[str, Fact], w: Words) -> list[Step]:
    lo, hi = catalog.years()
    fetched = (w.step("fetched_point", **facts) if s.cells is None else
               w.step("fetched_area", cells=s.cells, record=f"{lo}–{hi}", **facts))
    ids = ("extremes_sorted", "extremes_focus", "extremes_cluster",
           *(("extremes_months",) if d.months is not None else ()), *(("extremes_timing",) if d.timing else ()))
    return [fetched, *(w.step(i, **facts) for i in ids)]
