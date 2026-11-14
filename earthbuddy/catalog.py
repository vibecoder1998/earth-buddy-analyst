"""The closed list of what the app can measure and where. Reads spec-schema files in data/ (strict)."""
import functools
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from . import ROOT, SOURCES
from .types import Country, GroupId, Lang, Place, Point, QuestionError, Region, Source, VariableId

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
    param: str
    kind: Literal["reanalysis", "satellite", "model"]
    resolution: str
    ids: list[str]      # data/sources.json entries: dataset, method paper, "power"


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
    point_scale: float = 1           # POWER serves GWETROOT, GWETTOP and FRSEAICE as fractions; the catalog unit is %
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
    return json.loads((DATA / "catalog.json").read_text())


def years() -> tuple[int, int]:
    return load().years


def variables() -> list[VariableInfo]:
    return load().variables


@functools.cache
def _variables() -> dict[VariableId, VariableInfo]:
    return {v.id: v for v in load().variables}


def variable(id: VariableId) -> VariableInfo:
    try:
        return _variables()[id]
    except KeyError:
        raise QuestionError("variable", f"unknown variable {id!r}") from None


def _info(region: Region) -> PlaceInfo | CountryInfo:
    found = load().countries.get(region.iso3) if isinstance(region, Country) else _places().get(region.id)
    if found is None:
        raise QuestionError("region", f"unknown region {region!r}")
    return found


@functools.cache
def _places() -> dict[str, PlaceInfo]:
    return {p.id: p for p in load().places}


def name(region: Region, lang: Lang = "en") -> str:
    return region.name if isinstance(region, Point) else _info(region).name(lang)


def centre(region: Region, lang: Lang = "en") -> Point:
    """Country/Place -> its centre Point; Point -> itself."""
    if isinstance(region, Point):
        return region
    info = _info(region)
    return Point(lat=info.lat, lon=info.lon, name=info.name(lang)[:80])


def cells(region: Region) -> int | None:
    return None if isinstance(region, Point) else _info(region).cells


@functools.cache
def _aliases(lang: Lang) -> list[tuple[str, Region]]:
    """Places, then countries, then group member Points; longest alias first within each tier."""
    langs = ("en", "km") if lang == "km" else ("en",)

    def names(n: L10n, aliases: dict[str, list[str]]) -> set[str]:
        return {s.casefold() for lg in langs for s in (getattr(n, lg), *aliases.get(lg, [])) if s}

    c = load()
    tiers = [
        [(a, Place(id=p.id)) for p in c.places for a in names(p.name, p.aliases)],
        [(a, Country(iso3=iso)) for iso, k in c.countries.items() for a in names(k.name, k.aliases)],
        [(m.name.split(",")[0].casefold(), m) for g in c.groups for m in g.members if isinstance(m, Point)],
    ]
    return [hit for tier in tiers for hit in sorted(tier, key=lambda h: -len(h[0]))]


def _contains(text: str, alias: str) -> bool:
    if not alias.isascii():
        return alias in text   # Khmer writes no spaces between words
    return re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text) is not None


def find_region(text: str, lang: Lang, *, exact: bool = False) -> Region | None:
    """Longest word-bounded alias match: places, then countries, then group member Points (provinces, capitals). No network."""
    t = " ".join(text.casefold().split())
    return next((r for a, r in _aliases(lang) if (t == a if exact else _contains(t, a))), None)


@functools.cache
def _groups() -> dict[GroupId, Group]:
    return {g.id: g for g in load().groups}


def group(id: GroupId) -> Group:
    try:
        return _groups()[id]
    except KeyError:
        raise QuestionError("among", f"unknown group {id!r}") from None


@functools.cache
def _regional(variable: VariableId) -> dict[str, list[float | None]]:
    return json.loads((DATA / "v" / f"{variable}.json").read_text())["regions"]


def regional_values(variable: VariableId, region: Region) -> list[float | None]:
    """data/v/<id>.json for a Country or Place. Missing region -> QuestionError("region")."""
    if variable not in _variables():
        raise QuestionError("variable", f"unknown variable {variable!r}")
    key = region.iso3 if isinstance(region, Country) else getattr(region, "id", None)
    values = _regional(variable).get(key)
    if values is None:
        raise QuestionError("region", f"no {variable} series for {region!r}")
    return values


def audit() -> dict:
    """data/audit.json: {frozen, note, claims: [{id, quote, region, tests, window, known_before}]}."""
    return json.loads((DATA / "audit.json").read_text())
