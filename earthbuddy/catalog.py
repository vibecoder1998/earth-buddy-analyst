"""The closed list of what the app can measure and where. Reads spec-schema files in data/ (strict)."""
import functools
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict

from . import ROOT, SOURCES
from .types import GroupId, Lang, Point, Region, Source, VariableId

DATA = ROOT / "data"
ALLOWED_AGENCIES = {"NASA", "NASA/JAXA"}


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")   # schema drift fails loudly


class L10n(_M):
    en: str
    km: str | None = None

    def __call__(self, lang: Lang) -> str:
        return (self.km if lang == "km" else None) or self.en


class SourceInfo(_M):
    dataset: str
    param: str
    kind: Literal["reanalysis", "satellite", "model"]
    url: str
    resolution: str


class VariableInfo(_M):
    id: VariableId
    label: L10n
    what: L10n
    definition: L10n
    unit: str
    decimals: int
    rel: bool
    aggregate: Literal["mean", "sum", "max"]
    per_day: bool = False            # POWER gives a rate (mm/day): a sum needs days-in-month
    season: list[int] | None = None  # calendar months; when it wraps (rain_dry 11..4) Nov-Dec count toward the next year
    warm_up: bool
    topics: list[str]
    keywords: dict[str, list[str]]
    up: dict[str, list[str]]
    down: dict[str, list[str]]
    source: SourceInfo
    caveats: dict[str, list[str]]
    doubt: Literal["up", "down"] | None
    regional: bool
    point_param: str | None
    first_year: int


class PlaceInfo(_M):
    id: str
    name: L10n
    aliases: dict[str, list[str]]
    kind: str
    bbox: tuple[float, float, float, float]
    lat: float
    lon: float
    cells: int


class CountryInfo(_M):
    name: L10n
    aliases: dict[str, list[str]]
    cells: int
    lat: float
    lon: float


class Group(_M):
    id: GroupId
    name: L10n
    aliases: dict[str, list[str]]
    members: list[Region]
    note: L10n


class Catalog(_M):
    years: tuple[int, int]
    variables: list[VariableInfo]
    places: list[PlaceInfo]
    countries: dict[str, CountryInfo]
    groups: list[Group]
    topics: list[dict]


@functools.cache
def load() -> Catalog:
    """Parse data/catalog.json once. Lookups below build their indexes once too."""
    return Catalog.model_validate(json.loads((DATA / "catalog.json").read_text()))


@functools.cache
def sources() -> list[Source]:
    return [Source.model_validate(s) for s in json.loads(SOURCES.read_text())]


def raw() -> dict:
    """What GET /api/catalog serves (before analyses adds `kinds`)."""
    raise NotImplementedError


def years() -> tuple[int, int]:
    return load().years


def variables() -> list[VariableInfo]:
    return load().variables


def variable(id: VariableId) -> VariableInfo:
    raise NotImplementedError


def name(region: Region, lang: Lang = "en") -> str:
    raise NotImplementedError


def centre(region: Region, lang: Lang = "en") -> Point:
    """Country/Place -> its centre Point; Point -> itself."""
    raise NotImplementedError


def cells(region: Region) -> int | None:
    raise NotImplementedError


def find_region(text: str, lang: Lang, *, exact: bool = False) -> Region | None:
    """Longest word-bounded alias match: places, then countries, then group member Points (provinces, capitals). No network."""
    raise NotImplementedError


def group(id: GroupId) -> Group:
    raise NotImplementedError


def regional_values(variable: VariableId, region: Region) -> list[float | None]:
    """data/v/<id>.json for a Country or Place. Missing region -> QuestionError("region")."""
    raise NotImplementedError


def audit() -> dict:
    """data/audit.json: {frozen, note, claims: [{id, quote, region, tests, window, known_before}]}."""
    raise NotImplementedError
