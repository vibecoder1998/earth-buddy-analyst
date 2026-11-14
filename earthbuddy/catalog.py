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


class LatLon(_M):
    lat: float
    lon: float


class PlaceInfo(_M):
    id: str
    name: L10n
    aliases: dict[str, list[str]]
    kind: str
    bbox: tuple[float, float, float, float]
    lat: float
    lon: float
    cells: int
    point: LatLon | None = None


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
    member_aliases: dict[str, list[str]] = {}
    member_names: dict[str, dict[str, str]] = {}
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
    if not isinstance(region, Point):
        return _info(region).name(lang)
    if info := _centres().get((region.lat, region.lon, region.name)):
        return info.name(lang)
    return _point_names(lang).get(region.name, region.name)


@functools.cache
def _centres() -> dict[tuple[float, float, str], PlaceInfo | CountryInfo]:
    """The Point centre() makes for each place and country, back to its entry."""
    c = load()
    regions = [*(Place(id=p.id) for p in c.places), *(Country(iso3=iso) for iso in c.countries)]
    return {(at.lat, at.lon, at.name): _info(r) for r, at in zip(regions, map(centre, regions))}


@functools.cache
def _point_names(lang: Lang) -> dict[str, str]:
    return {en: local for g in load().groups for en, local in g.member_names.get(lang, {}).items()}


def centre(region: Region, lang: Lang = "en") -> Point:
    """Country/Place -> its centre Point (a city's SEDAC centre when it has one); Point -> itself."""
    if isinstance(region, Point):
        return region
    info = _info(region)
    at = (info.point if isinstance(info, PlaceInfo) else None) or info
    return Point(lat=at.lat, lon=at.lon, name=info.name(lang)[:80])


def cells(region: Region) -> int | None:
    return None if isinstance(region, Point) else _info(region).cells


@functools.cache
def _aliases(lang: Lang) -> list[tuple[str, Region]]:
    """Longest alias first; on a tie, places, then countries, then group member Points."""
    langs = ("en", "km") if lang == "km" else ("en",)

    def names(n: L10n, aliases: dict[str, list[str]]) -> set[str]:
        return {s.casefold() for lg in langs for s in (getattr(n, lg), *aliases.get(lg, [])) if s}

    c = load()
    tiers = [
        [(a, Place(id=p.id)) for p in c.places for a in names(p.name, p.aliases)],
        [(a, Country(iso3=iso)) for iso, k in c.countries.items() for a in names(k.name, k.aliases)],
        [(a, m) for g in c.groups for m in g.members if isinstance(m, Point)
         for a in (m.name.split(",")[0].casefold(), *g.member_aliases.get(m.name, []))],
    ]
    return sorted((hit for tier in tiers for hit in tier), key=lambda h: -len(h[0]))


def _alias_re(alias: str) -> str:
    if not alias.isascii():
        return re.escape(alias)   # Khmer writes no spaces between words
    return rf"(?<!\w){re.escape(alias)}(?!\w)"


def _contains(text: str, alias: str) -> bool:
    return re.search(_alias_re(alias), text) is not None


def find_region(text: str, lang: Lang, *, exact: bool = False) -> Region | None:
    """Longest word-bounded alias match across places, countries, and group member Points (provinces, capitals). No network."""
    t = " ".join(text.casefold().split())
    return next((r for a, r in _aliases(lang) if (t == a if exact else _contains(t, a))), None)


def find_regions(text: str, lang: Lang) -> list[Region]:
    """Every distinct region named, longest alias first; a matched alias is blanked so its own words do not match again."""
    t = " ".join(text.casefold().split())
    found: list[Region] = []
    for a, r in _aliases(lang):
        t, n = re.subn(_alias_re(a), " ", t)
        if n and r not in found:
            found.append(r)
    return found


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


@functools.cache
def summary() -> dict[VariableId, dict[str, dict]]:
    return json.loads((DATA / "summary.json").read_text())


def audit() -> dict:
    """data/audit.json: {frozen, note, claims: [{id, quote, region, tests, window, known_before}]}."""
    return json.loads((DATA / "audit.json").read_text())
