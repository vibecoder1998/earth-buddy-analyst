"""The only way an analysis gets data. Country/Place: precomputed file. Point: live NASA POWER.
The Analyze panels read their own tables: fires() for the Fire panel."""
import base64
import calendar
import csv
import functools
import json
import statistics
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, NamedTuple

from . import catalog, power
from .catalog import FireIndex, VariableInfo
from .types import Point, QuestionError, Region, Series, Source, Span, VariableId, Window


def get_series(region: Region, variable: VariableId, window: Window) -> Series:
    v = catalog.variable(variable)
    if isinstance(region, Point):
        s = _from_power(region, v, power.point(region.lat, region.lon, _param(v), *_record(v)), window)
    else:
        if not v.regional:
            raise QuestionError("variable", "not-regional")
        lo, hi = catalog.years()
        s = _clip(region, v, list(range(lo, hi + 1)), catalog.regional_values(variable, region), None, False, window)
    if not s.years:
        raise QuestionError("variable", f"{variable} has no data here")
    return s


def get_many(asks: list[tuple[Region, VariableId]], window: Window, *, tolerant: bool = False) -> list[Series | Exception]:
    """Same order as asks. net's semaphore keeps POWER at 3 in flight; cache hits do not queue.
    tolerant=False raises the first error; tolerant=True returns QuestionError in place (rank lists it as skipped)."""
    with ThreadPoolExecutor(8) as pool:
        futures = [pool.submit(get_series, region, var, window) for region, var in asks]
    out: list[Series | Exception] = []
    for f in futures:
        e = f.exception()
        if e is not None and not tolerant:
            raise e
        out.append(e if e is not None else f.result())
    return out


def get_grid(box: tuple[float, float, float, float], variable: VariableId, window: Window) -> list[Series]:
    v = catalog.variable(variable)
    cells = power.grid(box, _param(v), *_record(v))
    out = [s for c in cells
           if (s := _from_power(Point(lat=c.lat, lon=c.lon, name=f"{c.lat:g}, {c.lon:g}"), v, c.monthly, window)).years]
    if not out:
        raise QuestionError("variable", f"{variable} has no data here")
    return out


def _param(v: VariableInfo) -> str:
    if v.point_param is None:
        raise QuestionError("variable", "no-point-data")
    return v.point_param


def _record(v: VariableInfo) -> tuple[int, int]:
    wraps = bool(v.season) and v.season[0] > v.season[-1]
    return v.first_year - wraps, power.last_complete_year()


def _from_power(point: Point, v: VariableInfo, m: power.Monthly, window: Window) -> Series:
    scaled = [(y, mo, None if x is None else x * v.point_scale) for y, mo, x in m.values]
    years, values = annualise(scaled, v)
    return _clip(point, v, years, values, [t for t in scaled if t[2] is not None], m.cached, window)


def _clip(region: Region, v: VariableInfo, years: list[int], values: list[float | None],
          monthly: list[tuple[int, int, float]] | None, cached: bool, window: Window) -> Series:
    lo, hi = window or (min(years, default=0), max(years, default=0))
    keep = [i for i, y in enumerate(years) if max(lo, v.first_year) <= y <= hi]
    if years and not keep:
        raise QuestionError("window", f"{v.id} has data for {years[0]} to {years[-1]}")
    registry = {s.id: s for s in catalog.sources()}
    return Series(
        region=region, variable=v.id,
        years=[years[i] for i in keep], values=[values[i] for i in keep],
        monthly=None if monthly is None else [t for t in monthly if lo <= t[0] <= hi],
        cells=catalog.cells(region),
        sources=[registry[i].model_copy(update={"cached": cached}) for i in v.source.ids],
    )


def annualise(monthly: list[tuple[int, int, float | None]], v: VariableInfo) -> tuple[list[int], list[float | None]]:
    """Pure. A year counts only with all its months (v.season months if set; wrap -> next year).
    mean | max over months; sum: value × days-in-month when v.per_day, else as given (counts such as FROST_DAYS).
    Years outside the first and last complete ones are dropped; a gap inside the record is None."""
    combine = {"mean": statistics.fmean, "sum": sum, "max": max}[v.aggregate]
    annual = _by_season(monthly, v.season or list(range(1, 13)), combine, v.per_day)
    return _whole(annual, min(annual, default=0), max(annual, default=0))


