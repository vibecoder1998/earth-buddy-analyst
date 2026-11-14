"""Trend at a place (docs/06). Row 7."""
from typing import Literal

from pydantic import BaseModel

from ..types import Decomposition, Fit, SeasonalCycle, TrendQ
from ..words import Words
from .base import Finding

VERDICTS = ("trend.clear", "trend.likely", "trend.unclear", "trend.too_short")


class Size(BaseModel):
    word: Literal["small", "moderate", "large", "none"]
    years: float


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
    # TODO row 7:
    # v = catalog.variable(q.variable); s = series.get_series(q.region, q.variable, q.window)
    # fit = stats.trend_test(s.years, s.values, rel=v.rel)        # TooShort -> 400 window
    # dec, cyc = stats.stl(s.monthly), stats.seasonal_cycle(s.monthly) when s.monthly
    # facts per docs/06 step 6, numbers via fmt / fmt_p; words via w("word.*")
    # tiles: change ± range, how sure (level, p, coin), peak month or highest year
    # charts: annual line + Sen band; STL tabs; early-vs-late cycle. method: 5-8 w.step(...) incl. "not clear ≠ nothing"
    # verdict = Verdict(key=f"trend.{fit.level}", level=fit.level)
    raise NotImplementedError
