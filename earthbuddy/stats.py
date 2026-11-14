"""Every statistical function and constant. No I/O. Nothing else computes a p-value, a slope, or a verdict."""
import calendar
import math
import statistics
from typing import Literal, NamedTuple

import numpy as np
import pymannkendall
from scipy import stats as sp

from .types import Decomposition, Direction, Fit, Level, Outcome, SeasonalCycle, TooShort, Verdict


class T:
    """Every statistical threshold. No other file repeats one of these numbers (a test greps for it)."""
    alpha = 0.05          # "clear"
    likely = 0.10         # "likely, but not certain"
    fdr_q = 0.10          # Benjamini-Hochberg false discovery rate
    min_years = 8         # below this: refuse to compute
    reliable = 10         # below this: compute, but the level is "too_short"
    step_ratio = 0.8      # two-level SSE / Sen-line SSE below this = "one jump"
    pettitt_p = 0.05
    ci = 0.95             # Sen slope interval
    vif_a = 3
    vif_b = 6
    vif_cap = 0.9
    neff_floor = 4        # effective sample size floor for the slope t-test
    vif_table = [[0, 1], [.1, 1.183], [.2, 1.383], [.3, 1.683], [.4, 2.021], [.5, 2.482], [.6, 3.12], [.7, 4],
                 [.8, 5.386], [.9, 7.712]]
    step_false_fire = 0.16
    swing_mad = 1.4826    # MAD -> standard deviation
    size_large = 10       # years to move one swing: under this "large"
    size_small = 30       # at or above this "small"
    size_cap = 200        # above this the text says "more than 200"
    coin_floor = 0.75     # heads below this: "not surprising at all"
    coin_cap = 10
    fmt_decimals = 4
    p_floor = 0.001
    stl_min_months = 36
    cycle_years = 10      # early/late seasonal cycle span
    where_box = 4.0       # degrees a side
    where_snap = 0.5      # degrees; the box centre snaps to this grid
    where_centre = 0.6    # degrees; the strongest cell this close reads "close to the centre"
    rank_level_years = 10 # rank by level: the mean of the last this many years
    baseline_gap = 2      # a baseline ends at least this many years before the last complete year
    recent_min = 3        # years the recent period needs
    se_floor = 1e-12      # slope standard error floor in the pace test
    extremes_listed = 3   # highest and lowest years shown
    unusual = 1           # typical swings from the trend line: under this "ordinary"
    exceptional = 2       # at or above this "exceptional"; between the two "unusual"
    cluster_k_min = 3     # record clustering: top_k = max(min, min(max, n // 4))
    cluster_k_max = 10
    cluster_window = 10   # recent years checked: min(this, n // 2)
    season_concentration = 0.15   # under this the year has no rainy season to time
    rho_weak = 0.2        # |Spearman rho| under this: "no" link
    rho_moderate = 0.4    # under this "weak"
    rho_strong = 0.6      # under this "moderate", else "strong"
    short_record = 20     # relate: fewer shared years than this is a short record


class Scored(NamedTuple):
    verdict: Verdict
    survives: list[bool]       # q < T.fdr_q, per test
    final: list[Outcome]       # a non-surviving supported/opposed/step becomes unsupported


def fmt(x: float) -> str:
    """About 2 significant figures, at most 4 decimals, U+2212 minus. fmt(-0.01234) == "−0.012".
    A nonzero number that 4 decimals would round to 0 keeps 1 significant figure instead."""
    if not math.isfinite(x):
        return "n/a"
    if x == 0:
        return "0"
    mag = math.floor(math.log10(abs(x)))
    d = min(1 - mag, T.fmt_decimals)
    if round(x, d) == 0:
        d = -mag
    s = f"{round(x, d):.{max(d, 0)}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace("-", "−")


def fmt_p(p: float) -> str:
    """"< 0.001" or 3 decimals."""
    return f"< {T.p_floor}" if p < T.p_floor else f"{p:.3f}"


