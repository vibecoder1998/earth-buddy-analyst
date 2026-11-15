"""What one analysis returns, the registry record, and shared helpers. Private to analyses/."""
import calendar
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, get_args, get_origin

from pydantic import BaseModel

from .. import stats
from ..catalog import VariableInfo
from ..stats import T, fmt, fmt_level, fmt_p
from ..types import (Chart, Fact, Fit, Line, Region, Scope, Series, Signal, Source, Step, Tile, TooShort, VariableId,
                     Verdict)
from ..words import Words


@dataclass(frozen=True)
class Ground:
    """What an analysis knows about its own data when its question names no catalog variable or place."""
    scope: Scope
    context: list[VariableId]     # catalog variables whose drivers, impacts and guidance apply
    limits: list[str]             # filled from facts, so every number in them traces


@dataclass
class Finding:
    """What an analysis decides. analyses.run turns it into a Result. No headline: wording belongs to the verdict key."""
    verdict: Verdict
    facts: dict[str, Fact]
    tiles: list[Tile]
    charts: list[Chart]
    method: list[Step]
    sources: list[Source]
    detail: BaseModel
    notes: list[str] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)   # the directions it measured; empty when it measures none
    tested: bool = True            # False when the verdict level is not the outcome of a significance test
    focus: Region | None = None    # where a follow-up starts when the question names no single place
    ground: Ground | None = None   # set by a kind whose question names no catalog variable or place


@dataclass(frozen=True)
class Analysis:
    question: type[BaseModel]                 # its fields are the card's fields and the guard's fill list
    fn: Callable[[Any, Words], Finding]
    verdicts: tuple[str, ...]                 # every verdict key fn may return
    screen: Literal["ask", "analyze"] = "ask" # which screen lists the kind; the client reads it from kinds_meta

    @property
    def fields(self) -> tuple[str, ...]:
        return tuple(f for f in self.question.model_fields if f != "kind")

    def required(self, name: str) -> bool:
        return self.question.model_fields[name].is_required()

    def choices(self, name: str) -> list[str] | None:
        """A Literal field's values, in declaration order. The client draws its select from these."""
        annotation = self.question.model_fields[name].annotation
        return list(get_args(annotation)) if get_origin(annotation) is Literal else None

    def region_kinds(self, name: str) -> list[str]:
        annotation = self.question.model_fields[name].annotation
        return [m.model_fields["kind"].default for m in get_args(annotation) or (annotation,)]


def fit_or_none(s: Series, rel: bool) -> Fit | None:
    try:
        return stats.trend_test(s.years, s.values, rel=rel)
    except TooShort:
        return None


def signal(variable: str, fit: Fit | None, level: str | None = None) -> list[Signal]:
    """A fit as a Signal. None for no fit or a flat one: there is no direction to talk about."""
    if fit is None or fit.direction == "flat":
        return []
    return [Signal(variable=variable, direction="up" if fit.direction == "rising" else "down", level=level or fit.level)]


def per_decade(fit: Fit, v: VariableInfo) -> tuple[float, float, float, str]:
    """(value, lo, hi, unit). For rel variables: percent of the mean per decade."""
    if v.rel and fit.mean > 0:
        k = 100 / fit.mean
        return fit.slope_per_decade * k, fit.lo_per_decade * k, fit.hi_per_decade * k, "%"
    return fit.slope_per_decade, fit.lo_per_decade, fit.hi_per_decade, v.unit


def line_chart(years: list[int], values: list[float | None], unit: str, fit: Fit | None, title: str,
               mark_year: int | None = None, mark_label: str | None = None) -> Line:
    """Annual line with the Sen line and its 95% band."""
    if fit is None:
        return Line(title=title, x=years, y=values, mark_year=mark_year, mark_label=mark_label, unit=unit)
    mid = (fit.first_year + fit.last_year) / 2
    known = [y for y, x in zip(years, values) if x is not None]

    def at(slope: float, year: int) -> float:
        return fit.intercept + slope / 10 * (year - mid)

    band = [(y, *sorted((at(fit.lo_per_decade, y), at(fit.hi_per_decade, y)))) for y in known]
    return Line(title=title, x=years, y=values, unit=unit, mark_year=mark_year, mark_label=mark_label,
                trend=[(y, stats.sen_at(fit, y)) for y in (fit.first_year, fit.last_year)], band=band)


