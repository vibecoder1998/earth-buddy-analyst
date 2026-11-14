"""Free text to Point: coordinates, then the catalog (no network), then Open-Meteo, then Nominatim."""
from .types import Point

TTL_DAYS = 365


def search(q: str) -> list[Point]:
    # TODO row 3:
    # 1 "11.55, 104.92" -> [Point]
    # 2 catalog.find_region(q, "en", exact=True) -> [catalog.centre(region)]
    # 3 Open-Meteo via net.get_json(ttl_days=TTL_DAYS); on DataSourceError, Nominatim; both failing -> DataSourceError
    raise NotImplementedError
