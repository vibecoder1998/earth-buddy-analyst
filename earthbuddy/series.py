"""The only way an analysis gets data. Country/Place: precomputed file. Point: live NASA POWER."""
import calendar
import statistics
from concurrent.futures import ThreadPoolExecutor

from . import catalog, power
from .catalog import VariableInfo
from .types import Point, QuestionError, Region, Series, VariableId, Window


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
    keep = [i for i, y in enumerate(years) if lo <= y <= hi]
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
    season = v.season or list(range(1, 13))
    wraps = season[0] > season[-1]
    by_year: dict[int, list[float | None]] = {}
    for y, m, x in monthly:
        if m in season:
            if x is not None and v.per_day:
                x *= calendar.monthrange(y, m)[1]
            by_year.setdefault(y + (wraps and m >= season[0]), []).append(x)
    combine = {"mean": statistics.fmean, "sum": sum, "max": max}[v.aggregate]
    annual = {y: combine(xs) if len(xs) == len(season) and None not in xs else None for y, xs in by_year.items()}
    full = [y for y, x in annual.items() if x is not None]
    if not full:
        return [], []
    years = list(range(min(full), max(full) + 1))
    return years, [annual.get(y) for y in years]
