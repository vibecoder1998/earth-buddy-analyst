"""NASA POWER client: URLs and payload parsing. All HTTP goes through net."""
import datetime
from typing import NamedTuple
from urllib.parse import urlencode

from . import net
from .types import DataSourceError

BASE = "https://power.larc.nasa.gov/api/temporal/monthly"
TTL_DAYS = 30
PARSE_ERRORS = (KeyError, TypeError, ValueError, IndexError)
TO_CATALOG_UNIT = {"MJ/m^2/day": 1e6 / 86400}   # the AG community serves irradiance in MJ/m²/day; the catalog and the Zarr stores use W/m²


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
    got = _get("point", {"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}"}, param, start, end)
    try:
        fill = got.payload["header"]["fill_value"]
        return Monthly(_values(got.payload["properties"]["parameter"][param], fill, _scale(got.payload, param)), got.url, got.cached)
    except PARSE_ERRORS:
        raise DataSourceError("NASA POWER sent an unexpected response", 200, got.url) from None


def grid(box: tuple[float, float, float, float], param: str, start: int, end: int) -> list[CellMonthly]:
    """POWER's regional endpoint takes one parameter per request and sides of 2° to 4.5°."""
    lat_min, lat_max, lon_min, lon_max = box
    got = _get("regional", {"latitude-max": f"{lat_max:g}", "latitude-min": f"{lat_min:g}",
                            "longitude-max": f"{lon_max:g}", "longitude-min": f"{lon_min:g}"}, param, start, end)
    try:
        fill, scale = got.payload["header"]["fill_value"], _scale(got.payload, param)
        return [CellMonthly(float(f["geometry"]["coordinates"][1]), float(f["geometry"]["coordinates"][0]),
                            Monthly(_values(f["properties"]["parameter"][param], fill, scale), got.url, got.cached))
                for f in got.payload["features"]]
    except PARSE_ERRORS:
        raise DataSourceError("NASA POWER sent an unexpected response", 200, got.url) from None


def _get(endpoint: str, where: dict[str, str], param: str, start: int, end: int) -> net.Fetched:
    """A 422 on the latest year means it is not published yet: retry once with end − 1."""
    query = where | {"community": "AG", "end": end, "format": "JSON", "parameters": param, "start": start}
    try:
        return net.get_json(f"{BASE}/{endpoint}?{urlencode(sorted(query.items()))}", ttl_days=TTL_DAYS, source="power")
    except DataSourceError as e:
        if e.status != 422 or end != last_complete_year():
            raise
        return _get(endpoint, where, param, start, end - 1)


def _scale(payload: dict, param: str) -> float:
    return TO_CATALOG_UNIT.get(payload.get("parameters", {}).get(param, {}).get("units"), 1)


def _values(by_month: dict[str, float], fill: float, scale: float) -> list[tuple[int, int, float | None]]:
    return [(int(k[:4]), int(k[4:]), None if v == fill or v <= -990 else float(v) * scale)
            for k, v in sorted(by_month.items()) if k[4:] != "13"]
