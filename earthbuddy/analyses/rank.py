"""Rank places and say when the leaders cannot be told apart (docs/09)."""
from typing import Literal, NamedTuple

from pydantic import BaseModel

from .. import catalog, series, stats
from ..catalog import Group, VariableInfo
from ..stats import T, fmt, fmt_level, fmt_p
from ..types import (DataSourceError, Fact, Fit, Intervals, Point, QuestionError, RankQ, Region, Series, Step, Tile,
                     TooShort, Verdict)
from ..words import Words
from .base import Finding, per_decade

VERDICTS = ("rank.clear_leader", "rank.tied", "rank.none")
NUMBER = {"change": fmt, "level": fmt_level}


class Row(BaseModel):
    region: Region
    name: str
    rank: int
    value: float
    lo: float
    hi: float
    p: float
    q: float
    clear: bool
    same_as_leader: bool
    shares_grid_cell: bool
    text: str


class Skipped(BaseModel):
    name: str
    reason: Literal["no_series", "too_short", "source_down"]


class RankDetail(BaseModel):
    rows: list[Row]
    skipped: list[Skipped]
    tied_with_first: int


class _Place(NamedTuple):
    region: Region
    name: str
    series: Series
    fit: Fit
    value: float
    lo: float
    hi: float


def rank(q: RankQ, w: Words) -> Finding:
    v = catalog.variable(q.variable)
    group = catalog.group(q.among) if isinstance(q.among, str) else None
    regions = group.members if group else q.among
    places, skipped, errors = _measure(q, v, regions, w)
    if len(places) < 2:
        raise next(iter(errors), QuestionError("among", "fewer than two places have enough years"))
    places.sort(key=lambda x: x.value, reverse=q.order == "highest")
    years = sorted({y for x in places for y in x.series.years})
    aligned = [[dict(zip(x.series.years, x.series.values)).get(y) for y in years] for x in places]
    cells = stats.shared_cells(aligned)
    compared = [_as_percent_of_mean(row, x.fit, v, q.metric) for row, x in zip(aligned, places)]
    gap_ps = [1.0 if 0 in cells[i] else stats.gap_p(years, compared[0], compared[i], q.metric)
              for i in range(1, len(places))]
    same = [False, *(0 in cells[i] or g >= T.fdr_q for i, g in enumerate(stats.bh(gap_ps), 1))]
    qs = stats.bh([x.fit.p for x in places])
    unit = w("word.per_decade", unit=per_decade(places[0].fit, v)[3]) if q.metric == "change" else v.unit
    num = NUMBER[q.metric]
    rows = [Row(region=x.region, name=x.name, rank=i + 1, value=x.value, lo=x.lo, hi=x.hi, p=x.fit.p, q=qs[i],
                clear=x.fit.level == "clear" and qs[i] < T.fdr_q, same_as_leader=same[i], shares_grid_cell=bool(cells[i]),
                text=w("word.rank_row", value=num(x.value), lo=num(x.lo), hi=num(x.hi), unit=unit, ci_pct=fmt(T.ci * 100)))
            for i, x in enumerate(places)]
    shown = rows[:q.top_n]
    n_tied = sum(same)
    key = "rank.none" if n_tied == len(rows) - 1 else "rank.tied" if n_tied else "rank.clear_leader"
    facts = _facts(q, v, group, rows, unit, n_tied, len(skipped), years, w)
    return Finding(
        verdict=Verdict(key=key, level={"rank.none": "unclear", "rank.tied": "likely"}.get(key, "clear")),
        facts=facts,
        tiles=_tiles(facts, w),
        charts=[Intervals(title=w(f"word.rank_chart.{q.metric}", variable=v.label(w.lang)),
                          rows=[(_label_without_country(r), r.value, r.lo, r.hi, r.rank == 1 or r.same_as_leader)
                                for r in shown],
                          unit=unit)],
        method=_method(q, regions, facts, w),
        sources=[s for x in places for s in x.series.sources],
        detail=RankDetail(rows=shown, skipped=skipped, tied_with_first=sum(r.same_as_leader for r in shown)),
        notes=_notes(group, regions, rows, cells, len(shown), n_tied, w),
    )


