"""Every shared type and error. Pydantic parses outside data at the boundary; inside, code trusts these types."""
from __future__ import annotations

import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")   # outside dicts cannot smuggle keys


VariableId = str
GroupId = str
Lang = Literal["en", "km"]
Audience = Literal["student", "policymaker", "researcher"]
Direction = Literal["up", "down", "any"]
Level = Literal["clear", "likely", "unclear", "too_short"]
Outcome = Literal["insufficient", "unsupported", "opposed", "step", "supported"]
Via = Literal["ai", "keywords", "form", "audit", "link"]
Kind = Literal["claim", "trend", "where", "baseline", "rank", "extremes", "relate", "scan"]
Window = tuple[int, int] | None


# ---- errors ---------------------------------------------------------------------------------------

class QuestionError(ValueError):
    """The only 400. `field` names the card control at fault."""

    def __init__(self, field: str, message: str = ""):
        self.field = field
        super().__init__(message or field)


class TooShort(QuestionError):
    """Fewer than T.min_years usable years. Claim catches it; trend lets it become a 400."""

    def __init__(self, n: int):
        super().__init__("window", f"only {n} usable years")
        self.n = n


class DataSourceError(Exception):
    """The only 502."""

    def __init__(self, message: str, status: int | None, url: str):
        super().__init__(message)
        self.message, self.status, self.url = message, status, url


class AIFailed(Exception):
    """Timeout, refusal, bad JSON, or no key. Never reaches a route: callers fall back."""


# ---- regions and questions ------------------------------------------------------------------------

class Country(_M):
    kind: Literal["country"] = "country"
    iso3: str


class Place(_M):
    kind: Literal["place"] = "place"
    id: str


class Point(_M):
    kind: Literal["point"] = "point"
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    name: str = Field(max_length=80)


Region = Annotated[Country | Place | Point, Field(discriminator="kind")]


class Test(_M):
    __test__ = False   # keep pytest from collecting it
    variable: VariableId
    direction: Direction


def _window_ok(w: Window) -> Window:
    if w is not None and w[0] > w[1]:
        raise ValueError("window must run forward")
    return w


class _Q(_M):
    @field_validator("window", check_fields=False)
    @classmethod
    def _w(cls, w: Window) -> Window:
        return _window_ok(w)


# Field declaration order is the card's field order.
class ClaimQ(_Q):
    kind: Literal["claim"]
    region: Region
    tests: list[Test] = Field(min_length=1, max_length=8)
    window: Window = None

    @field_validator("tests")
    @classmethod
    def _unique(cls, tests: list[Test]) -> list[Test]:
        if len({t.variable for t in tests}) != len(tests):
            raise ValueError("each variable may appear once")
        return tests


class TrendQ(_Q):
    kind: Literal["trend"]
    region: Region
    variable: VariableId
    window: Window = None


class WhereQ(_Q):
    kind: Literal["where"]
    point: Point
    variable: VariableId
    window: Window = None


class BaselineQ(_Q):
    kind: Literal["baseline"]
    point: Point
    variable: VariableId
    baseline: tuple[int, int] = (1981, 2010)


class RankQ(_Q):
    kind: Literal["rank"]
    variable: VariableId
    among: GroupId | Annotated[list[Region], Field(min_length=2, max_length=60)]
    metric: Literal["change", "level"] = "change"
    order: Literal["highest", "lowest"] = "highest"
    top_n: int = Field(10, ge=1, le=60)
    window: Window = None


class ExtremesQ(_Q):
    kind: Literal["extremes"]
    region: Region
    variable: VariableId
    year: int | None = None
    window: Window = None


class RelateQ(_Q):
    kind: Literal["relate"]
    region: Region
    x: VariableId
    y: VariableId
    window: Window = None


class ScanQ(_Q):
    kind: Literal["scan"]
    region: Annotated[Country | Place, Field(discriminator="kind")]


Question = Annotated[
    ClaimQ | TrendQ | WhereQ | BaselineQ | RankQ | ExtremesQ | RelateQ | ScanQ,
    Field(discriminator="kind"),
]


# ---- reader output --------------------------------------------------------------------------------

