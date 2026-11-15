"""Fire panel (docs/20): MODIS detections per fire season around Cambodia, by satellite, month and province."""
from .. import catalog, series, stats
from ..stats import fmt, fmt_level, fmt_p
from ..types import Bars, Country, Fact, FireQ, Intervals, QuestionError, Scope
from ..words import Words
from .base import Finding, Ground, PanelDetail, Record, per_decade, signal, tested

CONTEXT = "fire"          # the catalog variable whose name, drivers, impacts and guidance apply
PROVINCES = "cambodia_provinces"
TOP = 5                   # provinces the "busiest provinces" share counts, and the bars mark


def fire(q: FireQ, w: Words) -> Finding:
    f, v = series.fires(), catalog.variable(CONTEXT)
    ix = f.index
    lo, hi = max(q.span[0], ix.seasons[0]), min(q.span[1], ix.seasons[1])
    if lo > hi:
        raise QuestionError("span", f"fire seasons run {ix.seasons[0]} to {ix.seasons[1]}")
    seasons = list(range(lo, hi + 1))
    chosen = series.satellites(q.satellite)
    names = {key: " + ".join(s.capitalize() for s in series.satellites(key)) for key in ("aqua", "terra", "both")}

    def counts(key: str) -> list[float]:
        return [float(sum(f.seasons[sat][s] for sat in series.satellites(key))) for s in seasons]

    values = counts(q.satellite)
    core = tested(Record(place=ix.place(w.lang), label=f"{v.label(w.lang)}, {names[q.satellite]}",
                         noun=f"{v.what(w.lang)} ({names[q.satellite]})", unit=w("word.fire.unit"), rel=True,
                         years=seasons, values=values, sources=f.sources, field="span"), w)
    fits = {key: core.fit if key == q.satellite else stats.trend_test(seasons, counts(key), rel=True) for key in names}
    by_satellite = {key: per_decade(fit, v) for key, fit in fits.items()}

    months = _month_shares(f, chosen, seasons)
    place = {m.name.split(",")[0]: catalog.name(m, w.lang).split(",")[0] for m in catalog.group(PROVINCES).members}
    province = {p: sum(f.provinces[sat].get(p, {}).get(s, 0) for sat in chosen for s in seasons) for p in place}
    total = sum(province.values())
    ranked = sorted(province, key=province.get, reverse=True)
    parts = {key: sum(province[p] for p in z.provinces) for key, z in ix.zones.items() if key != "all"}
    top_zone = max(parts, key=parts.get)
    zone = ix.zones[q.zone]
    by_season = dict(zip(seasons, map(int, values)))
    busiest, quietest = max(by_season, key=by_season.get), min(by_season, key=by_season.get)
    busiest_month = max(months, key=months.get)

    def share(n: float) -> str:
        return w("word.percent", n=fmt(100 * n / total))

    facts: dict[str, Fact] = core.facts | {
        "satellite": names[q.satellite], "zone": zone.name(w.lang),
        "total_detections": total, "mean_per_season": fmt_level(core.fit.mean),
        "busiest_season": busiest, "busiest_n": by_season[busiest],
        "quietest_season": quietest, "quietest_n": by_season[quietest],
        "percent_per_decade": w("word.percent", n=fmt(by_satellite[q.satellite][0])),
        "busiest_month": w(f"month.{busiest_month}"), "busiest_month_share": w("word.percent", n=fmt(months[busiest_month])),
        "season_months": w("word.fire.months", first=w(f"month.{ix.season_months[0]}"), last=w(f"month.{ix.season_months[-1]}")),
        "season_share": w("word.percent", n=fmt(sum(months[m] for m in ix.season_months))),
        "months_until": min(hi, f.fire_years[1]),
        "top_province": place[ranked[0]], "top_province_share": share(province[ranked[0]]),
        "top_provinces": TOP, "top_share": share(sum(province[p] for p in ranked[:TOP])),
        "top_zone": ix.zones[top_zone].name(w.lang), "top_zone_share": share(parts[top_zone]),
        "zone_share": share(sum(province[p] for p in zone.provinces)),
        "like_for_like_until": ix.like_for_like_until, "drift_year": ix.like_for_like_until + 1,
        "archive_first": ix.audit.first, "archive_last": ix.audit.last, "min_confidence": ix.min_confidence,
        "season_first": ix.seasons[0], "season_last": ix.seasons[1],
        "box": w("word.fire.box", south=f"{ix.box[0]:g}", west=f"{ix.box[1]:g}", north=f"{ix.box[2]:g}", east=f"{ix.box[3]:g}"),
    } | {f"{key}_change": w("word.fire.change", percent=w("word.percent", n=fmt(by_satellite[key][0])), p=fmt_p(fit.p),
                           level=w(f"word.level.{fit.level}")) for key, fit in fits.items()}

    listed = [p for p in ranked if p in zone.provinces]
    charts = [
        core.chart,
        Intervals(title=w("word.fire.by_satellite"), unit=w("word.per_decade", unit="%"),
                  rows=[(names[key], *by_satellite[key][:3], key == q.satellite) for key in names]),
        Bars(title=w("word.fire.by_month", **facts), unit="%", labels=[w(f"month.{m}") for m in months],
             values=[round(x, 1) for x in months.values()], highlight=[m in ix.season_months for m in months]),
        Bars(title=w("word.fire.by_province", **facts), unit=w("word.fire.unit"), labels=[place[p] for p in listed],
             values=[round(province[p] / len(seasons), 1) for p in listed], highlight=[p in ranked[:TOP] for p in listed]),
    ]
    rows = [(w(f"word.fire.row.{id}", **facts), w(f"word.fire.value.{id}", **facts)) for id in
            ("total", "mean", "busiest", "quietest", "percent", "aqua", "terra", "both", "month", "season", "province", "top",
             "top_zone", "zone")]
    notes = [w(f"note.fire.{id}", **facts) for id, applies in
             (("both", len(chosen) > 1), ("drift", hi > ix.like_for_like_until), ("months_stop", hi > f.fire_years[1])) if applies]
    return Finding(
        verdict=core.verdict,
        facts=facts,
        tiles=[*core.tiles, w.tile("fire_total", str(total), **facts), w.tile("fire_busiest", str(busiest), **facts)],
        charts=charts,
        method=[w.step("fire_seasons", **facts), *core.steps],
        sources=f.sources,
        detail=PanelDetail(fit=core.fit, size=core.size, sure=core.sure, rows=rows),
        notes=notes + core.notes,
        signals=signal(CONTEXT, core.fit),
        focus=Country(iso3="KHM"),
        ground=Ground(
            scope=Scope(kind="box", name=ix.place(w.lang), text=w("inv.scope.fire", **facts), limit=w("inv.scope.limit.fire")),
            context=[CONTEXT],
            limits=[w(f"inv.limit.fire.{id}", **facts) for id in ("hotspots", "drift", "both", "provinces", "archive")],
        ),
    )


def _month_shares(f: series.Fires, chosen: tuple[str, ...], seasons: list[int]) -> dict[int, float]:
    """Percent of detections in each calendar month, over the whole fire years among the chosen seasons.
    A fire year runs from the season's first month to the month before it, a year later, so the months add to a full year."""
    start = f.index.season_months[0]
    counts = dict.fromkeys(range(1, 13), 0)
    for year in seasons:
        if f.fire_years[0] <= year <= f.fire_years[1]:
            for m in counts:
                counts[m] += sum(f.months[sat].get((year - (m >= start), m), 0) for sat in chosen)
    total = sum(counts.values())
    return {m: 100 * n / total for m, n in counts.items()}
