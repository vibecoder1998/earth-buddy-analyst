"""The investigation block of a Result (docs/19): where, why, impact, validation, provenance, what next.
Built from the question's field names, the facts and the catalog. No kind is named here, so a new kind
that reuses those names gets its investigation for free."""
from itertools import chain, zip_longest

from pydantic import TypeAdapter, ValidationError

from .. import catalog
from ..catalog import L10n
from ..stats import T
from ..types import (Country, Dataset, Fact, FollowUp, Investigation, Place, Point, Question, Region, Row, Scope, Seg,
                     Statement)
from ..words import EN, Words
from .base import Finding

_QUESTION = TypeAdapter(Question)
VALIDATION = ("p_value", "leader_p", "nearest_p", "change_per_decade_95pct_range", "sensitivity_range", "leader_range",
              "effective_years", "alpha", "fdr_q")   # fact keys, in the order the rows show
SHOWN = 3            # statements of one kind, and variables that get impact text
FOLLOW_UPS = 4
RANK_GROUP = "southeast_asia_capitals"


def investigate(q, f: Finding, headline: list[Seg], w: Words) -> Investigation:
    vs = _variables(q)
    place = _place(q) or f.focus
    scope = _scope(q, f.facts, w)
    return Investigation(
        scope=scope,
        why=_why(q, vs, f, headline, w),
        impact=_impact(vs, f, scope.name if scope else "", w),
        validation=_validation(vs, f, w),
        limits=_limits(vs, f.facts, w),
        datasets=[_dataset(v, not isinstance(_place(q), Country | Place), f, w) for v in vs],
        next=_next(q, vs, place, w),
        guidance=_guidance(vs, w),
    )


def _variables(q) -> list[str]:
    named = [getattr(q, n, None) for n in ("variable", "x", "y")] + [t.variable for t in getattr(q, "tests", [])]
    return list(dict.fromkeys(v for v in named if v))


def _place(q) -> Region | None:
    return getattr(q, "region", None) or getattr(q, "point", None)


def _span(facts: dict[str, Fact]) -> int | None:
    first, last = facts.get("first_year"), facts.get("last_year")
    return last - first + 1 if isinstance(first, int) and isinstance(last, int) else None


def _spread(lists: list[list[L10n]], lang: str) -> list[str]:
    """Take turns between variables, so two measures each get a say before either gets a second."""
    turns = chain.from_iterable(zip_longest(*lists))
    return list(dict.fromkeys(x(lang) for x in turns if x is not None))[:SHOWN]


def _scope(q, facts: dict[str, Fact], w: Words) -> Scope | None:
    place = _place(q)
    if place is None:
        among = getattr(q, "among", None)
        if among is None:
            return None
        members = catalog.group(among).members if isinstance(among, str) else among
        name = (catalog.group(among).name(w.lang) if isinstance(among, str)
                else ", ".join(catalog.name(r, w.lang) for r in among))
        return Scope(kind="group", name=name, text=w("inv.scope.group", name=name, n=len(members)),
                     limit=w("inv.scope.limit.point"))
    name = catalog.name(place, w.lang)
    if isinstance(place, Point):
        key = "inv.scope.box" if "box_deg" in facts else "inv.scope.point"
        return Scope(kind="point", name=name, limit=w("inv.scope.limit.point"),
                     text=w(key, **facts | {"name": name, "lat": f"{place.lat:g}", "lon": f"{place.lon:g}"}))
    cells = catalog.cells(place)
    return Scope(kind=place.kind, name=name, limit=w("inv.scope.limit.area"),
                 text=w("inv.scope.one" if cells == 1 else "inv.scope.area", name=name, cells=cells))


def _why(q, vs: list[str], f: Finding, headline: list[Seg], w: Words) -> list[Statement]:
    out = [Statement(basis="measured", text="".join(s.t for s in headline)),
           Statement(basis="interpretation", text=w(f"inv.why.level.{f.verdict.level}"))]
    if getattr(q, "x", None):   # a link question asks about the link, so what drives each measure alone is off the point
        return out + [Statement(basis="interpretation", text=w("inv.why.link"))]
    drivers = _spread([catalog.context(v).drivers for v in vs], w.lang)
    if drivers:
        out.append(Statement(basis="interpretation", text=w("inv.why.untested")))
    return out + [Statement(basis="hypothesis", text=d) for d in drivers]


def _impact(vs: list[str], f: Finding, place: str, w: Words) -> list[Statement]:
    matters = dict.fromkeys(catalog.context(v).matters(w.lang) for v in vs[:SHOWN])
    out = [Statement(basis="interpretation", text=m) for m in matters]
    live = [s for s in f.signals if s.level in ("clear", "likely")][:SHOWN]
    if f.signals and not live:
        out.append(Statement(basis="interpretation", text=w("inv.impact.none", place=place)))
    for s in live:
        c, v = catalog.context(s.variable), catalog.variable(s.variable)
        notes = c.up if s.direction == "up" else c.down
        if not notes:
            out.append(Statement(basis="interpretation", text=w("inv.impact.no_notes", variable=v.label(w.lang))))
            continue
        out.append(Statement(basis="interpretation",
                             text=w(f"inv.impact.if.{s.direction}.{s.level}", noun=v.what(w.lang), place=place)))
        out += [Statement(basis="hypothesis", text=n(w.lang)) for n in notes]
    return out


