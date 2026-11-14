"""Small, readable implementations of the trend tests we use.

Written from the textbook formulas (no hidden library calls) so the team can
explain every step to the judges.  check_against_libraries.py compares these
against scipy and pymannkendall.
"""
import numpy as np
from scipy import stats


def mann_kendall(x):
    """Mann-Kendall trend test (two-sided), with tie correction.

    S = number of (later > earlier) pairs minus number of (later < earlier) pairs.
    Z = standardised S (with continuity correction), p from the normal curve.
    tau = S / number_of_pairs, between -1 (always falling) and +1 (always rising).
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    s = 0.0
    for i in range(n - 1):
        s += np.sign(x[i + 1:] - x[i]).sum()
    # tied values make some pairs undecidable, which lowers the variance of S (the standard tie correction)
    _, counts = np.unique(x, return_counts=True)
    tie_term = sum(t * (t - 1) * (2 * t + 5) for t in counts if t > 1)
    var_s = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0
    # continuity correction: move S one step towards zero before dividing by its standard deviation
    if s > 0:
        z = (s - 1) / np.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / np.sqrt(var_s)
    else:
        z = 0.0
    p = 2.0 * stats.norm.sf(abs(z))
    tau = s / (n * (n - 1) / 2.0)
    return {"s": s, "var_s": var_s, "z": z, "p": p, "tau": tau, "n": n}


def sens_slope(x, t=None):
    """Theil-Sen slope: the MEDIAN of all pairwise slopes (robust to outliers)."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    t = np.arange(n, dtype=float) if t is None else np.asarray(t, dtype=float)
    # every pair (i < j) gives one slope; the Sen slope is their median
    slopes = [(x[j] - x[i]) / (t[j] - t[i]) for i in range(n - 1) for j in range(i + 1, n)]
    b = float(np.median(slopes))
    intercept = float(np.median(x - b * t))
    return b, intercept


def lag1_autocorr(x):
    """Lag-1 autocorrelation r1: how much this year 'remembers' last year (-1..+1)."""
    x = np.asarray(x, dtype=float)
    m = x.mean()
    denom = ((x - m) ** 2).sum()
    if denom == 0:
        return 0.0
    return float(((x[:-1] - m) * (x[1:] - m)).sum() / denom)


def ar1_is_significant(r1, n):
    """Rough 95% test: |r1| larger than 1.96/sqrt(n) is more than chance."""
    return abs(r1) > 1.96 / np.sqrt(n)


def tfpw_mann_kendall(x):
    """Mann-Kendall after Trend-Free Pre-Whitening (Yue et al. 2002).

    1) estimate the trend b (Sen slope) and remove it
    2) estimate the AR(1) memory r1 of what is left and remove it
    3) put the trend back, then run ordinary Mann-Kendall
    Used because positive year-to-year memory makes plain Mann-Kendall
    over-confident (p-values too small).
    Returns (mk_result_dict, r1, slope).
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    t = np.arange(n, dtype=float)
    b, _ = sens_slope(x)
    detrended = x - b * t
    r1 = lag1_autocorr(detrended)
    resid = detrended[1:] - r1 * detrended[:-1]
    y = resid + b * t[1:]
    return mann_kendall(y), r1, b


def pettitt(x):
    """Pettitt change-point test.

    Finds the single split after which the series 'jumps' to a new level.
    Returns index of the last point BEFORE the jump, the statistic K and p.
    p uses Pettitt's approximation 2*exp(-6K^2/(n^3+n^2)).
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    sgn = np.sign(x[:, None] - x[None, :])
    u = np.array([sgn[: t + 1, t + 1:].sum() for t in range(n - 1)])
    k = np.abs(u).max()
    t_star = int(np.abs(u).argmax())
    p = min(1.0, 2.0 * np.exp(-6.0 * k ** 2 / (n ** 3 + n ** 2)))
    return {"index": t_star, "k": float(k), "p": float(p)}


def ols_trend(x):
    """Ordinary least-squares line (the 'school' regression) for comparison."""
    x = np.asarray(x, dtype=float)
    res = stats.linregress(np.arange(len(x)), x)
    return float(res.slope), float(res.pvalue)
