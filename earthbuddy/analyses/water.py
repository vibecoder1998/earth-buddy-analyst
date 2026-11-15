"""Rain, soil and heat panel (docs/22): one monthly NASA Giovanni series over a box around Cambodia, as yearly means."""
import statistics

from .. import catalog, series, stats
from ..stats import T, fmt, fmt_p
from ..types import Country, Fact, Line, QuestionError, Scope, WaterQ
from ..words import Words
from .base import Finding, Ground, PanelDetail, Record, card, named, per_decade, signal, tested
from .monthly import (PARTS, Month, box, by_part, cited, files, levels, measured, monthly_line, rows, steps, typical_year,
                      whole_record)

KHM = Country(iso3="KHM")
PANEL = "water"
FIRE = "aqua"      # the satellite whose monthly counts the soil-to-fire link reads: the branch's choice
# The month-to-month links the branch's case tabs quote, each as (from, to). "fire" is the FIRE satellite's counts.
LINKS = (("imerg", "soil"), ("soil", "t2m"), ("soil", "fire"))


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
    ids = catalog.measures(PANEL)
    wholes = {id: whole_record(id, w) for id in ids}
    whole = wholes[info.id]
    under = [x for x in wholes.values() if x.plain < T.alpha]
    pair = next(x.info.pair for x in wholes.values() if x.info.pair)
    rain = [series.monthly(id).values for id in pair]
    facts: dict[str, Fact] = core.facts | part_facts | cycle_facts | steps(w) | {
        "n_months": len(months), "step_year": jump, "step_p": fmt_p(jump_p), "box": box(m, w),
        "file_first": m.values[0][0], "file_last": m.values[-1][0],
        "series": len(ids), "series_under": len(under), "under_names": w("word.list").join(x.card["name"] for x in under),
        "series_clear": sum(x.fit.level == "clear" for x in wholes.values()),
        "rain_r": fmt(stats.pearson(*([x for *_, x in s] for s in rain))), "rain_months": len(rain[0]),
        **named("sel", card(core.fit, years, values, info.unit, info.rel, w, months)), **named("whole", whole.card),
        **named("here", levels(months, info.unit, w)),
    }
    for id, x in wholes.items():
        facts |= named(f"all_{id}", x.card)
    if info.rel:
        facts["percent_per_decade"] = w("word.percent", n=fmt(per_decade(core.fit, info)[0]))
    ratio, ratio_facts = _ratio(pair, span, w)
    sel = {k.removeprefix("sel_"): v for k, v in facts.items() if k.startswith("sel_")}
    facts |= ratio_facts | {"sel_text": w("word.card", **sel), "sel_line_text": w("word.card.line", **sel),
                            "sel_monthly_text": w("word.card.monthly", **sel), "six_text": w("word.card.six", **whole.card)}
    mark = {"mark_year": jump, "mark_label": w("word.step_mark", p=facts["step_p"])} if step else {}
    by_season = {p: series.season_means(m.values, PARTS[p], span) for p in ("wet", "dry")}
    season_years = sorted(set(by_season["wet"][0]) | set(by_season["dry"][0]))
    charts = [
        core.chart.model_copy(update=mark),
        monthly_line(months, info.unit, w("word.monthly", **facts), w, trend=[(x + 0.5, y) for x, y in core.chart.trend]),
        parts,
        cycle,
        Line(title=w("word.water.seasons", **facts), unit=info.unit, x=season_years,
             y=[dict(zip(*by_season["wet"])).get(y) for y in season_years],
             compare=[dict(zip(*by_season["dry"])).get(y) for y in season_years],
             labels=(w("word.season.wet"), w("word.season.dry"))),
        ratio,
    ]
    shown = ["level", "average", "change", *(["percent"] if info.rel else []), "sel_card", "sel_line", "sel_monthly",
             *(p for p in PARTS if f"{p}_change" in facts), "peak", "low", *(["step"] if step else []), "six",
             *(["ratio", "ratio_share"] if ratio.mark_year is not None else []), "rain_r", "series_under"]
    stepped = whole.info.made.kind == "model" and whole.step_p < T.pettitt_p and span[0] <= whole.step_after < span[1]
    notes += [w(f"note.{id}", **facts) for id, applies in
              (("panel.step", step), ("water.model_step", stepped), ("water.ratio", ratio.mark_year is not None),
               ("panel.few", core.fit.n < T.reliable)) if applies]
    return Finding(
        verdict=core.verdict,
        facts=facts,
        tiles=[*core.tiles, w.tile("panel_level", str(facts["average"]), **facts),
               w.tile("panel_peak", str(facts["peak_month"]), **facts)],
        charts=charts,
        method=[w.step("giovanni", **facts), *core.steps, w.step("opinions", **facts), w.step("parts", **facts),
                w.step("panel_step", **facts), w.step("whole_record", **facts), w.step("water_links", **facts),
                w.step("files", **facts)],
        sources=cited(m.sources, series.fires().sources),
        detail=PanelDetail(fit=core.fit, size=core.size, sure=core.sure, rows=[
            *measured([info.id], w), *rows(shown, facts, w),
            *((w("word.card.fixed", **x.card), w("word.card", **x.card)) for x in wholes.values()),
            *(_link(a, b, w) for a, b in LINKS),
            *measured([id for id in ids if id != info.id], w), *files(ids, w)]),
        notes=notes + core.notes,
        signals=signal(info.context, core.fit),
        focus=KHM,
        ground=Ground(
            scope=Scope(kind="box", name=place, text=w("inv.scope.giovanni", **facts), limit=w("inv.scope.limit.giovanni")),
            context=[info.context],
            limits=[w(f"inv.limit.{id}", **facts) for id in
                    ("giovanni.model", "giovanni.steps", "giovanni.box", "panel.power", "water.humidity", "giovanni.files")],
        ),
    )


