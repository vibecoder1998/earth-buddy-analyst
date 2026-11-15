"""What the haze and water panels share: one monthly Giovanni series read by part of the year and by calendar month.
Not a kind."""
import functools
import statistics
from typing import NamedTuple

from .. import catalog, series, stats
from ..stats import T, fmt, fmt_level, fmt_p
from ..types import Fact, Fit, Intervals, Lang, Line, Source, Span, TooShort
from ..words import Words
from .base import card, per_decade

PARTS = {"year": list(range(1, 13)), "dry": [11, 12, 1, 2, 3, 4], "wet": [5, 6, 7, 8, 9, 10]}

Month = tuple[int, int, float]


def by_part(m: series.Monthly, span: Span, lead: str, w: Words) -> tuple[Intervals, dict[str, Fact], list[str]]:
    """Whole year, dry season and wet season through trend_test, over the years of `span`.
    (chart, facts, a note when the parts reach different levels). `lead` is the part the panel's headline tests."""
    fits = {}
    for part, months in PARTS.items():
        try:
            fits[part] = stats.trend_test(*series.season_means(m.values, months, span), rel=m.info.rel)
        except TooShort:
            pass
    shown = {p: per_decade(f, m.info) for p, f in fits.items()}
    unit = shown[lead][3]

    def amount(x: float) -> str:
        return w("word.percent", n=fmt(x)) if unit == "%" else w("word.amount", n=fmt(x), unit=unit)

    judged = [f.level for f in fits.values() if f.level != "too_short"]   # a part too short to judge neither agrees nor not
    agree = judged.count(fits[lead].level)
    facts: dict[str, Fact] = {"parts_agree": agree, "parts_tested": len(judged)} | {
        f"{p}_change": w("word.season_change", change=amount(shown[p][0]), p=fmt_p(f.p), level=w(f"word.level.{f.level}"))
        for p, f in fits.items()}
    notes = [w("note.parts", **facts)] if 0 < agree < len(judged) else []
    chart = Intervals(title=w("word.by_part"), unit=w("word.per_decade", unit=unit),
                      rows=[(w(f"word.season.{p}"), *shown[p][:3], p == lead) for p in fits])
    return chart, facts, notes


def box(m: series.Monthly, w: Words) -> str:
    south, west, north, east = m.box
    return w("word.fire.box", south=f"{south:g}", west=f"{west:g}", north=f"{north:g}", east=f"{east:g}")


def rows(ids: list[str], facts: dict[str, Fact], w: Words) -> list[tuple[str, str]]:
    """PanelDetail.rows from the word.panel.row.* and word.panel.value.* templates."""
    return [(w(f"word.panel.row.{i}", **facts), w(f"word.panel.value.{i}", **facts)) for i in ids]


def at(year: int, month: int) -> float:
    """A month on a line's x axis: the year plus the middle of the month."""
    return year + round((month - 0.5) / 12, 3)


def monthly_line(values: list[Month], unit: str, title: str, w: Words, **more) -> Line:
    """Every month as a line, with the dry seasons shaded."""
    runs: list[list[float]] = []
    for i, (y, mo, _) in enumerate(values):
        if mo in PARTS["dry"]:
            if i and values[i - 1][1] in PARTS["dry"] and runs:
                runs[-1][1] = at(y, mo)
            else:
                runs.append([at(y, mo), at(y, mo)])
    return Line(title=title, x=[at(y, mo) for y, mo, _ in values], y=[x for _, _, x in values], unit=unit,
                spans=[(a, b) for a, b in runs], span_label=w("word.span_dry"), **more)


def levels(values: list[Month], unit: str, w: Words) -> dict[str, Fact]:
    """The average of the months given, the highest and lowest calendar month, and the dry and wet season averages."""
    mean = {mo: statistics.fmean(x for _, m, x in values if m == mo) for mo in sorted({m for _, m, _ in values})}
    peak, low = max(mean, key=mean.get), min(mean, key=mean.get)

    def level(xs) -> str:
        return w("word.amount", n=fmt_level(statistics.fmean(xs)), unit=unit).strip()

    return {"mean": level(x for *_, x in values), "months": len(values),
            "peak_month": w(f"month.{peak}"), "peak": level([mean[peak]]), "low_month": w(f"month.{low}"), "low": level([mean[low]]),
            "ratio": fmt(mean[peak] / mean[low]) if mean[low] > 0 else None,
            "dry": level(x for _, m, x in values if m in PARTS["dry"]), "wet": level(x for _, m, x in values if m in PARTS["wet"])}


