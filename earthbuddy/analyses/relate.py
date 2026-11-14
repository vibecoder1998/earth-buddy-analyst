"""Whether two measures move together at one place, once each trend is removed (docs/11)."""
from typing import Literal

from pydantic import BaseModel

from .. import catalog, series, stats
from ..stats import T, fmt, fmt_p
from ..types import Fact, QuestionError, RelateQ, Scatter, Tile, Verdict
from ..words import Words
from .base import Finding

VERDICTS = ("relate.together", "relate.opposite", "relate.none")
STEPS = ("relate_data", "relate_detrend", "relate_rho", "relate_memory", "relate_lead", "relate_cause")


class Sensitivity(BaseModel):
    value: float
    lo: float
    hi: float


class Lead(BaseModel):
    rho: float
    p: float


class RelateDetail(BaseModel):
    n_years: int
    rho: float
    rho_raw: float
    p: float
    effective_years: float
    strength: Literal["no", "weak", "moderate", "strong"]
    direction: Literal["together", "opposite"]
    share_moving_together: float
    sensitivity: Sensitivity
    x_leads_one_year: Lead | None
    points: list[tuple[float, float, int]]
    short_record: bool


def relate(q: RelateQ, w: Words) -> Finding:
    if q.x == q.y:
        raise QuestionError("y", "pick two different measures")
    vx, vy = catalog.variable(q.x), catalog.variable(q.y)
    sx, sy = series.get_many([(q.region, q.x), (q.region, q.y)], q.window)
    by_year = dict(zip(sy.years, sy.values))
    shared = [(t, a, by_year[t]) for t, a in zip(sx.years, sx.values) if a is not None and by_year.get(t) is not None]
    if len(shared) < T.reliable:
        raise QuestionError("window", f"relate needs {T.reliable} shared years, found {len(shared)}")
    years, xs, ys = (list(c) for c in zip(*shared))
    for name, values in (("x", xs), ("y", ys)):
        if len(set(values)) == 1:
            raise QuestionError(name, "this measure does not change here")
    r = stats.relation(years, xs, ys)
    strength = stats.strength(r.rho)
    direction = "together" if r.rho >= 0 else "opposite"
    level = stats.level_of(r.p, len(years))
    key = "relate.none" if strength == "no" or level not in ("clear", "likely") else f"relate.{direction}"
    ra, rb = r.residuals
    detail = RelateDetail(
        n_years=len(years), rho=r.rho, rho_raw=r.rho_raw, p=r.p, effective_years=r.n_eff, strength=strength,
        direction=direction, share_moving_together=r.share_together, sensitivity=Sensitivity(
            value=r.sensitivity[0], lo=r.sensitivity[1], hi=r.sensitivity[2]),
        x_leads_one_year=None if r.lead is None else Lead(rho=r.lead[0], p=r.lead[1]),
        points=[(float(a), float(b), y) for a, b, y in zip(ra, rb, years)], short_record=len(years) < T.short_record)
    facts = _facts(q, detail, years, level, sx.sources[0].name, sy.sources[0].name, w)
    shared_refs = [i for i in vx.source.ids if i in vy.source.ids and i != "power"]   # POWER only serves the data
    notes = [w("note.relate_short", **facts)] if detail.short_record else []
    if shared_refs:
        name = next(s.name for s in catalog.sources() if s.id == shared_refs[0])
        notes.append(w("note.relate_one_dataset", source=name, **facts))
    return Finding(
        verdict=Verdict(key=key, level=level),
        facts=facts,
        tiles=_tiles(facts, w),
        charts=[Scatter(title=w("word.relate_chart", x=facts["x_variable"], y=facts["y_variable"]),
                        points=[(a, b, str(y)) for a, b, y in detail.points],
                        x_label=w("word.residual", unit=vx.unit), y_label=w("word.residual", unit=vy.unit))],
        method=[w.step(i, **facts) for i in STEPS],
        sources=[*sx.sources, *sy.sources],
        detail=detail,
        notes=notes,
    )


def _facts(q: RelateQ, d: RelateDetail, years: list[int], level: str, x_source: str, y_source: str,
           w: Words) -> dict[str, Fact]:
    vx, vy = catalog.variable(q.x), catalog.variable(q.y)
    s = d.sensitivity
    facts: dict[str, Fact] = {
        "place": catalog.name(q.region, w.lang), "x_noun": vx.what(w.lang), "y_noun": vy.what(w.lang),
        "x_variable": vx.label(w.lang), "y_variable": vy.label(w.lang),
        "period": f"{years[0]}–{years[-1]}", "first_year": years[0], "last_year": years[-1], "n_years": d.n_years,
        "rho": fmt(d.rho), "rho_raw": fmt(d.rho_raw), "p_value": fmt_p(d.p), "effective_years": fmt(d.effective_years),
        "strength": w(f"word.strength.{d.strength}"), "certainty": w(f"word.level.{level}"),
        "share_together": w("word.percent", n=fmt(d.share_moving_together * 100)),
        "sensitivity": w("word.sensitivity", n=fmt(s.value), y_unit=vy.unit, x_unit=vx.unit).strip(),
        "sensitivity_range": w("word.range", lo=fmt(s.lo), hi=fmt(s.hi), unit="").strip(),
        "data_source": x_source if x_source == y_source else f"{x_source}; {y_source}",
        "alpha": fmt(T.alpha), "likely": fmt(T.likely), "ci_pct": fmt(T.ci * 100), "reliable": T.reliable,
        "short_record": T.short_record,
        "rho_weak": fmt(T.rho_weak), "rho_moderate": fmt(T.rho_moderate), "rho_strong": fmt(T.rho_strong),
    }
    lead = d.x_leads_one_year
    facts["lead"] = (w("word.lead.none") if lead is None else
                     w("word.lead.tested", x_noun=facts["x_noun"], y_noun=facts["y_noun"], rho=fmt(lead.rho), p=fmt_p(lead.p)))
    return facts


def _tiles(facts: dict[str, Fact], w: Words) -> list[Tile]:
    return [
        w.tile("link", str(facts["strength"]).capitalize(), **facts),
        w.tile("rho", str(facts["rho"]), **facts),
        w.tile("together", str(facts["share_together"]), **facts),
    ]
