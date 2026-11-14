"""Every statistical function and constant. No I/O. Nothing else computes a p-value, a slope, or a verdict."""
from typing import Literal, NamedTuple

from .types import Decomposition, Direction, Fit, Outcome, SeasonalCycle, TooShort, Verdict


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
    z95 = 1.96            # Hamed-Rao switch: |lag1| > z95 / sqrt(n)
    swing_mad = 1.4826    # MAD -> standard deviation
    size_large = 10       # years to move one swing: under this "large"
    size_small = 30       # at or above this "small"
    size_cap = 200        # above this the text says "more than 200"
    coin_floor = 0.75     # heads below this: "not surprising at all"
    coin_cap = 10
    stl_min_months = 36
    cycle_years = 10      # early/late seasonal cycle span
    # P1/P2 rows add theirs here: where box, baseline minimums, extremes words, relate bands, ...


class Scored(NamedTuple):
    verdict: Verdict
    survives: list[bool]       # q < T.fdr_q, per test
    final: list[Outcome]       # a non-surviving supported/opposed/step becomes unsupported


def fmt(x: float) -> str:
    """About 2 significant figures, at most 4 decimals, U+2212 minus. fmt(-0.01234) == "−0.012"."""
    raise NotImplementedError


def fmt_p(p: float) -> str:
    """"< 0.001" or 3 decimals."""
    raise NotImplementedError


def trend_test(years: list[int], values: list[float | None], *, rel: bool = False) -> Fit:
    # TODO row 4 (docs/03):
    # 1 drop None; n < T.min_years -> raise TooShort(n)
    # 2 scipy.stats.theilslopes(y, x, T.ci); constant series -> p=1, constant=True, level "unclear"
    # 3 pymannkendall.original_test; hamed_rao_modification_test when n >= T.reliable and |lag1| > T.z95/sqrt(n);
    #   non-finite -> original -> p = 1
    # 4 level: too_short if n < T.reliable else clear (p < T.alpha) / likely (p < T.likely) / unclear
    # 5 direction from the slope sign; percent_change only when rel
    raise NotImplementedError


def pettitt(years: list[int], values: list[float | None]) -> tuple[int, float]:
    """(first year of the new regime, p). p = min(1, 2·exp(−6K² / (n³ + n²)))."""
    raise NotImplementedError


def is_step(years: list[int], values: list[float | None], cp: int) -> bool:
    """Two-level fit SSE < T.step_ratio × Sen-line SSE."""
    raise NotImplementedError


def bh(ps: list[float]) -> list[float]:
    """Benjamini-Hochberg q-values: step-up, monotone, capped at 1, NaN kept as NaN."""
    raise NotImplementedError


def test_claim(fit: Fit | None, direction: Direction, years: list[int], values: list[float | None]) -> Outcome:
    raise NotImplementedError


test_claim.__test__ = False   # keep pytest from collecting it


def claim_verdict(tests: list[tuple[Outcome, float]]) -> Scored:
    """bh over live tests; demote non-survivors; key by docs/03 order.
    Level: supported/opposed/step -> clear, mixed -> likely, unsupported -> unclear, nothing -> too_short."""
    raise NotImplementedError


def sen_at(fit: Fit, year: float) -> float:
    """The Sen line at a year (charts, extremes)."""
    raise NotImplementedError


def size(fit: Fit) -> tuple[Literal["small", "moderate", "large", "none"], float]:
    raise NotImplementedError


def coin(p: float) -> tuple[Literal["clearly", "probably", "cant_tell"], int | None]:
    """(word, heads in a row capped at T.coin_cap, or None when not surprising)."""
    raise NotImplementedError


def stl(monthly: list[tuple[int, int, float]]) -> Decomposition | None:
    """STL(period=12, robust=True) after interpolating gaps. None under T.stl_min_months.
    Imports statsmodels lazily, so a deploy without it only loses the decomposition."""
    raise NotImplementedError


def seasonal_cycle(monthly: list[tuple[int, int, float]]) -> SeasonalCycle:
    raise NotImplementedError
