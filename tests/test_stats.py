import math

import numpy as np
import pymannkendall
import pytest
from scipy.stats import linregress, theilslopes

from earthbuddy import stats
from earthbuddy.stats import T
from earthbuddy.types import TooShort

YEARS = list(range(2001, 2025))


def ar1(rng: np.random.Generator, phi: float, runs: int, trend: float = 0.0, n: int = 24) -> np.ndarray:
    x = rng.standard_normal(runs) / math.sqrt(1 - phi * phi)
    out = np.empty((runs, n))
    for t in range(n):
        x = phi * x + rng.standard_normal(runs)
        out[:, t] = x + trend * t
    return out


def false_positive_rate(series: np.ndarray, field: str = "p") -> float:
    return float(np.mean([getattr(stats.trend_test(YEARS, list(y)), field) < T.alpha for y in series]))


def test_sen_recovers_known_slope():
    fit = stats.trend_test(YEARS, [5 + 0.3 * (y - 2001) for y in YEARS])
    assert fit.slope_per_decade == pytest.approx(3.0)
    assert fit.lo_per_decade == pytest.approx(3.0) and fit.hi_per_decade == pytest.approx(3.0)
    assert stats.sen_at(fit, 2011) == pytest.approx(8.0)
    assert fit.total_change == pytest.approx(0.3 * 23)
    assert (fit.direction, fit.level, fit.n) == ("rising", "clear", 24)


def test_agrees_with_pymannkendall_and_scipy():
    rng = np.random.default_rng(20)
    for k in range(20):
        y = rng.standard_normal(24) + 0.05 * k * np.arange(24)
        fit, mk = stats.trend_test(YEARS, list(y)), pymannkendall.original_test(y)
        sen = theilslopes(y, YEARS, T.ci)
        assert fit.slope_per_decade == pytest.approx(sen.slope * 10)
        assert fit.lo_per_decade <= sen.low_slope * 10 and fit.hi_per_decade >= sen.high_slope * 10
        assert fit.tau == pytest.approx(mk.Tau)
        assert np.sign(fit.z) == np.sign(mk.z)
        assert fit.p >= mk.p - 1e-12, "the memory correction only widens"
        if fit.test == "mann-kendall":
            assert fit.p == pytest.approx(mk.p)
            assert (fit.lo_per_decade, fit.hi_per_decade) == pytest.approx((sen.low_slope * 10, sen.high_slope * 10))
        assert fit.t_p >= linregress(YEARS, y).pvalue - 1e-12, "the memory correction only widens"


def test_ar1_false_positive_at_most_0_08(capsys):
    rng = np.random.default_rng(4)
    rates = {phi: false_positive_rate(ar1(rng, phi, 2000)) for phi in (0, 0.3, 0.5)}
    with capsys.disabled():
        print(f"\nAR(1) n=24, 2000 runs, p < {T.alpha}: " + ", ".join(f"phi {k} -> {v:.3f}" for k, v in rates.items()))
    assert all(r <= 0.08 for r in rates.values()), rates


def test_ar1_slope_t_test_false_positive_at_most_0_08(capsys):
    rng = np.random.default_rng(4)
    rates = {phi: false_positive_rate(ar1(rng, phi, 2000), "t_p") for phi in (0, 0.3, 0.5)}
    with capsys.disabled():
        print(f"\nt-test AR(1) n=24, 2000 runs, t_p < {T.alpha}: " + ", ".join(f"phi {k} -> {v:.3f}" for k, v in rates.items()))
    assert all(r <= 0.08 for r in rates.values()), rates


def excludes_zero(fit) -> bool:
    return fit.lo_per_decade > 0 or fit.hi_per_decade < 0


def test_ar1_interval_excludes_zero_no_more_than_p(capsys):
    rng = np.random.default_rng(4)
    for phi in (0.3, 0.5):
        fits = [stats.trend_test(YEARS, list(y)) for y in ar1(rng, phi, 2000)]
        excl = float(np.mean([excludes_zero(f) for f in fits]))
        clear = float(np.mean([f.p < T.alpha for f in fits]))
        with capsys.disabled():
            print(f"\ninterval AR(1) phi {phi} n=24, 2000 runs: excludes 0 {excl:.3f}, p < {T.alpha} {clear:.3f}")
        assert excl <= clear + 0.005 and excl <= 0.08, (phi, excl, clear)