def _row(id: str, value: str, facts: dict[str, Fact], w: Words) -> Row:
    shaped = w(f"inv.row.{id}.value", **facts | {"value": value}) if f"inv.row.{id}.value" in EN else value
    return Row(id=id, label=w(f"inv.row.{id}.label", **facts), value=shaped, help=w(f"inv.row.{id}.help", **facts))


def _validation(vs: list[str], f: Finding, w: Words) -> list[Row]:
    facts, level = f.facts, f.verdict.level
    rows = [_row("status", w(f"inv.status.{level}"), facts, w) if f.tested else
            _row("level", w(f"word.level.{level}").capitalize(), facts, w)]
    method = next((str(facts[k]) for k in ("test", "gap_test") if facts.get(k)), "; ".join(s.title for s in f.method))
    rows.append(_row("method", method, facts, w))
    rows += [_row(k, str(facts[k]), facts, w) for k in VALIDATION[:-2] if facts.get(k) is not None]
    for id in vs:   # a claim keeps one p-value and one interval per variable
        named = facts | {"variable": catalog.variable(id).label(w.lang)}
        rows += [_row(row, str(facts[key]), named, w) for row, key in (("var_p", f"{id}_p"), ("var_range", f"{id}_95pct_range"))
                 if facts.get(key) is not None]
    rows += [_row(k, str(facts[k]), facts, w) for k in VALIDATION[-2:] if facts.get(k) is not None]
    span = _span(facts)
    if span is not None and isinstance(facts.get("n_years"), int):
        rows.append(_row("sample", "", facts | {"span": span}, w))
    return rows


def _limits(vs: list[str], facts: dict[str, Fact], w: Words) -> list[str]:
    out: list[str] = []
    for id in vs:
        v, c = catalog.variable(id), catalog.context(id)
        out += v.caveats.get(w.lang) or v.caveats.get("en", [])
        if c.distinct:
            out.append(c.distinct(w.lang))
    span = _span(facts)
    if span is not None and span < T.climate_years:
        out.append(w("inv.limit.short", span=span, climate_years=T.climate_years))
    if facts.get("test"):
        out.append(w("inv.limit.monotonic"))
    return list(dict.fromkeys(out))


def _dataset(id: str, point: bool, f: Finding, w: Words) -> Dataset:
    v = catalog.variable(id)
    cited = {s.id for s in f.sources}
    months = w("inv.data.season", months=", ".join(w(f"month.{m}") for m in v.season)) if v.season else ""
    return Dataset(
        variable=id, label=v.label(w.lang),
        parameter=(v.point_param if point else None) or v.source.param,
        kind=w(f"inv.data.kind.{v.source.kind}"),
        resolution=v.source.resolution.split(",")[0] if point else v.source.resolution,
        coverage=w("inv.data.coverage", period=f.facts.get("period") or f.facts.get("years") or "",
                   start=v.first_year if point else max(v.first_year, catalog.years()[0])),
        processing=w(f"inv.data.processing.{v.aggregate}") + months + w("inv.data.point" if point else "inv.data.area"),
        sources=[i for i in v.source.ids if i in cited],
    )


def _has(id: str, place: Region) -> bool:
    v = catalog.variable(id)
    return bool(v.point_param) if isinstance(place, Point) else v.regional


def _next(q, vs: list[str], place: Region | None, w: Words) -> list[FollowUp]:
    if not vs or place is None:
        return []
    var, v = vs[0], catalog.variable(vs[0])
    at = catalog.centre(place, w.lang) if v.point_param else None
    other = next((r for r in catalog.context(var).related if r not in vs and _has(r, place)), None)
    words = {"noun": v.what(w.lang), "place": catalog.name(place, w.lang),
             "other": catalog.variable(other).what(w.lang) if other else "",
             "group": catalog.group(RANK_GROUP).name(w.lang)}
    drafts = {
        "trend": {"kind": "trend", "region": place, "variable": var},
        "where": at and {"kind": "where", "point": at, "variable": var},
        "relate": other and {"kind": "relate", "region": place, "x": other, "y": var},
        "extremes": {"kind": "extremes", "region": place, "variable": var},
        "baseline": at and {"kind": "baseline", "point": at, "variable": var},
        "scan": {"kind": "scan", "region": place},
        "rank": at and {"kind": "rank", "variable": var, "among": RANK_GROUP},
    }
    out = []
    for id, draft in drafts.items():
        if not draft or draft["kind"] == q.kind:
            continue
        try:
            asked = _QUESTION.validate_python(draft)
        except ValidationError:
            continue
        out.append(FollowUp(id=id, label=w(f"inv.next.{id}", **words), question=asked.model_dump(mode="json")))
    return out[:FOLLOW_UPS]


def _guidance(vs: list[str], w: Words) -> list[Statement]:
    lines = _spread([catalog.context(v).guidance for v in vs], w.lang) or [w("inv.guidance.local")]
    return [Statement(basis="guidance", text=g) for g in lines]
