"""The only way an analysis gets data. Country/Place: precomputed file. Point: live NASA POWER."""
from concurrent.futures import ThreadPoolExecutor

from .catalog import VariableInfo
from .types import Region, Series, VariableId, Window


def get_series(region: Region, variable: VariableId, window: Window) -> Series:
    # TODO row 3:
    # v = catalog.variable(variable)
    # Country | Place: v.regional else QuestionError("variable", "not-regional");
    #                  values = catalog.regional_values(variable, region); years = catalog.years(); no network
    # Point: v.point_param else QuestionError("variable", "no-point-data");
    #        m = power.point(lat, lon, v.point_param, v.first_year, power.last_complete_year())
    #        years, values = annualise(m.values, v)
    # sources: catalog.sources() entries named by v.source.ids, each model_copy(update={"cached": m.cached})
    # window: clip; outside the record -> QuestionError("window")
    raise NotImplementedError


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
    """Where map (row 11): one regional request; each cell becomes a Point series."""
    raise NotImplementedError


def annualise(monthly: list[tuple[int, int, float | None]], v: VariableInfo) -> tuple[list[int], list[float | None]]:
    """Pure. A year counts only with all its months (v.season months if set; wrap -> next year).
    mean | max over months; sum: value × days-in-month when v.per_day, else as given (counts such as FROST_DAYS)."""
    raise NotImplementedError