class Whole(NamedTuple):
    """One series over every year on file: fixed, whatever the controls say."""
    info: catalog.MeasureInfo
    years: list[int]
    values: list[float | None]
    fit: Fit
    step_after: int        # the last year before the most likely jump
    step_p: float
    plain: float           # the plain Mann-Kendall p-value, the one the branch counts series by
    card: dict[str, Fact]


def whole_record(id: str, w: Words) -> Whole:
    return _whole(id, w.lang)


@functools.cache
def _whole(id: str, lang: Lang) -> Whole:
    m, w = series.monthly(id), Words(lang)
    years, values = series.season_means(m.values, PARTS["year"], (m.values[0][0], m.values[-1][0]))
    fit = stats.trend_test(years, values, rel=m.info.rel)
    jump, jump_p = stats.pettitt(years, values)
    facts = card(fit, years, values, m.info.unit, m.info.rel, w, m.values) | {"first": years[0], "last": years[-1],
                                                                             "name": m.info.label(w.lang)}
    return Whole(m.info, years, values, fit, jump - 1, jump_p, stats.second_opinions(values).plain, facts)


def steps(w: Words) -> dict[str, Fact]:
    """How many of the model series on file jump over their whole record, and when, beside the satellite record's own check."""
    wholes = [whole_record(id, w) for id in catalog.measures()]
    model = [x for x in wholes if x.info.made.kind == "model"]
    jumps = [x.step_after for x in model if x.step_p < T.pettitt_p]
    seen = next(x for x in wholes if x.info.made.kind == "satellite")
    return {"model_series": len(model), "model_steps": len(jumps),
            "steps_first": min(jumps, default=None), "steps_last": max(jumps, default=None),
            "satellite_name": seen.card["name"], "satellite_step_p": seen.card["step_p"], "satellite_plain": seen.card["plain"]}


def cited(*lists: list[Source]) -> list[Source]:
    """The sources of the series chosen, then of every other Giovanni series the fixed rows read. Each once."""
    every = [s for sources in lists for s in sources] + [s for id in catalog.measures() for s in series.monthly(id).sources]
    return list({s.id: s for s in every}.values())


def measured(ids: list[str], w: Words) -> list[tuple[str, str]]:
    """The "what is measured, and with what" rows, one per series."""
    out = []
    for id in ids:
        info = catalog.measure(id)[0]
        out.append((w("word.measured.row", name=info.label(w.lang), unit=info.unit),
                    w("word.measured.value", kind=w(f"word.measured.kind.{info.made.kind}"), what=info.made.what(w.lang),
                      product=info.made.product, grid=info.made.grid)))
    return out


def files(ids: list[str], w: Words) -> list[tuple[str, str]]:
    """What reading each file found: the branch's raw-file audit, counted on this read."""
    out = []
    for id in ids:
        m = series.monthly(id)
        xs = [x for *_, x in m.values]
        text = w("word.file.value", **m.audit._asdict(), first=f"{m.values[0][0]}-{m.values[0][1]:02d}",
                 last=f"{m.values[-1][0]}-{m.values[-1][1]:02d}", lo=fmt_level(min(xs)), hi=fmt_level(max(xs)),
                 mean=fmt_level(statistics.fmean(xs)), unit=m.info.unit)
        if m.info.factor != 1:
            text += " " + w("word.file.scaled", lo=f"{min(xs) / m.info.factor:.4g}", hi=f"{max(xs) / m.info.factor:.4g}",
                            factor=f"{m.info.factor:g}")
        out.append((w("word.file.row", name=m.info.label(w.lang)), text))
    return out


def typical_year(values: list[Month], unit: str, w: Words) -> tuple[Intervals, dict[str, Fact]]:
    """Twelve rows, January first: the mean of each calendar month, with its lowest and highest year. The peak is marked."""
    by_month = {mo: [x for _, m, x in values if m == mo] for mo in range(1, 13)}
    mean = {mo: statistics.fmean(xs) for mo, xs in by_month.items()}
    peak, low = max(mean, key=mean.get), min(mean, key=mean.get)

    def level(x: float) -> str:
        return w("word.amount", n=fmt_level(x), unit=unit).strip()

    facts: dict[str, Fact] = {"peak_month": w(f"month.{peak}"), "peak_level": level(mean[peak]),
                              "low_month": w(f"month.{low}"), "low_level": level(mean[low])}
    chart = Intervals(title=w("word.typical_year", first=values[0][0], last=values[-1][0]), unit=unit,
                      rows=[(w(f"month.{mo}"), mean[mo], min(xs), max(xs), mo == peak) for mo, xs in by_month.items()])
    return chart, facts
