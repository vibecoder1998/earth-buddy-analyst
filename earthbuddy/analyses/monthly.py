"""What the haze and water panels share: one monthly Giovanni series read by part of the year and by calendar month.
Not a kind."""
import statistics

from .. import series, stats
from ..stats import fmt, fmt_level, fmt_p
from ..types import Fact, Intervals, Line, Span, TooShort
from ..words import Words
from .base import per_decade

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


def monthly_line(values: list[Month], unit: str, title: str) -> Line:
    return Line(title=title, x=[y + round((mo - 0.5) / 12, 3) for y, mo, _ in values], y=[x for _, _, x in values], unit=unit)


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
