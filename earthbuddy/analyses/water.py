"""Rain, soil and heat panel (docs/22): one monthly NASA Giovanni series over a box around Cambodia, as yearly means."""
import statistics

from .. import catalog, series, stats
from ..stats import T, fmt, fmt_p
from ..types import Country, Fact, Line, QuestionError, Scope, WaterQ
from ..words import Words
from .base import Finding, Ground, PanelDetail, Record, per_decade, signal, tested
from .monthly import PARTS, box, by_part, monthly_line, rows, typical_year

KHM = Country(iso3="KHM")


def water(q: WaterQ, w: Words) -> Finding:
    m = series.monthly(q.measure)
    info = m.info
    years, values = series.season_means(m.values, PARTS["year"], q.span)
    if not years:
        raise QuestionError("span", f"the {info.id} file runs {m.values[0][0]} to {m.values[-1][0]}")
    place = catalog.name(KHM, w.lang)
    core = tested(Record(place=place, label=info.label(w.lang), noun=info.noun(w.lang), unit=info.unit, rel=info.rel,
                         years=years, values=values, sources=m.sources, field="span"), w)
    span = (core.fit.first_year, core.fit.last_year)
    months = [t for t in m.values if span[0] <= t[0] <= span[1]]
    parts, part_facts, notes = by_part(m, span, "year", w)
    cycle, cycle_facts = typical_year(months, info.unit, w)
    jump, jump_p = stats.pettitt(years, values)
    step = jump_p < T.pettitt_p and stats.is_step(years, values, jump)
    facts: dict[str, Fact] = core.facts | part_facts | cycle_facts | {
        "n_months": len(months), "step_year": jump, "step_p": fmt_p(jump_p), "box": box(m, w),
        "file_first": m.values[0][0], "file_last": m.values[-1][0],
    }
    if info.rel:
        facts["percent_per_decade"] = w("word.percent", n=fmt(per_decade(core.fit, info)[0]))
    mark = {"mark_year": jump, "mark_label": w("word.step_mark", p=facts["step_p"])} if step else {}
    charts = [core.chart.model_copy(update=mark),monthly_line(months, info.unit, w("word.monthly", **facts)), parts, cycle]
    shown = ["average", "change", *(["percent"] if info.rel else []), *(p for p in PARTS if f"{p}_change" in facts),
             "peak", "low", *(["step"] if step else [])]
    if step:
        notes.append(w("note.panel.step", **facts))
    if info.pair:
        ratio, ratio_facts = _ratio(info.pair, span, w)
        charts.append(ratio)
        facts |= ratio_facts
        if ratio.mark_year is not None:
            shown.append("ratio")
            notes.append(w("note.water.ratio", **facts))
    return Finding(
        verdict=core.verdict,
        facts=facts,
        tiles=[*core.tiles, w.tile("panel_level", str(facts["average"]), **facts),
               w.tile("panel_peak", str(facts["peak_month"]), **facts)],
        charts=charts,
        method=[w.step("giovanni", **facts), *core.steps, w.step("parts", **facts), w.step("panel_step", **facts)],
        sources=m.sources,
        detail=PanelDetail(fit=core.fit, size=core.size, sure=core.sure, rows=rows(shown, facts, w)),
        notes=notes + core.notes,
        signals=signal(info.context, core.fit),
        focus=KHM,
        ground=Ground(
            scope=Scope(kind="box", name=place, text=w("inv.scope.giovanni", **facts), limit=w("inv.scope.limit.giovanni")),
            context=[info.context],
            limits=[w(f"inv.limit.giovanni.{id}", **facts) for id in ("model", "box", "files")],
        ),
    )


def _ratio(pair: tuple[str, str], span: tuple[int, int], w: Words) -> tuple[Line, dict[str, Fact]]:
    """The first series over the second, per year. Where Pettitt finds a break, the chart marks it and draws both levels."""
    over, under = (series.monthly(k) for k in pair)
    a, b = (dict(zip(*series.season_means(s.values, PARTS["year"], span))) for s in (over, under))
    years = [y for y in a if a[y] is not None and b.get(y)]
    ratio = [a[y] / b[y] for y in years]
    facts: dict[str, Fact] = {"ratio_over": over.info.noun(w.lang), "ratio_under": under.info.noun(w.lang)}
    line = Line(title=w("word.water.ratio", over=facts["ratio_over"], under=facts["ratio_under"]), x=years, y=ratio,
                unit=w("word.ratio"))
    jump, p = stats.pettitt(years, ratio)
    if p >= T.pettitt_p:
        return line, facts
    before = statistics.fmean(r for y, r in zip(years, ratio) if y < jump)
    after = statistics.fmean(r for y, r in zip(years, ratio) if y >= jump)
    facts |= {"ratio_year": jump, "ratio_break_p": fmt_p(p), "ratio_before": fmt(before), "ratio_after": fmt(after)}
    return line.model_copy(update={"mark_year": jump, "mark_label": w("word.step_mark", p=facts["ratio_break_p"]),
                                   "means": [(years[0], jump - 1, before), (jump, years[-1], after)]}), facts
