"""Free text to Point, offline: coordinates, then the catalog, then the NASA SEDAC gazetteer."""
from .types import Point


def search(q: str) -> list[Point]:
    raise NotImplementedError