def _monthly(id: str) -> tuple[str, list[Month]]:
    """(name, monthly values) of one end of a link: a measure, or the fire counts over the whole calendar years on file."""
    if id != "fire":
        m = series.monthly(id)
        return id, m.values
    f = series.fires()
    first, last = f.index.seasons[0], catalog.years()[1]
    return id, [(y, mo, float(f.months[FIRE].get((y, mo), 0))) for y in range(first, last + 1) for mo in range(1, 13)]


def _link(a: str, b: str, w: Words) -> tuple[str, str]:
    """Pearson r between two monthly series over the months both have, as they are and with each calendar month's mean taken out."""
    (_, xs), (_, ys) = _monthly(a), _monthly(b)
    both = sorted({t[:2] for t in xs} & {t[:2] for t in ys})
    xs, ys = ([t for t in s if t[:2] in set(both)] for s in (xs, ys))

    def name(id: str) -> str:
        return w("word.water.fire", satellite=FIRE.capitalize()) if id == "fire" else catalog.measure(id)[0].noun(w.lang)

    return (w("word.water.link.row", a=name(a), b=name(b)),
            w("word.water.link.value", n=len(both), first=both[0][0], last=both[-1][0],
              raw=fmt(stats.pearson([x for *_, x in xs], [y for *_, y in ys])),
              anom=fmt(stats.pearson(stats.anomalies(xs), stats.anomalies(ys)))))


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
    facts |= {"ratio_year": jump, "ratio_break_p": fmt_p(p), "ratio_before": fmt(before), "ratio_after": fmt(after),
              "ratio_before_share": w("word.percent", n=fmt(100 * before)), "ratio_after_share": w("word.percent", n=fmt(100 * after))}
    return line.model_copy(update={"mark_year": jump, "mark_label": w("word.step_mark", p=facts["ratio_break_p"]),
                                   "means": [(years[0], jump - 1, before), (jump, years[-1], after)]}), facts