def season_means(monthly: list[tuple[int, int, float | None]], months: list[int], span: Span) -> tuple[list[int], list[float | None]]:
    """Mean over `months` per year inside `span`, whole seasons only. A wrapping season counts toward the year it ends.
    Runs from the first to the last whole season; a gap between them is None."""
    return _whole(_by_season(monthly, months, statistics.fmean), *span)


def _by_season(monthly: list[tuple[int, int, float | None]], season: list[int],
               combine: Callable[[list[float]], float], per_day: bool = False) -> dict[int, float | None]:
    """One value per year from the months in `season`. A year without all of them is None."""
    wraps = season[0] > season[-1]
    by_year: dict[int, list[float | None]] = {}
    for y, m, x in monthly:
        if m in season:
            if x is not None and per_day:
                x *= calendar.monthrange(y, m)[1]
            by_year.setdefault(y + (wraps and m >= season[0]), []).append(x)
    return {y: combine(xs) if len(xs) == len(season) and None not in xs else None for y, xs in by_year.items()}


def _whole(annual: dict[int, float | None], lo: int, hi: int) -> tuple[list[int], list[float | None]]:
    full = [y for y, x in annual.items() if x is not None and lo <= y <= hi]
    if not full:
        return [], []
    years = list(range(min(full), max(full) + 1))
    return years, [annual.get(y) for y in years]


class Fires(NamedTuple):
    """The Fire panel's tables (data/firms/). Keyed by "aqua" and "terra"; satellites() says what a choice adds up."""
    index: FireIndex
    seasons: dict[str, dict[int, int]]                 # satellite -> season -> detections
    months: dict[str, dict[tuple[int, int], int]]      # satellite -> (year, month) -> detections, every month on file
    provinces: dict[str, dict[str, dict[int, int]]]    # satellite -> province -> season -> detections; no row means 0
    cells: list[tuple[float, float]]                   # (lat, lon) of the centre of each square, index.cell_deg a side
    cell_counts: dict[str, dict[int, bytes]]           # satellite -> season -> one count per square, in cells order
    fire_years: tuple[int, int]                        # first and last whole fire year (November to October) in months
    sources: list[Source]


def satellites(choice: str) -> tuple[str, ...]:
    """The tables a satellite choice adds up. "both" is Aqua plus Terra, so a fire both saw counts twice."""
    return ("aqua", "terra") if choice == "both" else (choice,)


@functools.cache
def fires() -> Fires:
    ix = catalog.fire_index()
    folder = catalog.DATA / "firms"
    lo, hi = ix.seasons

    def rows(key: str) -> list[dict[str, str]]:
        with open(folder / ix.files[key], newline="") as f:
            return list(csv.DictReader(f))

    seasons: dict[str, dict[int, int]] = {"aqua": {}, "terra": {}}
    for r in rows("seasons"):
        if lo <= int(r["season"]) <= hi:
            for sat in seasons:
                seasons[sat][int(r["season"])] = int(r[sat])
    months: dict[str, dict[tuple[int, int], int]] = {"aqua": {}, "terra": {}}
    for r in rows("months"):
        months[r["satellite"].lower()][int(r["year"]), int(r["month"])] = int(r["detections"])
    provinces: dict[str, dict[str, dict[int, int]]] = {"aqua": {}, "terra": {}}
    for r in rows("provinces"):
        if lo <= int(r["season"]) <= hi:
            name = ix.rename.get(r["province"], r["province"])
            provinces[r["satellite"].lower()].setdefault(name, {})[int(r["season"])] = int(r["detections"])
    grid = json.loads((folder / ix.files["cells"]).read_text())
    start = ix.season_months[0]   # a fire year runs from this month to the month before it, a year later
    begun, last = max(min(m) for m in months.values()), min(max(m) for m in months.values())
    registry = {s.id: s for s in catalog.sources()}
    return Fires(
        index=ix, seasons=seasons, months=months, provinces=provinces,
        cells=[(round((iy + 0.5) * ix.cell_deg, 4), round((jx + 0.5) * ix.cell_deg, 4)) for jx, iy in zip(grid["ix"], grid["iy"])],
        cell_counts={sat: {s: base64.b64decode(b) for s, b in zip(grid["seasons"], grid[sat])} for sat in seasons},
        fire_years=(begun[0] + 1 + (begun[1] > start), last[0] - (last[1] < start - 1)),
        sources=[registry[i] for i in ix.sources],
    )