class Size(BaseModel):
    word: Literal["small", "moderate", "large", "none"]
    years: float | None


class Sure(BaseModel):
    word: Literal["clearly", "probably", "cant_tell"]
    coin: str


@dataclass(frozen=True)
class Record:
    """One value per year or season, however it was made. What trend and every panel test."""
    place: str
    label: str
    noun: str
    unit: str
    rel: bool
    years: list[int]
    values: list[float | None]
    sources: list[Source]
    field: str = "window"      # the card control that sets its length; a too-short record is a 400 on it


class PanelDetail(BaseModel):
    """Result.detail of every Analyze kind."""
    fit: Fit
    size: Size
    sure: Sure
    rows: list[tuple[str, str]]   # label and value of each summary number, in reading order


@dataclass(frozen=True)
class Tested:
    fit: Fit
    verdict: Verdict           # key "trend.<level>"
    facts: dict[str, Fact]     # every fact trend's templates read
    size: Size
    sure: Sure
    chart: Line
    tiles: list[Tile]          # change, sure
    steps: list[Step]          # sen, size, tested, not_clear
    notes: list[str]


def tested(rec: Record, w: Words) -> Tested:
    """stats.trend_test plus trend's facts, chart, tiles and steps. Raises TooShort under T.min_years."""
    try:
        fit = stats.trend_test(rec.years, rec.values, rel=rec.rel)
    except TooShort as e:
        e.field = rec.field
        raise
    size_word, size_years = stats.size(fit)
    sure_word, heads = stats.coin(fit)
    coin = w("word.coin_none" if heads is None else "word.coin_one" if heads == 1 else "word.coin", n=heads)

    def amount(x: float | str) -> str:
        return w("word.amount", n=x if isinstance(x, str) else fmt(x), unit=rec.unit).strip()

    facts: dict[str, Fact] = {
        "place": rec.place, "variable": rec.label, "noun": rec.noun, "unit": rec.unit,
        "period": f"{fit.first_year}–{fit.last_year}", "first_year": fit.first_year, "last_year": fit.last_year,
        "n_years": fit.n, "direction": w(f"word.direction.{fit.direction}"),
        "change_per_decade": amount(fit.slope_per_decade),
        "change_per_decade_95pct_range": w("word.range", lo=fmt(fit.lo_per_decade), hi=fmt(fit.hi_per_decade),
                                           unit=rec.unit).strip(),
        "total_change": amount(fit.total_change), "average": amount(fmt_level(fit.mean)), "p_value": fmt_p(fit.p),
        "t_test_p": fmt_p(fit.t_p),
        "certainty": w(f"word.level.{fit.level}"), "coin": coin, "typical_swing": amount(fit.swing),
        "size_word": w(f"word.size.{size_word}"), "test": w(f"word.test.{fit.test}"),
        "data_source": rec.sources[0].name,
        "alpha": fmt(T.alpha), "likely": fmt(T.likely), "reliable": T.reliable, "ci_pct": fmt(T.ci * 100),
    }
    if fit.percent_change is not None:
        facts["percent_change"] = w("word.percent", n=fmt(fit.percent_change))
    return Tested(
        fit=fit, verdict=Verdict(key=f"trend.{fit.level}", level=fit.level), facts=facts,
        size=Size(word=size_word, years=None if size_word == "none" else size_years),
        sure=Sure(word=sure_word, coin=coin),
        chart=line_chart(rec.years, rec.values, rec.unit, fit, rec.label),
        tiles=[w.tile("change", str(facts["change_per_decade"]), **facts),
               w.tile("sure", str(facts["certainty"]).capitalize(), **facts)],
        steps=[w.step(i, **facts) for i in ("sen", "size", "tested", "not_clear")],
        notes=[w("note.tied", **facts)] if fit.level != stats.level_of(fit.p, fit.n) else [],
    )


def monthly_totals(s: Series, v: VariableInfo) -> tuple[list[tuple[int, int, float]] | None, str]:
    """(monthly values, their unit). A summed variable becomes totals per month: mm/day rates times days."""
    if s.monthly is None or v.aggregate != "sum":
        return s.monthly, v.unit
    days = (lambda y, m: calendar.monthrange(y, m)[1]) if v.per_day else (lambda y, m: 1)
    return [(y, m, x * days(y, m)) for y, m, x in s.monthly], v.unit.removesuffix("/yr") + "/month"
