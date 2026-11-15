"""Fire panel (docs/20): MODIS detections per fire season around Cambodia, by satellite, month and province."""
import statistics

from .. import catalog, series, stats
from ..stats import T, fmt, fmt_level
from ..types import Bars, Cells, Country, Fact, Fit, FireQ, Intervals, Line, QuestionError, Scope
from ..words import Words
from .base import Finding, Ground, PanelDetail, Record, card, named, per_decade, signal, tested

CONTEXT = "fire"          # the catalog variable whose name, drivers, impacts and guidance apply
PROVINCES = "cambodia_provinces"
TOP = 5                   # provinces the "busiest provinces" share counts, and the bars mark
SATELLITES = ("aqua", "terra", "both")
BESIDE = {"aqua": "terra", "terra": "aqua", "both": "aqua"}   # the second line drawn beside each satellite choice
CENTRE_DEG = 0.3          # side of the square the province trend map draws at a province centre


def fire(q: FireQ, w: Words) -> Finding:
    f, v = series.fires(), catalog.variable(CONTEXT)
    ix = f.index
    lo, hi = max(q.span[0], ix.seasons[0]), min(q.span[1], ix.seasons[1])
    if lo > hi:
        raise QuestionError("span", f"fire seasons run {ix.seasons[0]} to {ix.seasons[1]}")
    seasons, on_file = list(range(lo, hi + 1)), list(range(ix.seasons[0], ix.seasons[1] + 1))
    chosen = series.satellites(q.satellite)
    names = {key: " + ".join(s.capitalize() for s in series.satellites(key)) for key in SATELLITES}
    unit = w("word.fire.unit")

    def counts(key: str, years: list[int] = seasons) -> list[float]:
        return [float(sum(f.seasons[sat][s] for sat in series.satellites(key))) for s in years]

    values = counts(q.satellite)
    core = tested(Record(place=ix.place(w.lang), label=f"{v.label(w.lang)}, {names[q.satellite]}",
                         noun=f"{v.what(w.lang)} ({names[q.satellite]})", unit=unit, rel=True,
                         years=seasons, values=values, sources=f.sources, field="span"), w)
    fits = {key: core.fit if key == q.satellite else stats.trend_test(seasons, counts(key), rel=True) for key in names}
    by_satellite = {key: per_decade(fit, v) for key, fit in fits.items()}
    cards = {key: card(fit, seasons, counts(key), unit, True, w) for key, fit in fits.items()}

    months = _month_shares(f, chosen, seasons)
    members = {m.name.split(",")[0]: m for m in catalog.group(PROVINCES).members}
    place = {p: catalog.name(m, w.lang).split(",")[0] for p, m in members.items()}
    centres = {p: catalog.centre(m) for p, m in members.items()}
    province = {p: sum(f.provinces[sat].get(p, {}).get(s, 0) for sat in chosen for s in seasons) for p in place}
    total = sum(province.values())
    ranked = sorted(province, key=province.get, reverse=True)
    zones = {key: z for key, z in ix.zones.items() if key != "all"}
    parts = {key: sum(province[p] for p in z.provinces) for key, z in zones.items()}
    by_size = sorted(parts, key=parts.get, reverse=True)
    zone = ix.zones[q.zone]
    by_season = dict(zip(seasons, map(int, values)))
    busiest, quietest = max(by_season, key=by_season.get), min(by_season, key=by_season.get)
    busiest_month = max(months, key=months.get)
    squares = [sum(f.cell_counts[sat][s][i] for sat in chosen for s in seasons) / len(seasons) for i in range(len(f.cells))]

    def share(n: float, digits=fmt) -> str:
        return w("word.percent", n=digits(100 * n / total))

    def month_span(ms: list[int]) -> str:
        return w("word.fire.months", first=w(f"month.{ms[0]}"), last=w(f"month.{ms[-1]}"))

    kept = {sat: sum(f.months[sat].values()) for sat in ("aqua", "terra")}
    month_keys = sorted({k for sat in kept for k in f.months[sat]})
    in_months = {key: sum(n for sat in kept for (_, m), n in f.months[sat].items() if m in ms)
                 for key, ms in (("season", ix.season_months), ("peak", ix.peak_months))}
    facts: dict[str, Fact] = core.facts | {
        "satellite": names[q.satellite], "beside": names[BESIDE[q.satellite]], "zone": zone.name(w.lang),
        "total_detections": total, "mean_per_season": fmt_level(core.fit.mean),
        "busiest_season": busiest, "busiest_n": by_season[busiest],
        "quietest_season": quietest, "quietest_n": by_season[quietest],
        "percent_per_decade": w("word.percent", n=fmt(by_satellite[q.satellite][0])),
        "busiest_month": w(f"month.{busiest_month}"), "busiest_month_share": w("word.percent", n=fmt(months[busiest_month])),
        "season_months": month_span(ix.season_months),
        "season_share": w("word.percent", n=fmt(sum(months[m] for m in ix.season_months))),
        "peak_months": month_span(ix.peak_months),
        "peak_share": w("word.percent", n=fmt(sum(months[m] for m in ix.peak_months))),
        "months_until": min(hi, f.fire_years[1]),
        "top_province": place[ranked[0]], "top_province_share": share(province[ranked[0]]),
        "top_provinces": TOP, "top_share": share(sum(province[p] for p in ranked[:TOP])),
        "top_list": w("word.list").join(w("word.fire.ranked", name=place[p], share=share(province[p], fmt_level),
                                          n=fmt_level(province[p] / len(seasons))) for p in ranked[:TOP]),
        "rest_provinces": len(ranked) - TOP, "rest_share": share(sum(province[p] for p in ranked[TOP:]), fmt_level),
        "top_zone": zones[by_size[0]].name(w.lang), "top_zone_share": share(parts[by_size[0]]),
        "zone_share": share(sum(province[p] for p in zone.provinces)),
        "busiest_square": fmt_level(max(squares)), "squares": sum(n > 0 for n in squares), "cell_deg": f"{ix.cell_deg:g}",
        "like_for_like_until": ix.like_for_like_until, "drift_year": ix.like_for_like_until + 1,
        "archive_first": ix.audit.first, "archive_last": ix.audit.last, "min_confidence": ix.min_confidence,
        "season_first": ix.seasons[0], "season_last": ix.seasons[1], "seasons_on_file": len(on_file),
        "box": w("word.fire.box", south=f"{ix.box[0]:g}", west=f"{ix.box[1]:g}", north=f"{ix.box[2]:g}", east=f"{ix.box[3]:g}"),
        **ix.audit.model_dump(exclude={"first", "last"}),
        "kept_vegetation": ix.audit.raw_rows - ix.audit.dropped_type, "kept_aqua": kept["aqua"], "kept_terra": kept["terra"],
        "season_rows": in_months["season"], "peak_rows": in_months["peak"],
        "season_rows_share": w("word.percent", n=fmt_level(100 * in_months["season"] / ix.audit.clean_rows)),
        "months_on_file": len(month_keys),
        "months_expected": (month_keys[-1][0] - month_keys[0][0]) * 12 + month_keys[-1][1] - month_keys[0][1] + 1,
        "table_rows": w("word.list").join(str(n) for n in f.table_rows),
        "fire_min_total": T.fire_min_total, "fire_min_distinct": T.fire_min_distinct, "fdr_q": fmt(T.fdr_q),
    }
    for key in names:
        facts |= named(key, cards[key])

    listed = [p for p in ranked if p in zone.provinces]
    tested_provinces = _province_fits(f, chosen, seasons, list(place))
    qs = dict(zip(tested_provinces, stats.bh([fit.p for fit in tested_provinces.values()])))
    under = [fit for fit in tested_provinces.values() if fit.p < T.alpha]
    untested = [place[p] for p in ranked if p not in qs]
    facts |= {"provinces_tested": len(qs), "provinces_found": sum(x < T.fdr_q for x in qs.values()),
              "provinces_under": len(under), "provinces_chance": fmt(len(qs) * T.alpha), "provinces_up": sum(fit.direction == "rising" for fit in under),
              "provinces_down": sum(fit.direction == "falling" for fit in under),
              "untested": w("word.list").join(untested)}
    changing = sorted(((place[p], *per_decade(tested_provinces[p], v)[:3], qs[p] < T.fdr_q) for p in listed if p in qs),
                      key=lambda row: row[1], reverse=True)

    cross_years = list(range(ix.seasons[0], catalog.years()[1] + 1))
    catalog_fire = series.get_series(Country(iso3="KHM"), CONTEXT, (cross_years[0], cross_years[-1]))
    yearly = {sat: [float(sum(f.months[sat].get((y, m), 0) for m in range(1, 13))) for y in cross_years] for sat in ("terra", "aqua")}
    cross = {"catalog": (catalog_fire.years, catalog_fire.values), "terra": (cross_years, yearly["terra"]),
             "aqua": (cross_years, yearly["aqua"])}
    cross_fits = {key: stats.trend_test(*xy, rel=True) for key, xy in cross.items()}
    cross_names = {key: w("word.fire.catalog_row") if key == "catalog" else names[key] for key in cross}
    cross_cards = {key: card(cross_fits[key], *cross[key], w("word.fire.year_unit"), True, w) for key in cross}
    both_years = [(a, b) for a, b in zip(catalog_fire.values, yearly["terra"]) if a is not None]
    facts |= {"cross_first": cross_years[0], "cross_last": cross_years[-1],
              "cross_rho": fmt(stats.spearman(*zip(*both_years))[0]),
              "cross_ratio": fmt_level(statistics.median(a / b for a, b in both_years))}
    for key in cross:
        facts |= named(f"cross_{key}", cross_cards[key])

    def per_month(key: str) -> list[float | None]:
        sats = series.satellites(key)
        return [float(sum(f.months[sat][k] for sat in sats)) if all(k in f.months[sat] for sat in sats) else None
                for k in month_keys]

    after = [float(s) for s in on_file if s > ix.like_for_like_until]
    beside = (names[q.satellite], names[BESIDE[q.satellite]])
    charts = [
        core.chart.model_copy(update={
            "title": w("word.fire.seasons", **facts), "x": on_file, "y": counts(q.satellite, on_file),
            "compare": counts(BESIDE[q.satellite], on_file), "labels": beside,
            "spans": [(after[0], after[-1])] if after else None,
            "span_label": w("word.fire.span_drift", **facts) if after else None}),
        Intervals(title=w("word.fire.by_satellite"), unit=w("word.per_decade", unit="%"),
                  rows=[(names[key], *by_satellite[key][:3], key == q.satellite) for key in names]),
        Line(title=w("word.fire.all_months", **facts), unit=w("word.fire.month_unit"),
             x=[_at(*k) for k in month_keys], y=per_month(q.satellite), compare=per_month(BESIDE[q.satellite]), labels=beside,
             spans=[(_at(lo - 1, ix.season_months[0]), _at(hi, ix.season_months[-1]))],
             span_label=w("word.fire.span_chosen", **facts)),
        Bars(title=w("word.fire.by_month", **facts), unit="%", labels=[w(f"month.{m}") for m in months],
             values=[round(x, 1) for x in months.values()], highlight=[m in ix.season_months for m in months]),
        Cells(title=w("word.fire.density", **facts), unit=unit, cell_size=(ix.cell_deg, ix.cell_deg),
              warm_up=True, scale="level", cells=[(lat, lon, round(n, 2), False) for (lat, lon), n in zip(f.cells, squares) if n]),
        Bars(title=w("word.fire.by_zone", **facts), unit="%", labels=[zones[key].name(w.lang) for key in by_size],
             values=[round(100 * parts[key] / total, 1) for key in by_size],
             highlight=[key == (by_size[0] if q.zone == "all" else q.zone) for key in by_size]),
        Bars(title=w("word.fire.by_province", **facts), unit=unit, labels=[place[p] for p in listed],
             values=[round(province[p] / len(seasons), 1) for p in listed], highlight=[p in ranked[:TOP] for p in listed]),
        *([Cells(title=w("word.fire.change_map", **facts), unit=w("word.per_decade", unit="%"),
                 cell_size=(CENTRE_DEG, CENTRE_DEG), warm_up=True, scale="change",
                 cells=[(centres[p].lat, centres[p].lon, round(per_decade(fit, v)[0], 1), qs[p] < T.fdr_q)
                        for p, fit in tested_provinces.items()]),
           Intervals(title=w("word.fire.province_change", **facts), unit=w("word.per_decade", unit="%"), rows=changing)]
          if changing else []),
        Intervals(title=w("word.fire.cross", first=cross_years[0], last=cross_years[-1]), unit=w("word.per_decade", unit="%"),
                  rows=[(cross_names[key], *per_decade(fit, v)[:3], key == q.satellite) for key, fit in cross_fits.items()]),
        Bars(title=w("word.fire.funnel", **facts), unit=w("word.fire.rows_unit"),
             labels=[w(f"word.fire.funnel.{id}", **facts) for id in ("raw", "vegetation", "kept", "season", "peak")],
             values=[float(facts[k]) for k in ("raw_rows", "kept_vegetation", "clean_rows", "season_rows", "peak_rows")],
             highlight=[False, False, True, False, False]),
    ]

    def row(id: str, **more: Fact) -> tuple[str, str]:
        return w(f"word.fire.row.{id}", **facts | more), w(f"word.fire.value.{id}", **facts | more)

    rows = [
        *(row(id) for id in ("total", "mean", "busiest", "quietest", "percent")),
        *((w("word.card.row", name=names[key]), w("word.card", **cards[key])) for key in names),
        *(row(id) for id in ("month", "peak", "season", "province", "top", "rest", "top_zone")),
        *(row("part", part=zones[key].name(w.lang), part_share=share(parts[key]),
              members=w("word.list").join(place[p] for p in zones[key].provinces)) for key in by_size),
        *(row(id) for id in ("zone", "square")),
        *([row("provinces")] if qs else []),      # under T.reliable seasons nothing is tested, and a note says so
        *([row("untested")] if qs and untested else []),
        *((w("word.fire.row.cross", name=cross_names[key], **facts), w("word.card", **cross_cards[key])) for key in cross),
        *(row(id) for id in ("cross_link", "measured", "archive", "kept", "coverage", "used", "unused", "tables")),
    ]
    notes = [w(f"note.fire.{id}", **facts) for id, applies in
             (("both", len(chosen) > 1), ("drift", hi > ix.like_for_like_until), ("months_stop", hi > f.fire_years[1]),
              ("provinces_short", len(seasons) < T.reliable)) if applies]
    notes += [w("note.panel.few", **facts)] if core.fit.n < T.reliable else []
    return Finding(
        verdict=core.verdict,
        facts=facts,
        tiles=[*core.tiles, w.tile("fire_total", str(total), **facts), w.tile("fire_busiest", str(busiest), **facts)],
        charts=charts,
        method=[w.step("fire_seasons", **facts), w.step("fire_audit", **facts), *core.steps, w.step("opinions", **facts),
                w.step("fire_provinces", **facts), w.step("fire_cross", **facts)],
        sources=f.sources,
        detail=PanelDetail(fit=core.fit, size=core.size, sure=core.sure, rows=rows),
        notes=notes + core.notes,
        signals=signal(CONTEXT, core.fit),
        focus=Country(iso3="KHM"),
        ground=Ground(
            scope=Scope(kind="box", name=ix.place(w.lang), text=w("inv.scope.fire", **facts), limit=w("inv.scope.limit.fire")),
            context=[CONTEXT],
            limits=[w(f"inv.limit.fire.{id}", **facts) for id in
                    ("direction", "hotspots", "drift", "both", "provinces", "archive")],
        ),
    )


def _at(year: int, month: int) -> float:
    """A month on a line's x axis: the year plus the middle of the month."""
    return year + round((month - 0.5) / 12, 3)


def _province_fits(f: series.Fires, chosen: tuple[str, ...], seasons: list[int], provinces: list[str]) -> dict[str, Fit]:
    """The trend of each province with enough seasons, detections and distinct counts to test."""
    out = {}
    for p in provinces:
        counts = [sum(f.provinces[sat].get(p, {}).get(s, 0) for sat in chosen) for s in seasons]
        if len(seasons) >= T.reliable and sum(counts) >= T.fire_min_total and len(set(counts)) >= T.fire_min_distinct:
            out[p] = stats.trend_test(seasons, counts, rel=True)
    return out


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