def test_interval_agrees_with_p(capsys):
    rng = np.random.default_rng(8)
    agree = []
    for _ in range(1000):
        y = ar1(rng, rng.uniform(0, 0.6), 1, trend=rng.uniform(0, 0.15))[0]
        fit = stats.trend_test(YEARS, list(y))
        agree.append(excludes_zero(fit) == (fit.p < T.alpha))
    rate = float(np.mean(agree))
    with capsys.disabled():
        print(f"\ninterval excludes 0 == p < {T.alpha}: {rate:.3f} of 1000 series")
    assert rate >= 0.95


def test_white_noise_at_most_7_percent(capsys):
    rate = false_positive_rate(np.random.default_rng(7).standard_normal((2000, 24)))
    with capsys.disabled():
        print(f"\nwhite noise n=24, 2000 runs: {rate:.3f}")
    assert rate <= 0.07


def test_bh_worked_example():
    assert stats.bh([0.01, 0.04, 0.03, 0.005]) == pytest.approx([0.02, 0.04, 0.04, 0.02])
    q = stats.bh([math.nan, 0.2, 0.9])
    assert math.isnan(q[0]) and q[1:] == pytest.approx([0.4, 0.9])


def test_claim_verdict_all_six_keys():
    def key(*tests):
        return stats.claim_verdict(list(tests)).verdict.key

    assert key(("supported", 0.001), ("supported", 0.01)) == "claim.supported"
    assert key(("opposed", 0.001)) == "claim.opposed"
    assert key(("supported", 0.001), ("opposed", 0.002)) == "claim.mixed"
    assert key(("step", 0.001), ("unsupported", 0.4)) == "claim.step"
    assert key(("unsupported", 0.3)) == "claim.unsupported"
    assert key(("insufficient", math.nan)) == "claim.nothing"
    many = stats.claim_verdict([("supported", 0.04)] + [("unsupported", 0.3 + i / 20) for i in range(7)])
    assert (many.verdict.key, many.survives[0], many.final[0]) == ("claim.unsupported", False, "unsupported")
    mixed = stats.claim_verdict([("supported", 0.001), ("opposed", 0.002), ("insufficient", math.nan)])
    assert (mixed.verdict.level, mixed.survives) == ("likely", [True, True, False])


def test_step_rate_measured(capsys):
    series = ar1(np.random.default_rng(11), 0.3, 1000, trend=3 / 23)
    outcomes = [stats.test_claim(stats.trend_test(YEARS, list(y)), "up", YEARS, list(y)) for y in series]
    real = [o for o in outcomes if o in ("supported", "step")]
    rate = real.count("step") / len(real)
    with capsys.disabled():
        print(f"\nstep on steady AR(1) trends: {rate:.3f} of {len(real)} real trends")
    assert rate == pytest.approx(T.step_false_fire, abs=0.02)


def test_vif_table_matches_a_fresh_simulation():
    rng, n = np.random.default_rng(77), 24
    i, j = np.triu_indices(n, 1)
    white = n * (n - 1) * (2 * n + 5) / 18
    for phi, factor in T.vif_table[3::3]:
        y = ar1(rng, phi, 6000)
        s = np.sign(y[:, j] - y[:, i]).sum(axis=1)
        assert np.mean(s ** 2) / white / factor == pytest.approx(1, abs=0.08), phi


def test_fmt_minus_sign():
    assert stats.fmt(-0.01234) == "−" + "0.012"
    assert [stats.fmt(x) for x in (1234.5, 0.000012, 0)] == ["1200", "0.00001", "0"]
    assert (stats.fmt_p(0.0004), stats.fmt_p(0.6789)) == ("< 0.001", "0.679")


def test_short_and_constant_series():
    with pytest.raises(TooShort) as e:
        stats.trend_test(YEARS[:7], [1.0, 2, 3, 4, 5, 6, 7])
    assert e.value.field == "window"
    assert stats.trend_test(YEARS[:9], list(range(9))).level == "too_short"
    flat = stats.trend_test(YEARS, [2.0] * 24)
    assert (flat.p, flat.t_p, flat.constant, flat.level) == (1, 1, True, "unclear")
    assert stats.test_claim(flat, "up", YEARS, [2.0] * 24) == "insufficient"


def test_pettitt_finds_a_jump():
    y = list(np.random.default_rng(0).standard_normal(24) + 3 * (np.array(YEARS) >= 2012))
    cp, p = stats.pettitt(YEARS, y)
    assert cp in (2012, 2013) and p < T.pettitt_p
    assert stats.is_step(YEARS, y, cp)


def test_number_tokens_match_fmt():
    from earthbuddy.words import number_tokens
    assert number_tokens(f"fell {stats.fmt(-0.01234)} from 2010-2020, 1,5 or 0.20; ២០២៤") == \
        {"-0.012", "2010", "2020", "1.5", "0.2", "2024"}
