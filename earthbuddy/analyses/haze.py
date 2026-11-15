"""Soot and haze panel (docs/21): one MERRA-2 aerosol series over a box around Cambodia, by dry season, and its link to fire."""
import statistics

from .. import catalog, series, stats
from ..stats import T, fmt, fmt_p
from ..types import Country, Fact, HazeQ, Line, QuestionError, Scatter, Scope
from ..words import Words
from .base import Finding, Ground, PanelDetail, Record, per_decade, signal, tested
from .monthly import PARTS, box, by_part, monthly_line, rows, typical_year

KHM = Country(iso3="KHM")
DRY = PARTS["dry"]


def haze(q: HazeQ, w: Words) -> Finding:
    m, f = series.monthly(q.measure), series.fires()
    info, ix = m.info, f.index
    years, values = series.season_means(m.values, DRY, (max(q.span[0], ix.seasons[0]), min(q.span[1], ix.seasons[1])))
    if not years:
        raise QuestionError("span", f"fire seasons run {ix.seasons[0]} to {ix.seasons[1]}; "
                                    f"the {info.id} file ends in {m.values[-1][0]}")
    sats = series.satellites(q.satellite)
    satellite = " + ".join(s.capitalize() for s in sats)
    place = catalog.name(KHM, w.lang)
    core = tested(Record(place=place, label=w("word.haze.dry", variable=info.label(w.lang)),
                         noun=w("word.haze.dry_noun", noun=info.noun(w.lang)), unit=info.unit, rel=info.rel,
                         years=years, values=values, sources=m.sources + f.sources, field="span"), w)
    lo, hi = core.fit.first_year, core.fit.last_year
    # fire years: November before the first season to October of the last, so every month counts once
    months = [t for t in m.values if (lo - 1, DRY[0]) <= t[:2] <= (hi, DRY[0] - 1)]
    fires = [sum(f.months[s].get(t[:2], 0) for s in sats) for t in months]
    parts, part_facts, notes = by_part(m, (lo, hi), "dry", w)
    cycle, cycle_facts = typical_year(months, info.unit, w)
    jump, jump_p = stats.pettitt(years, values)
    step = jump_p < T.pettitt_p and stats.is_step(years, values, jump)
    pairs = [(y, x, sum(f.seasons[s][y] for s in sats)) for y, x in zip(years, values) if x is not None]
    season = stats.relation(*(list(c) for c in zip(*pairs)))
    facts: dict[str, Fact] = core.facts | part_facts | cycle_facts | {
        "satellite": satellite, "n_months": len(months), "step_year": jump, "step_p": fmt_p(jump_p), "box": box(m, w),
        "file_first": m.values[0][0], "file_last": m.values[-1][0],
        "like_for_like_until": ix.like_for_like_until, "drift_year": ix.like_for_like_until + 1,
        "season_rho": fmt(season.rho), "season_rho_raw": fmt(season.rho_raw), "season_link_p": fmt_p(season.p),
        "season_strength": w(f"word.strength.{stats.strength(season.rho)}"),
        "season_level": w(f"word.level.{stats.level_of(season.p, len(pairs))}"), "n_link_seasons": len(pairs),
    }
    if info.rel:
        facts["percent_per_decade"] = w("word.percent", n=fmt(per_decade(core.fit, info)[0]))
    shown = ["average", "change", *(["percent"] if info.rel else []), *(p for p in PARTS if f"{p}_change" in facts),
             "peak", "low", "season_link"]
    if len(months) >= T.stl_min_months:   # always true past T.min_years seasons; the anomalies need it
        order = list(range(len(months)))
        fire_months = [(y, mo, float(n)) for (y, mo, _), n in zip(months, fires)]
        link = stats.relation(order, stats.anomalies(months), stats.anomalies(fire_months))
        facts |= {"month_rho": fmt(link.rho), "month_link_p": fmt_p(link.p), "n_link_months": len(months),
                  "month_rho_raw": fmt(stats.relation(order, [x for _, _, x in months], fires).rho_raw)}
        shown += ["month_link", "month_raw"]
    mark = {"mark_year": jump, "mark_label": w("word.step_mark", p=facts["step_p"])} if step else {}
    if step:
        shown.append("step")
        notes.append(w("note.panel.step", **facts))
    notes += [w(f"note.fire.{id}", **facts) for id, applies in
              (("both", len(sats) > 1), ("drift", hi > ix.like_for_like_until)) if applies]
    charts = [
        core.chart.model_copy(update=mark),
        monthly_line(months, info.unit, w("word.monthly", variable=info.label(w.lang))),
        _through_the_year(months, fires, w("word.haze.fire", satellite=satellite), info.label(w.lang), w),
        parts,
        Scatter(title=w("word.haze.scatter", variable=info.label(w.lang), satellite=satellite),
                points=[(x, float(n), str(y)) for y, x, n in pairs],
                x_label=w("word.haze.scatter_x", unit=info.unit), y_label=w("word.haze.scatter_y", satellite=satellite)),
    ]
    return Finding(
        verdict=core.verdict,
        facts=facts,
        tiles=[*core.tiles, w.tile("haze_link", str(facts["season_rho"]), **facts),
               w.tile("panel_peak", str(facts["peak_month"]), **facts)],
        charts=charts,
        method=[w.step("haze_seasons", **facts), *core.steps, w.step("parts", **facts), w.step("panel_step", **facts),
                w.step("haze_link", **facts)],
        sources=m.sources + f.sources,
        detail=PanelDetail(fit=core.fit, size=core.size, sure=core.sure, rows=rows(shown, facts, w)),
        notes=notes + core.notes,
        signals=signal(info.context, core.fit),
        focus=KHM,
        ground=Ground(
            scope=Scope(kind="box", name=place, text=w("inv.scope.giovanni", **facts), limit=w("inv.scope.limit.giovanni")),
            context=[info.context, "fire"],
            limits=[w(f"inv.limit.{id}", **facts) for id in
                    ("haze.model", "haze.link", "giovanni.box", "giovanni.files", "fire.hotspots")],
        ),
    )


def _through_the_year(months: list[tuple[int, int, float]], fires: list[int], fire_label: str, label: str,
                      w: Words) -> Line:
    """Each calendar month's average as a percent of the average month, for the aerosol (y) and the fire counts (compare)."""
    def shares(xs: list[float]) -> list[float]:
        by_month = [statistics.fmean(x for (_, mo, _), x in zip(months, xs) if mo == k) for k in range(1, 13)]
        mean = statistics.fmean(by_month)
        return [100 * x / mean for x in by_month]

    return Line(title=w("word.haze.through_year"), x=list(range(1, 13)), y=shares([x for _, _, x in months]),
                compare=shares([float(n) for n in fires]), labels=(label, fire_label), unit=w("word.haze.share_unit"))
