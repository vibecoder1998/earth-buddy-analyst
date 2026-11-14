"""Recent years against a reference period at one point (docs/08)."""
import statistics
from typing import Literal

from pydantic import BaseModel

from .. import catalog, series, stats
from ..catalog import VariableInfo
from ..stats import T, fmt, fmt_p, fmt_pair
from ..types import BaselineQ, Fact, Fit, Level, Line, QuestionError, Series, Signal, Step, Tile, Verdict
from ..words import Words
from .base import Finding, fit_or_none

VERDICTS = ("baseline.higher", "baseline.lower", "baseline.same")


class Period(BaseModel):
    start: int
    end: int
    mean: float
    fit: Fit | None


class LevelGap(BaseModel):
    difference: float
    percent: float | None
    p: float
    test: Literal["mann-whitney"] = "mann-whitney"
    level: Level


class Pace(BaseModel):
    difference_per_decade: float
    z: float
    p: float
    level: Level


class BaselineDetail(BaseModel):
    baseline: Period
    recent: Period
    level: LevelGap
    pace: Pace | None


def baseline(q: BaselineQ, w: Words) -> Finding:
    v = catalog.variable(q.variable)
    s = series.get_series(q.point, q.variable, None)
    b0, b1 = q.baseline
    last = s.years[-1]
    base, recent = _span(s, b0, b1), _span(s, b1 + 1, last)
    if len(base.years) < T.min_years or last - b1 < T.baseline_gap or len(recent.years) < T.recent_min:
        raise QuestionError("baseline", f"a baseline needs {T.min_years} years with data, ending by {last - T.baseline_gap}")
    periods = [_period(p, v) for p in (base, recent)]
    gap = _level_gap(base, recent, v)
    pace = _pace(*periods)
    facts = _facts(q, v, s, *periods, gap, pace, (len(base.years), len(recent.years)), w)
    key = "baseline.same" if gap.level not in ("clear", "likely") else (
        "baseline.higher" if gap.difference > 0 else "baseline.lower")
    return Finding(
        verdict=Verdict(key=key, level=gap.level),
        facts=facts,
        tiles=_tiles(pace is not None, facts, w),
        charts=[Line(title=v.label(w.lang), x=s.years, y=s.values, unit=v.unit,
                     means=[(p.start, p.end, p.mean) for p in periods])],
        method=_method(pace is not None, facts, w),
        sources=s.sources,
        detail=BaselineDetail(baseline=periods[0], recent=periods[1], level=gap, pace=pace),
        signals=[Signal(variable=q.variable, direction="up" if gap.difference > 0 else "down", level=gap.level)]
        if gap.difference else [],
    )


def _span(s: Series, lo: int, hi: int) -> Series:
    keep = [(y, x) for y, x in zip(s.years, s.values) if lo <= y <= hi and x is not None]
    years, values = map(list, zip(*keep)) if keep else ([], [])
    return s.model_copy(update={"years": years, "values": values, "monthly": None})


def _period(s: Series, v: VariableInfo) -> Period:
    return Period(start=s.years[0], end=s.years[-1], mean=statistics.fmean(s.values), fit=fit_or_none(s, v.rel))


def _level_gap(base: Series, recent: Series, v: VariableInfo) -> LevelGap:
    mean_base = statistics.fmean(base.values)
    d = statistics.fmean(recent.values) - mean_base
    p = stats.level_gap_p(recent.values, base.values)
    return LevelGap(difference=d, percent=d / mean_base * 100 if v.rel and mean_base > 0 else None, p=p,
                    level=stats.level_of(p, len(base.years) + len(recent.years)))


def _pace(base: Period, recent: Period) -> Pace | None:
    if base.fit is None or recent.fit is None or min(base.fit.n, recent.fit.n) < T.reliable:
        return None
    d, z, p = stats.slope_gap(recent.fit, base.fit)
    return Pace(difference_per_decade=d, z=z, p=p, level=stats.level_of(p, min(base.fit.n, recent.fit.n)))


def _facts(q: BaselineQ, v: VariableInfo, s: Series, base: Period, recent: Period, gap: LevelGap, pace: Pace | None,
           counts: tuple[int, int], w: Words) -> dict[str, Fact]:
    def amount(x: float | str, unit: str = v.unit) -> str:
        return w("word.amount", n=x if isinstance(x, str) else fmt(x), unit=unit).strip()

    per_decade = w("word.per_decade", unit=v.unit)
    pace_word = ("none" if pace is None else "same" if pace.level not in ("clear", "likely") else
                 "up" if pace.difference_per_decade > 0 else "down")
    base_average, recent_average = fmt_pair(base.mean, recent.mean)
    facts: dict[str, Fact] = {
        "place": catalog.name(q.point, w.lang), "variable": v.label(w.lang), "noun": v.what(w.lang), "unit": v.unit,
        "period": f"{s.years[0]}–{s.years[-1]}", "first_year": s.years[0], "last_year": s.years[-1],
        "baseline_period": f"{base.start}–{base.end}", "recent_period": f"{recent.start}–{recent.end}",
        "baseline_years": counts[0], "recent_years": counts[1],
        "baseline_average": amount(base_average), "recent_average": amount(recent_average),
        "difference": amount(gap.difference), "p_value": fmt_p(gap.p),
        "certainty": w(f"word.level.{gap.level}"), "how_sure": w(f"word.sure.{gap.level}"),
        "pace": w(f"word.pace.{pace_word}"),
        "data_source": s.sources[0].name,
        "alpha": fmt(T.alpha), "likely": fmt(T.likely), "reliable": T.reliable, "ci_pct": fmt(T.ci * 100),
    }
    if gap.percent is not None:
        facts["percent_difference"] = w("word.percent", n=fmt(gap.percent))
    for name, p in (("baseline", base), ("recent", recent)):
        if p.fit is not None:
            facts[f"{name}_change_per_decade"] = amount(p.fit.slope_per_decade, per_decade)
    if pace is None:
        facts["pace_test"] = w("word.pace_test.untested", reliable=T.reliable)
    else:
        facts |= {"pace_difference": amount(pace.difference_per_decade, per_decade), "pace_p": fmt_p(pace.p)}
        facts["pace_test"] = w("word.pace_test.tested", diff=facts["pace_difference"], p=facts["pace_p"],
                               ci_pct=facts["ci_pct"])
    return facts


def _tiles(has_pace: bool, facts: dict[str, Fact], w: Words) -> list[Tile]:
    return [
        w.tile("difference", str(facts["difference"]), **facts),
        w.tile("baseline_sure", str(facts["certainty"]).capitalize(), **facts),
        w.tile("pace", str(facts["pace_difference"]), **facts) if has_pace else
        w.tile("recent_years", str(facts["recent_years"]), **facts),
    ]


def _method(has_pace: bool, facts: dict[str, Fact], w: Words) -> list[Step]:
    ids = ("fetched_point", "yearly", "baseline_split", "baseline_level",
           "baseline_pace" if has_pace else "baseline_no_pace", "not_clear")
    return [w.step(i, **facts) for i in ids]
