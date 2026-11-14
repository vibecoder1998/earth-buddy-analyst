"""Free text to Point, offline: coordinates, then the catalog, then the NASA SEDAC gazetteer."""
import functools
import json
import re
import unicodedata

from . import catalog
from .catalog import DATA
from .types import Point
from .words import Words

GAZETTEER = DATA / "gazetteer.json"
LIMIT = 5
_COORDS = re.compile(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*")


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).casefold().strip()


@functools.cache
def _gazetteer() -> tuple[list[tuple[set[str], dict]], dict[str, str]]:
    entries = json.loads(GAZETTEER.read_text())
    countries = {e["iso3"]: e["name"] for e in entries if e["level"] == 0}
    return [({_fold(n) for n in (e["name"], *e["alt_names"])}, e) for e in entries], countries


def _named(e: dict, countries: dict[str, str]) -> Point:
    name = e["name"] if e["level"] == 0 else f"{e['name']}, {countries.get(e['iso3'], e['iso3'])}"
    return Point(lat=e["lat"], lon=e["lon"], name=name[:80])


def search(q: str) -> list[Point]:
    if m := _COORDS.fullmatch(q):
        lat, lon = float(m[1]), float(m[2])
        return [Point(lat=lat, lon=lon, name=Words("en")("word.point", lat=str(lat), lon=str(lon)))] if abs(lat) <= 90 and abs(lon) <= 180 else []
    if region := catalog.find_region(q, "km", exact=True):
        return [catalog.centre(region)]
    key = _fold(q)
    if not key:
        return []
    entries, countries = _gazetteer()
    hits = [(key not in names, e["level"], e["name"], e) for names, e in entries
            if any(n.startswith(key) for n in names)]
    return [_named(e, countries) for *_, e in sorted(hits, key=lambda h: h[:3])[:LIMIT]]
