"""Where around a place a variable is changing (docs/07)."""
import math
from typing import Literal

from pydantic import BaseModel

from .. import catalog, series, stats
from ..catalog import VariableInfo
from ..stats import T, fmt, fmt_p
from ..types import Cells, Fact, Fit, Point, Series, TooShort, Verdict, WhereQ
from ..words import Words
from .base import Finding, fit_or_none

VERDICTS = ("where.clear", "where.chance", "where.too_short")
COMPASS = ("east", "north-east", "north", "north-west", "west", "south-west", "south", "south-east")


class Cell(BaseModel):
    lat: float
    lon: float
    slope_per_decade: float
    p: float
    q: float                  # Benjamini-Hochberg across the map's cells
    clear: bool               # stats.field_test
    mean: float


class Counts(BaseModel):
    rising: int
    falling: int
    flat: int
    clear: int                # clear after stats.field_test
    raw: int                  # clear on its own, before the check across cells
    total: int


class Strongest(BaseModel):
    lat: float
    lon: float
    slope_per_decade: float
    bearing: Literal["centre", "east", "north-east", "north", "north-west", "west", "south-west", "south", "south-east"]


class Nearest(BaseModel):
    lat: float
    lon: float
    slope_per_decade: float
    p: float


class WhereDetail(BaseModel):
    box: tuple[float, float, float, float]
    cell_size: tuple[float, float]
    cells: list[Cell]
    counts: Counts
    strongest: Strongest
    nearest: Nearest


def box(p: Point) -> tuple[float, float, float, float]:
    def side(c: float, limit: float) -> tuple[float, float]:
        lo = round(c / T.where_snap) * T.where_snap - T.where_box / 2
        lo = min(max(lo, -limit), limit - T.where_box)
        return lo, lo + T.where_box

    return (*side(p.lat, 90), *side(p.lon, 180))


def where(q: WhereQ, w: Words) -> Finding:
    v = catalog.variable(q.variable)
    b = box(q.point)
    grid = series.get_grid(b, q.variable, q.window)
    fitted = [(s, f) for s in grid if (f := fit_or_none(s, v.rel)) is not None]
    if not fitted:
        raise TooShort(max(sum(x is not None for x in s.values) for s in grid))
    fits = [f for _, f in fitted]
    clear, qs = stats.field_test(fits)
    cells = [Cell(lat=s.region.lat, lon=s.region.lon, slope_per_decade=f.slope_per_decade, p=f.p, q=q,
                  clear=c, mean=f.mean) for (s, f), c, q in zip(fitted, clear, qs)]
    counts = Counts(rising=sum(f.direction == "rising" for f in fits), falling=sum(f.direction == "falling" for f in fits),
                    flat=sum(f.direction == "flat" for f in fits), clear=sum(clear),
                    raw=sum(f.level == "clear" for f in fits), total=len(cells))
    up = sum(c.clear and c.slope_per_decade > 0 for c in cells)
    down = sum(c.clear and c.slope_per_decade < 0 for c in cells)
    top = max(cells, key=lambda c: abs(c.slope_per_decade))
    near = min(cells, key=lambda c: _distance(q.point, c))
    strongest = Strongest(lat=top.lat, lon=top.lon, slope_per_decade=top.slope_per_decade, bearing=_bearing(q.point, top))
    nearest = Nearest(lat=near.lat, lon=near.lon, slope_per_decade=near.slope_per_decade, p=near.p)
    key = ("too_short" if all(f.level == "too_short" for f in fits) else
           "clear" if counts.clear else "chance")
    change = "rise" if (up, counts.rising) >= (down, counts.falling) else "fall"
    size = (_step([c.lat for c in cells]), _step([c.lon for c in cells]))
    facts = _facts(q, v, grid[0], fits, counts, max(up, down), change, strongest, nearest, size, w)
    return Finding(
        verdict=Verdict(key=f"where.{key}", level="unclear" if key == "chance" else key),
        facts=facts,
        tiles=[w.tile("clear_cells", w("word.n_of", n=facts["n_clear"], total=counts.total), **facts),
               w.tile("strongest", str(facts["strongest_change"]), **facts),
               w.tile("nearest", str(facts["nearest_change"]), **facts)],
        charts=[Cells(title=w("word.where_chart", **facts), cell_size=size, unit=w("word.per_decade", unit=v.unit),
                      warm_up=v.warm_up, cells=[(c.lat, c.lon, c.slope_per_decade, c.clear) for c in cells])],
        method=[w.step(i, **facts) for i in ("grid", "yearly", "cell_trend", "field_fdr")],
        sources=[*grid[0].sources, *(s for s in catalog.sources() if s.id == "gibs-bluemarble")],
        detail=WhereDetail(box=b, cell_size=size, cells=cells, counts=counts, strongest=strongest, nearest=nearest),
    )


def _distance(p: Point, c: Cell) -> float:
    return math.hypot(c.lat - p.lat, (c.lon - p.lon) * math.cos(math.radians(p.lat)))


def _bearing(p: Point, c: Cell) -> str:
    if _distance(p, c) <= T.where_centre:
        return "centre"
    angle = math.degrees(math.atan2(c.lat - p.lat, (c.lon - p.lon) * math.cos(math.radians(p.lat))))
    return COMPASS[round(angle / 45) % 8]


def _step(xs: list[float]) -> float:
    u = sorted(set(xs))
    return min((b - a for a, b in zip(u, u[1:])), default=T.where_snap)


def _facts(q: WhereQ, v: VariableInfo, first: Series, fits: list[Fit], counts: Counts, n_clear: int, change: str,
           strongest: Strongest, nearest: Nearest, size: tuple[float, float], w: Words) -> dict[str, Fact]:
    lo, hi = min(f.first_year for f in fits), max(f.last_year for f in fits)
    return {
        "place": catalog.name(q.point, w.lang), "variable": v.label(w.lang), "noun": v.what(w.lang), "unit": v.unit,
        "period": f"{lo}–{hi}", "first_year": lo, "last_year": hi, "n_years": max(f.n for f in fits),
        "total": counts.total, "n_clear": n_clear, "n_clear_all": counts.clear, "n_raw": counts.raw,
        "n_rising": counts.rising, "n_falling": counts.falling,
        "by_chance": round(T.alpha * counts.total), "change": w(f"word.change.{change}"),
        "bearing": w(f"word.bearing.{strongest.bearing}"),
        "strongest_change": w("word.amount", n=fmt(strongest.slope_per_decade), unit=v.unit).strip(),
        "nearest_change": w("word.amount", n=fmt(nearest.slope_per_decade), unit=v.unit).strip(),
        "nearest_p": fmt_p(nearest.p),
        "cell_size": w("word.cell_size", lat=f"{size[0]:g}", lon=f"{size[1]:g}"), "box_deg": fmt(T.where_box),
        "min_years": T.min_years, "alpha": fmt(T.alpha), "field_q": fmt(T.field_q), "ci_pct": fmt(T.ci * 100),
        "data_source": first.sources[0].name,
    }
