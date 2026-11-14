"""NASA POWER client: URLs and payload parsing. All HTTP goes through net."""
import datetime
from typing import NamedTuple
from urllib.parse import urlencode

from . import net
from .types import DataSourceError

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
    query = {"community": "AG", "end": end, "format": "JSON", "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}",
             "parameters": param, "start": start}
    try:
        got = net.get_json(f"{BASE}/point?{urlencode(query)}", ttl_days=TTL_DAYS, source="power")
    except DataSourceError as e:
        if e.status != 422 or end != last_complete_year():
            raise
        return point(lat, lon, param, start, end - 1)
    try:
        fill = got.payload["header"]["fill_value"]
        values = [(int(k[:4]), int(k[4:]), None if v == fill or v <= -990 else float(v))
                  for k, v in sorted(got.payload["properties"]["parameter"][param].items()) if k[4:] != "13"]
    except (KeyError, TypeError, ValueError):
        raise DataSourceError("NASA POWER sent an unexpected response", 200, got.url) from None
    return Monthly(values, got.url, got.cached)


def grid(box: tuple[float, float, float, float], param: str, start: int, end: int) -> list[CellMonthly]:
    """Where map (row 11): one regional request, one parameter, each side 2° to 4.5°."""
    raise NotImplementedError