class Draft(_M):
    fields: dict                 # a partial Question; may fail to parse
    quote: str                   # what the person typed; shown, never parsed again
    via: Via
    leads: list[str] = []        # things the catalog cannot measure; no digits
    unmapped: list[str] = []     # words that matched nothing; no digits
    revision: int = Field(0, ge=0, le=99)


class ReadResult(_M):
    draft: Draft
    question: Question | None
    missing: list[str]
    ai_failed: bool


# ---- data -----------------------------------------------------------------------------------------

class Source(_M):
    id: str
    name: str
    short_name: str | None
    version: str | None
    agency: str
    center: str
    doi: str | None
    url: str
    citation: str
    via: str | None
    accessed: datetime.date | None
    cached: bool = False


class Series(_M):
    region: Region
    variable: VariableId
    years: list[int]
    values: list[float | None]                      # annual, one per year
    monthly: list[tuple[int, int, float]] | None = None   # POWER points only
    cells: int | None = None                        # None for a point
    sources: list[Source] = Field(min_length=1)

    @model_validator(mode="after")
    def _aligned(self) -> Series:
        if len(self.years) != len(self.values) or any(b <= a for a, b in zip(self.years, self.years[1:])):
            raise ValueError("years and values must align, years strictly increasing")
        return self


# ---- statistics outputs (docs/03) -----------------------------------------------------------------

class Fit(_M):
    n: int
    first_year: int
    last_year: int
    slope_per_decade: float
    lo_per_decade: float
    hi_per_decade: float
    intercept: float
    mean: float
    swing: float
    total_change: float
    percent_change: float | None
    p: float
    z: float
    tau: float
    test: Literal["mann-kendall", "mann-kendall-vif"]
    lag1: float
    constant: bool
    direction: Literal["rising", "falling", "flat"]
    level: Level


class Verdict(_M):
    key: str                     # i18n / words key, e.g. "claim.supported"
    level: Level


class Decomposition(_M):
    t: list[str]
    observed: list[float]
    trend: list[float]
    seasonal: list[float]
    residual: list[float]
    variance_share: dict[str, float]


class SeasonalCycle(_M):
    months: list[int]
    early: list[float]
    late: list[float]
    peak_month: int
    low_month: int
    amplitude: float


# ---- result ---------------------------------------------------------------------------------------

Fact = StrictStr | StrictInt | StrictBool | None   # no float: numbers enter as stats.fmt / fmt_p strings


class Seg(_M):
    t: str
    hl: bool = False


class Tile(_M):
    id: str
    label: str
    value: str
    note: str = ""


class Step(_M):
    title: str
    did: str
    why: str


class Line(_M):
    type: Literal["line"] = "line"
    title: str
    x: list[int | float]           # years, or fractional years for a monthly series
    y: list[float | None]
    trend: list[tuple[float, float]] | None = None
    band: list[tuple[float, float, float]] | None = None
    mark_year: int | None = None
    unit: str


class Bars(_M):
    type: Literal["bars"] = "bars"
    title: str
    labels: list[str]
    values: list[float]
    highlight: list[bool]
    unit: str


class Scatter(_M):
    type: Literal["scatter"] = "scatter"
    title: str
    points: list[tuple[float, float, str]]
    x_label: str
    y_label: str


class Cells(_M):
    type: Literal["cells"] = "cells"
    title: str
    cells: list[tuple[float, float, float, bool]]
    cell_size: tuple[float, float]
    unit: str
    warm_up: bool


class Intervals(_M):
    type: Literal["intervals"] = "intervals"
    title: str
    rows: list[tuple[str, float, float, float, bool]]
    unit: str


Chart = Annotated[Line | Bars | Scatter | Cells | Intervals, Field(discriminator="type")]


class Result(_M):
    kind: Kind
    question: Question
    headline: list[Seg]          # built by analyses.run from the verdict key, never by the model
    verdict: Verdict
    tiles: list[Tile] = Field(min_length=2, max_length=4)
    facts: dict[str, Fact]       # the only numbers an explanation may use
    charts: list[Chart]
    method: list[Step]
    sources: list[Source]
    notes: list[str]
    detail: dict                 # the kind's own Detail model, dumped


class Explanation(_M):
    short: str
    more: str
    via: Literal["ai", "template"]
