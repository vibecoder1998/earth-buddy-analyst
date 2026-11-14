"""What one analysis returns, the registry record, and shared helpers. Private to analyses/."""
import calendar
from dataclasses import dataclass, field
from typing import Any, Callable, get_args

from pydantic import BaseModel

from .. import stats
from ..catalog import VariableInfo
from ..types import Chart, Fact, Fit, Line, Region, Series, Signal, Source, Step, Tile, TooShort, Verdict
from ..words import Words


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


@dataclass(frozen=True)
class Analysis:
    question: type[BaseModel]                 # its fields are the card's fields and the guard's fill list
    fn: Callable[[Any, Words], Finding]
    verdicts: tuple[str, ...]                 # every verdict key fn may return

    @property
    def fields(self) -> tuple[str, ...]:
        return tuple(f for f in self.question.model_fields if f != "kind")

    def required(self, name: str) -> bool:
        return self.question.model_fields[name].is_required()

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


def line_chart(s: Series, fit: Fit | None, v: VariableInfo, title: str, mark_year: int | None = None,
               mark_label: str | None = None) -> Line:
    """Annual line with the Sen line and its 95% band."""
    if fit is None:
        return Line(title=title, x=s.years, y=s.values, mark_year=mark_year, mark_label=mark_label, unit=v.unit)
    mid = (fit.first_year + fit.last_year) / 2
    years = [y for y, x in zip(s.years, s.values) if x is not None]

    def at(slope: float, year: int) -> float:
        return fit.intercept + slope / 10 * (year - mid)

    band = [(y, *sorted((at(fit.lo_per_decade, y), at(fit.hi_per_decade, y)))) for y in years]
    return Line(title=title, x=s.years, y=s.values, unit=v.unit, mark_year=mark_year, mark_label=mark_label,
                trend=[(y, stats.sen_at(fit, y)) for y in (fit.first_year, fit.last_year)], band=band)


def monthly_totals(s: Series, v: VariableInfo) -> tuple[list[tuple[int, int, float]] | None, str]:
    """(monthly values, their unit). A summed variable becomes totals per month: mm/day rates times days."""
    if s.monthly is None or v.aggregate != "sum":
        return s.monthly, v.unit
    days = (lambda y, m: calendar.monthrange(y, m)[1]) if v.per_day else (lambda y, m: 1)
    return [(y, m, x * days(y, m)) for y, m, x in s.monthly], v.unit.removesuffix("/yr") + "/month"