def _measure(q: RankQ, v: VariableInfo, regions: list[Region],
             w: Words) -> tuple[list[_Place], list[Skipped], list[Exception]]:
    got = series.get_many([(r, v.id) for r in regions], q.window, tolerant=True)
    places: list[_Place] = []
    skipped: list[Skipped] = []
    errors: list[Exception] = []
    for region, s in zip(regions, got):
        name = catalog.name(region, w.lang)
        if isinstance(s, (QuestionError, DataSourceError)):
            errors.append(s)
            skipped.append(Skipped(name=name, reason="no_series" if isinstance(s, QuestionError) else "source_down"))
            continue
        if isinstance(s, Exception):
            raise s
        try:
            fit = stats.trend_test(s.years, s.values, rel=v.rel)
        except TooShort:
            skipped.append(Skipped(name=name, reason="too_short"))
            continue
        if q.metric == "change":
            value, lo, hi, _ = per_decade(fit, v)
        else:
            value, lo, hi = stats.mean_interval([x for x in s.values if x is not None][-T.rank_level_years:])
        places.append(_Place(region=region, name=name, series=s, fit=fit, value=value, lo=lo, hi=hi))
    return places, skipped, errors


def _label_without_country(r: Row) -> str:
    return r.name.split(",")[0] if isinstance(r.region, Point) else r.name


def _as_percent_of_mean(row: list[float | None], fit: Fit, v: VariableInfo, metric: str) -> list[float | None]:
    if metric != "change" or not (v.rel and fit.mean > 0):
        return row
    return [None if x is None else x / fit.mean for x in row]


def _facts(q: RankQ, v: VariableInfo, group: Group | None, rows: list[Row], unit: str, n_tied: int, n_skipped: int,
           years: list[int], w: Words) -> dict[str, Fact]:
    lead = rows[0]
    way = "" if q.metric == "level" else "." + ("up" if lead.value > 0 else "down")
    noun = v.what(w.lang)
    group_key = f"word.group.{q.among}" if group else "word.group.listed"
    num = NUMBER[q.metric]
    amount = w("word.amount", n=num(lead.value), unit=unit)
    return {
        "place": lead.name, "region": w(group_key) if w.has(group_key) else group.name(w.lang),
        "noun": noun, "variable": v.label(w.lang), "ranked_by": w(f"word.rank_by.{q.metric}.{q.order}{way}", noun=noun),
        "gap_test": w(f"word.gap_test.{q.metric}"),
        "leader_value": amount.strip(),
        "leader_range": w("word.range", lo=num(lead.lo), hi=num(lead.hi), unit="").strip(),
        "leader_p": fmt_p(lead.p), "runner_up": rows[1].name,
        "n_places": len(rows), "n_tied": n_tied, "n_clear": sum(r.clear for r in rows), "n_skipped": n_skipped,
        "tied_others": w("word.others_one") if n_tied == 1 else w("word.others", n=n_tied),
        "period": f"{years[0]}–{years[-1]}", "first_year": years[0], "last_year": years[-1],
        "level_years": T.rank_level_years, "alpha": fmt(T.alpha), "fdr_q": fmt(T.fdr_q), "ci_pct": fmt(T.ci * 100),
    }


def _tiles(facts: dict[str, Fact], w: Words) -> list[Tile]:
    return [
        w.tile("leader", str(facts["place"]), **facts),
        w.tile("tied", w("word.n_of", n=facts["n_tied"], total=int(facts["n_places"]) - 1), **facts),
        w.tile("ranked", str(facts["n_places"]), **facts),
    ]


def _method(q: RankQ, regions: list[Region], facts: dict[str, Fact], w: Words) -> list[Step]:
    ids = ["rank_data", f"rank_{q.metric}", "rank_fdr", f"rank_gap_{q.metric}"]
    if any(isinstance(r, Point) for r in regions):
        ids.append("rank_cells")
    return [w.step(i, **facts) for i in ids]


def _notes(group: Group | None, regions: list[Region], rows: list[Row], cells: list[set[int]], shown: int, n_tied: int,
           w: Words) -> list[str]:
    notes = [group.note(w.lang)] if group else [w("note.rank_points")] if any(isinstance(r, Point) for r in regions) else []
    shared = sorted({tuple(sorted({i, *c})) for i, c in enumerate(cells[:shown]) if c})
    notes += [w("note.rank_shared_cell", names="; ".join(rows[i].name for i in s)) for s in shared]
    hidden = n_tied - sum(r.same_as_leader for r in rows[:shown])
    if hidden:
        notes.append(w("note.rank_more_tied", n=hidden, top_n=shown))
    return notes
