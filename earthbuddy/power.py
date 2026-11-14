"""NASA POWER client: URLs and payload parsing. All HTTP goes through net."""
import datetime
from typing import NamedTuple

from . import net

BASE = "https://power.larc.nasa.gov/api/temporal/monthly"
TTL_DAYS = 30


class Monthly(NamedTuple):
    values: list[tuple[int, int, float | None]]   # (year, month, value); month 13 dropped; fill -> None
    url: str
    cached: bool


class CellMonthly(NamedTuple):
    lat: float
    lon: float
    monthly: Monthly


def last_complete_year() -> int:
    return datetime.date.today().year - 1


def point(lat: float, lon: float, param: str, start: int, end: int) -> Monthly:
    # TODO row 3: fixed-precision, sorted query so the cache key is stable;
    # net.get_json(url, ttl_days=TTL_DAYS, source="power");
    # on DataSourceError(status=422) and end == last_complete_year(): retry once with end - 1;
    # parse properties.parameter[param]["YYYYMM"]; drop month 13; value == header.fill_value or <= -990 -> None
    raise NotImplementedError


def grid(box: tuple[float, float, float, float], param: str, start: int, end: int) -> list[CellMonthly]:
    """Where map (row 11): one regional request, one parameter, each side 2° to 4.5°."""
    raise NotImplementedError
