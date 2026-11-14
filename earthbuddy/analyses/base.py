"""What one analysis returns, the registry record, and shared helpers. Private to analyses/."""
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel

from .. import stats
from ..catalog import VariableInfo
from ..types import Chart, Fact, Fit, Line, Series, Source, Step, Tile, TooShort, Verdict
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


def fit_or_none(s: Series, rel: bool) -> Fit | None:
    try:
        return stats.trend_test(s.years, s.values, rel=rel)
    except TooShort:
        return None


def per_decade(fit: Fit, v: VariableInfo) -> tuple[float, float, float, str]:
    """(value, lo, hi, unit). For rel variables: percent of the mean per decade."""
    raise NotImplementedError


def line_chart(s: Series, fit: Fit | None, v: VariableInfo, title: str, mark_year: int | None = None) -> Line:
    """Annual line with the Sen line and its 95% band."""
    raise NotImplementedError