def _clean(years: list[int], values: list[float | None]) -> tuple[np.ndarray, np.ndarray]:
    keep = [(x, v) for x, v in zip(years, values) if v is not None and math.isfinite(v)]
    x, y = (np.array(c, dtype=float) for c in zip(*keep)) if keep else (np.array([]), np.array([]))
    return x, y


def _lag1(r: np.ndarray) -> float:
    d = r - r.mean()
    den = float(d @ d)
    return float(d[1:] @ d[:-1]) / den if den else 0.0


def _sen_line(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    slope = sp.theilslopes(y, x).slope
    mid = (x[0] + x[-1]) / 2
    return float(slope), float(np.median(y - slope * (x - mid)))


def _sen_interval(x: np.ndarray, y: np.ndarray, var_s: float, vif: float) -> tuple[float, float]:
    i, j = np.triu_indices(len(y), 1)
    slopes = np.sort((y[j] - y[i]) / (x[j] - x[i]))
    c = sp.norm.ppf((1 + T.ci) / 2) * math.sqrt(var_s * vif)
    lo = max(round((len(slopes) - c) / 2) - 1, 0)
    hi = min(round((len(slopes) + c) / 2), len(slopes) - 1)
    return float(slopes[lo]), float(slopes[hi])


def _slope_t_p(x: np.ndarray, y: np.ndarray, phi: float) -> float:
    """OLS slope t-test from linregress, with n shrunk to n·(1 − φ)/(1 + φ) for year-to-year memory."""
    n = len(y)
    fit = sp.linregress(x, y)
    n_eff = min(n, max(T.neff_floor, n * (1 - phi) / (1 + phi)))
    t = math.inf if fit.stderr == 0 else abs(fit.slope) / fit.stderr * math.sqrt((n_eff - 2) / (n - 2))
    return float(2 * sp.t.sf(t, n_eff - 2))


def level_of(p: float, n: int) -> Level:
    return "too_short" if n < T.reliable else "clear" if p < T.alpha else "likely" if p < T.likely else "unclear"


def trend_test(years: list[int], values: list[float | None], *, rel: bool = False) -> Fit:
    x, y = _clean(years, values)
    n = len(y)
    if n < T.min_years:
        raise TooShort(n)
    slope, at_mid = _sen_line(x, y)
    mid = (x[0] + x[-1]) / 2
    res = y - (at_mid + slope * (x - mid))
    mad = float(np.median(np.abs(res - np.median(res))))
    swing = mad * T.swing_mad if mad else float(np.std(res, ddof=1))
    mean = float(y.mean())
    constant = bool(np.all(y == y[0]))
    lag1 = _lag1(res)
    if constant:
        p, z, tau, test, level, t_p, lo, hi = 1.0, 0.0, 0.0, "mann-kendall", "unclear", 1.0, slope, slope
    else:
        mk = pymannkendall.original_test(y)
        phi = min(max(lag1 + (T.vif_a + T.vif_b * lag1) / n, 0.0), T.vif_cap)
        t_p = _slope_t_p(x, y, phi)
        phis, factors = zip(*T.vif_table)
        vif = float(np.interp(phi, phis, factors))
        lo, hi = _sen_interval(x, y, mk.var_s, vif)
        z = float(mk.z) / math.sqrt(vif)
        p = float(2 * sp.norm.sf(abs(z)))
        tau = float(mk.Tau)
        test = "mann-kendall-vif" if vif > 1 else "mann-kendall"
        level = level_of(p, n)
    total = slope * (x[-1] - x[0])
    return Fit(
        n=n, first_year=int(x[0]), last_year=int(x[-1]),
        slope_per_decade=slope * 10, lo_per_decade=lo * 10, hi_per_decade=hi * 10,
        intercept=at_mid, mean=mean, swing=swing, total_change=total,
        percent_change=total / mean * 100 if rel and mean > 0 else None,
        p=p, z=z, tau=tau, test=test, t_p=t_p, lag1=lag1, constant=constant,
        direction="flat" if slope == 0 else "rising" if slope > 0 else "falling",
        level=level,
    )


def pettitt(years: list[int], values: list[float | None]) -> tuple[int, float]:
    """(first year of the new regime, p). p = min(1, 2·exp(−6K² / (n³ + n²)))."""
    x, y = _clean(years, values)
    n = len(y)
    u = np.cumsum(np.sign(y[:, None] - y[None, :]).sum(axis=1))[:-1]
    i = int(np.argmax(np.abs(u)))
    k = float(abs(u[i]))
    return int(x[i + 1]), min(1.0, 2 * math.exp(-6 * k * k / (n ** 3 + n ** 2)))


def is_step(years: list[int], values: list[float | None], cp: int) -> bool:
    """Two-level fit SSE < T.step_ratio × Sen-line SSE."""
    x, y = _clean(years, values)
    before, after = y[x < cp], y[x >= cp]
    if not len(before) or not len(after):
        return False
    two = float(((before - before.mean()) ** 2).sum() + ((after - after.mean()) ** 2).sum())
    slope, at_mid = _sen_line(x, y)
    line = float(((y - at_mid - slope * (x - (x[0] + x[-1]) / 2)) ** 2).sum())
    return two < T.step_ratio * line


def bh(ps: list[float]) -> list[float]:
    """Benjamini-Hochberg q-values: step-up, monotone, capped at 1, NaN kept as NaN."""
    p = np.asarray(ps, dtype=float)
    out = np.full(len(p), np.nan)
    live = np.flatnonzero(~np.isnan(p))
    order = live[np.argsort(p[live], kind="stable")]
    q = p[order] * len(order) / np.arange(1, len(order) + 1)
    out[order] = np.minimum(np.minimum.accumulate(q[::-1])[::-1], 1.0)
    return out.tolist()


def test_claim(fit: Fit | None, direction: Direction, years: list[int], values: list[float | None]) -> Outcome:
    if fit is None or fit.constant or fit.level == "too_short":
        return "insufficient"
    if fit.p >= T.alpha:
        return "unsupported"
    if direction != "any" and (direction == "up") != (fit.z > 0):
        return "opposed"
    cp, cp_p = pettitt(years, values)
    return "step" if cp_p < T.pettitt_p and is_step(years, values, cp) else "supported"


test_claim.__test__ = False   # keep pytest from collecting it

_CLAIM_LEVEL = {"claim.supported": "clear", "claim.opposed": "clear", "claim.step": "clear",
                "claim.mixed": "likely", "claim.unsupported": "unclear", "claim.nothing": "too_short"}


def claim_verdict(tests: list[tuple[Outcome, float]]) -> Scored:
    """bh over live tests; demote non-survivors; key by docs/03 order.
    Level: supported/opposed/step -> clear, mixed -> likely, unsupported -> unclear, nothing -> too_short."""
    live = [i for i, (o, _) in enumerate(tests) if o != "insufficient"]
    qs = bh([tests[i][1] for i in live])
    survives = [False] * len(tests)
    for i, q in zip(live, qs):
        survives[i] = q < T.fdr_q
    final: list[Outcome] = [
        "unsupported" if o in ("supported", "opposed", "step") and not s else o
        for (o, _), s in zip(tests, survives)
    ]
    got = [final[i] for i in live]
    key = ("claim.nothing" if not got else
           "claim.supported" if all(o == "supported" for o in got) else
           "claim.opposed" if all(o == "opposed" for o in got) else
           "claim.mixed" if "supported" in got and "opposed" in got else
           "claim.step" if "supported" not in got and "opposed" not in got and "step" in got else
           "claim.unsupported")
    return Scored(Verdict(key=key, level=_CLAIM_LEVEL[key]), survives, final)


def mean_interval(values: list[float]) -> tuple[float, float, float]:
    """(mean, lo, hi): Student t interval at T.ci."""
    y = np.asarray(values, dtype=float)
    half = sp.t.ppf((1 + T.ci) / 2, len(y) - 1) * y.std(ddof=1) / math.sqrt(len(y))
    m = float(y.mean())
    return m, m - half, m + half


def gap_p(years: list[int], a: list[float | None], b: list[float | None], metric: Literal["change", "level"]) -> float:
    """p that two places differ, from the year-by-year difference a − b."""
    d = [None if x is None or y is None else x - y for x, y in zip(a, b)]
    if metric == "change":
        try:
            return trend_test(years, d).p
        except TooShort:
            return 1.0
    last = [x for x in d if x is not None][-T.rank_level_years:]
    return float(sp.wilcoxon(last).pvalue) if any(last) else 1.0


def shared_cells(rows: list[list[float | None]]) -> list[set[int]]:
    """Per row, the other rows that differ from it by a constant: two names in one grid cell (docs/09)."""
    def key(row: list[float | None]) -> tuple:
        m = statistics.fmean(x for x in row if x is not None)
        return tuple(None if x is None else round(x - m, 9) for x in row)

    keys = [key(r) for r in rows]
    same: dict[tuple, set[int]] = {}
    for i, k in enumerate(keys):
        same.setdefault(k, set()).add(i)
    return [same[k] - {i} for i, k in enumerate(keys)]


def sen_at(fit: Fit, year: float) -> float:
    """The Sen line at a year (charts, extremes)."""
    return fit.intercept + fit.slope_per_decade / 10 * (year - (fit.first_year + fit.last_year) / 2)


def size(fit: Fit) -> tuple[Literal["small", "moderate", "large", "none"], float]:
    """(word, years the trend takes to move one typical swing)."""
    if fit.slope_per_decade == 0:
        return "none", math.inf
    years = fit.swing / (abs(fit.slope_per_decade) / 10)
    return ("large" if years < T.size_large else "moderate" if years < T.size_small else "small"), years


def coin(p: float) -> tuple[Literal["clearly", "probably", "cant_tell"], int | None]:
    """(word, heads in a row capped at T.coin_cap, or None when not surprising)."""
    word = "clearly" if p < T.alpha else "probably" if p < T.likely else "cant_tell"
    heads = -math.log2(p) if p > 0 else math.inf
    return word, None if heads < T.coin_floor else round(min(heads, T.coin_cap))


def _months(monthly: list[tuple[int, int, float]]) -> tuple[list[tuple[int, int]], np.ndarray]:
    got = {(y, m): v for y, m, v in monthly}
    (y0, m0), (y1, m1) = min(got), max(got)
    ym = [(k // 12, k % 12 + 1) for k in range(y0 * 12 + m0 - 1, y1 * 12 + m1)]
    return ym, np.array([got.get(k, np.nan) for k in ym], dtype=float)


def stl(monthly: list[tuple[int, int, float]]) -> Decomposition | None:
    """STL(period=12, robust=True) after interpolating gaps. None under T.stl_min_months.
    Imports statsmodels lazily, so a deploy without it only loses the decomposition."""
    if len(monthly) < T.stl_min_months:
        return None
    try:
        from statsmodels.tsa.seasonal import STL
    except ImportError:
        return None
    ym, v = _months(monthly)
    ok = np.isfinite(v)
    idx = np.arange(len(v))
    v = np.interp(idx, idx[ok], v[ok])
    r = STL(v, period=12, robust=True).fit()
    parts = {"trend": r.trend, "seasonal": r.seasonal, "residual": r.resid}
    var = {k: float(np.var(a)) for k, a in parts.items()}
    total = sum(var.values()) or 1.0
    return Decomposition(
        t=[f"{y}-{m:02d}" for y, m in ym], observed=v.tolist(),
        trend=r.trend.tolist(), seasonal=r.seasonal.tolist(), residual=r.resid.tolist(),
        variance_share={k: var[k] / total for k in var},
    )


def seasonal_cycle(monthly: list[tuple[int, int, float]]) -> SeasonalCycle:
    """Monthly means over the first and the last T.cycle_years years; peak, low, and amplitude from the late cycle."""
    years = sorted({y for y, _, _ in monthly})

    def cycle(span: set[int]) -> list[float]:
        return [float(np.nanmean([v for y, m, v in monthly if m == k and y in span] or [np.nan]))
                for k in range(1, 13)]

    early, late = cycle(set(years[:T.cycle_years])), cycle(set(years[-T.cycle_years:]))
    arr = np.array(late)
    return SeasonalCycle(months=list(range(1, 13)), early=early, late=late,
                         peak_month=int(np.nanargmax(arr)) + 1, low_month=int(np.nanargmin(arr)) + 1,
                         amplitude=float(np.nanmax(arr) - np.nanmin(arr)))


def level_gap_p(a: list[float], b: list[float]) -> float:
    """Two-sided Mann-Whitney U p that two periods differ in level (docs/08). Identical periods give 1."""
    p = float(sp.mannwhitneyu(a, b, alternative="two-sided").pvalue)
    return p if math.isfinite(p) else 1.0


def slope_gap(recent: Fit, base: Fit) -> tuple[float, float, float]:
    """(difference per decade, z, p) of two Sen slopes, a normal approximation from their intervals (docs/08)."""
    z_ci = sp.norm.ppf((1 + T.ci) / 2)

    def se(f: Fit) -> float:
        return max((f.hi_per_decade - f.lo_per_decade) / (2 * z_ci), T.se_floor)

    d = recent.slope_per_decade - base.slope_per_decade
    z = d / math.hypot(se(recent), se(base))
    return d, z, float(2 * sp.norm.sf(abs(z)))


def times_normal(fit: Fit, year: int, value: float) -> float:
    """How many typical swings a year sits from the Sen line (docs/10). Measured from the trend, not the mean."""
    return (value - sen_at(fit, year)) / fit.swing if fit.swing else 0.0


def unusual_word(times: float) -> Literal["ordinary", "unusual", "exceptional"]:
    a = abs(times)
    return "ordinary" if a < T.unusual else "unusual" if a < T.exceptional else "exceptional"


class Clustering(NamedTuple):
    top_k: int
    window: int
    high: tuple[int, float]    # (how many of the top_k highest years fall in the last `window` years, chance)
    low: tuple[int, float]


def clustering(years: list[int], values: list[float]) -> Clustering:
    """Do the most extreme years bunch in the recent past? Hypergeometric tail P(count >= observed)."""
    n = len(values)
    top_k = max(T.cluster_k_min, min(T.cluster_k_max, n // 4))
    window = min(T.cluster_window, n // 2)
    recent = set(sorted(years)[-window:])
    order = sorted(zip(values, years))

    def tail(picked: list[tuple[float, int]]) -> tuple[int, float]:
        count = sum(y in recent for _, y in picked)
        return count, float(sp.hypergeom.sf(count - 1, n, window, top_k))

    return Clustering(top_k, window, tail(order[-top_k:]), tail(order[:top_k]))


def season_centre(monthly: list[tuple[int, int, float]]) -> tuple[list[int], list[float], float, float] | None:
    """(years, centre day of each year, overall centre day, concentration): the circular mean of monthly totals
    on a 365-day circle. None when the totals are too even to have a season or fewer than T.min_years are whole."""
    days = np.array([calendar.monthrange(2001, m)[1] for m in range(1, 13)])   # a 365-day year
    angle = 2 * np.pi * (np.cumsum(days) - days / 2) / 365
    by_year: dict[int, dict[int, float]] = {}
    for y, m, x in monthly:
        by_year.setdefault(y, {})[m] = x
    whole = {y: np.array([ms[k] for k in range(1, 13)]) for y, ms in sorted(by_year.items()) if len(ms) == 12}
    total = sum(whole.values(), np.zeros(12))
    if len(whole) < T.min_years or total.sum() <= 0:
        return None
    resultant = (total * np.exp(1j * angle)).sum()
    concentration = float(abs(resultant) / total.sum())
    if concentration < T.season_concentration:
        return None
    centre = float(np.angle(resultant) * 365 / (2 * np.pi)) % 365
    years, days = [], []
    for y, w in whole.items():
        if w.sum() > 0:
            d = float(np.angle((w * np.exp(1j * angle)).sum()) * 365 / (2 * np.pi))
            years.append(y)
            days.append(centre + (d - centre + 182.5) % 365 - 182.5)
    return years, days, centre, concentration


class Relation(NamedTuple):
    rho: float                                 # Spearman rho of the residuals from each Sen line
    rho_raw: float                             # Spearman rho of the values themselves
    p: float
    n_eff: float
    share_together: float                      # years whose two residuals sit on the same side of their lines
    sensitivity: tuple[float, float, float]    # Sen slope of y residuals on x residuals, with its interval
    lead: tuple[float, float] | None           # (rho, p) of x in one year against y in the next
    residuals: tuple[np.ndarray, np.ndarray]


def strength(rho: float) -> Literal["no", "weak", "moderate", "strong"]:
    a = abs(rho)
    return "no" if a < T.rho_weak else "weak" if a < T.rho_moderate else "moderate" if a < T.rho_strong else "strong"


def _residuals(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    slope, at_mid = _sen_line(x, y)
    return y - (at_mid + slope * (x - (x[0] + x[-1]) / 2))


def _rho_p(a: np.ndarray, b: np.ndarray, n_eff: float) -> tuple[float, float]:
    """Spearman rho, and p from a t-test with n_eff − 2 degrees of freedom."""
    rho = float(sp.spearmanr(a, b).statistic)
    if abs(rho) >= 1:
        return rho, 0.0
    t = abs(rho) * math.sqrt((n_eff - 2) / (1 - rho * rho))
    return rho, float(2 * sp.t.sf(t, n_eff - 2))


def _n_eff(n: int, ra: np.ndarray, rb: np.ndarray) -> float:
    r = max(_lag1(ra) * _lag1(rb), 0.0)
    return min(n, max(T.neff_floor, n * (1 - r) / (1 + r)))


def relation(years: list[int], xs: list[float], ys: list[float]) -> Relation:
    """Detrended Spearman link between two aligned, non-constant series (docs/11), memory-corrected."""
    t, a, b = (np.asarray(v, dtype=float) for v in (years, xs, ys))
    ra, rb = _residuals(t, a), _residuals(t, b)
    n_eff = _n_eff(len(t), ra, rb)
    rho, p = _rho_p(ra, rb, n_eff)
    sens = sp.theilslopes(rb, ra, alpha=T.ci)
    lead = None
    if len(t) > T.reliable:
        nxt = {int(y): i for i, y in enumerate(t)}
        pairs = [(i, nxt[int(y) + 1]) for i, y in enumerate(t) if int(y) + 1 in nxt]
        la, lb = ra[[i for i, _ in pairs]], rb[[j for _, j in pairs]]
        lead = _rho_p(la, lb, _n_eff(len(pairs), la, lb))
    return Relation(rho=rho, rho_raw=float(sp.spearmanr(a, b).statistic), p=p, n_eff=n_eff,
                    share_together=float(np.mean(np.sign(ra) == np.sign(rb))),
                    sensitivity=(float(sens.slope), float(sens.low_slope), float(sens.high_slope)),
                    lead=lead, residuals=(ra, rb))
