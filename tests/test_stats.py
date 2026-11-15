import math

import numpy as np
import pymannkendall
import pytest
from scipy.stats import linregress, norm, theilslopes

from earthbuddy import stats
from earthbuddy.stats import T
from earthbuddy.types import TooShort

YEARS = list(range(2001, 2025))
CAIRO_ALBEDO = [0.21, 0.22, 0.21, 0.21, 0.21, 0.21, 0.21, 0.2, 0.21, 0.21, 0.21, 0.21, 0.21, 0.21, 0.21, 0.21, 0.2, 0.21,
                0.2, 0.21, 0.2, 0.21, 0.2, 0.21]
SIEM_REAP_AEROSOL = [0.4, 0.42, 0.42, 0.45, 0.48, 0.44, 0.43, 0.47, 0.44, 0.46, 0.5, 0.46, 0.47, 0.47, 0.46, 0.52, 0.43,
                     0.51, 0.46, 0.47, 0.46, 0.45, 0.47, 0.48]


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
        assert fit.p == pytest.approx(2 * norm.sf(abs(fit.z))), "Fit.p stays two-sided"
        assert stats.claim_p(fit, "any") == fit.p
        assert stats.claim_p(fit, "up" if fit.z > 0 else "down") == fit.p / 2
        assert stats.claim_p(fit, "down" if fit.z > 0 else "up") == fit.p
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


def includes_zero(fit) -> bool:
    return fit.lo_per_decade <= 0 <= fit.hi_per_decade


def test_a_slope_of_0_is_never_clear_or_likely():
    fit = stats.trend_test(YEARS, CAIRO_ALBEDO)
    assert fit.p < T.alpha and fit.slope_per_decade == 0, "the premise: ties give a small p beside a slope of 0"
    assert (fit.level, fit.direction) == ("unclear", "flat")
    assert stats.coin(fit)[0] == "cant_tell"
    assert {stats.test_claim(fit, d, YEARS, CAIRO_ALBEDO) for d in ("up", "down", "any")} == {"unsupported"}


def test_clear_needs_an_interval_that_leaves_out_0():
    fit = stats.trend_test(YEARS, SIEM_REAP_AEROSOL)
    assert fit.p < T.alpha and fit.lo_per_decade == 0, "the premise: p under alpha beside an interval that touches 0"
    assert fit.level == "likely" and stats.coin(fit)[0] == "probably"
    assert stats.test_claim(fit, "any", YEARS, SIEM_REAP_AEROSOL) == "unsupported"
    assert fit.clear_one_sided, "the one-sided interval, 5% in each tail, leaves out 0"
    assert stats.test_claim(fit, "up", YEARS, SIEM_REAP_AEROSOL) == "supported"


def test_a_named_direction_is_a_one_sided_test():
    rng = np.random.default_rng(13)
    y = next(list(y) for y in ar1(rng, 0, 4000, trend=0.06)
             if (f := stats.trend_test(YEARS, list(y))).z > 0 and T.alpha <= f.p < 2 * T.alpha and f.clear_one_sided
             and stats.test_claim(f, "up", YEARS, list(y)) == "supported")
    fit = stats.trend_test(YEARS, y)
    assert fit.level != "clear"
    assert [stats.test_claim(fit, d, YEARS, y) for d in ("up", "any", "down")] == ["supported", "unsupported", "unsupported"]
    assert stats.claim_p(fit, "up") < T.alpha <= stats.claim_p(fit, "any")


def test_level_never_contradicts_the_interval_on_rounded_series():
    rng, held = np.random.default_rng(5), 0
    for _ in range(500):
        y = np.round(0.6 * rng.standard_normal(24) + rng.uniform(0, 0.08) * np.arange(24)).tolist()
        if len(set(y)) == 1:
            continue
        fit = stats.trend_test(YEARS, y)
        held += fit.p < T.alpha and includes_zero(fit)
        assert not (fit.level == "clear" and includes_zero(fit)), y
        assert not (fit.slope_per_decade == 0 and fit.level in ("clear", "likely")), y
    assert held > 50, "rounded series must reach the tied case"


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
    assert key(("step", 0.001), ("step", 0.002)) == "claim.step"
    assert key(("unsupported", 0.3)) == "claim.unsupported"
    assert key(("insufficient", math.nan)) == "claim.nothing"
    many = stats.claim_verdict([("supported", 0.04)] + [("unsupported", 0.3 + i / 20) for i in range(7)])
    assert (many.verdict.key, many.survives[0], many.final[0]) == ("claim.unsupported", False, "unsupported")
    mixed = stats.claim_verdict([("supported", 0.001), ("opposed", 0.002), ("insufficient", math.nan)])
    assert (mixed.verdict.level, mixed.survives) == ("likely", [True, True, False])


def test_a_jump_in_the_claimed_direction_is_support():
    def key(*tests):
        return stats.claim_verdict(list(tests)).verdict.key

    assert key(("supported", 0.001), ("step", 0.002)) == "claim.supported"
    assert key(("step", 0.001), ("unsupported", 0.4)) == "claim.unsupported"
    assert key(("step", 0.001), ("opposed", 0.002)) == "claim.mixed"
    assert key(("step", 0.001), ("insufficient", math.nan)) == "claim.step"


def test_field_test_needs_its_q_and_its_own_level():
    base = stats.trend_test(YEARS, [0.1 * i for i in range(24)])
    cells = [(0.001, "clear"), (0.02, "clear"), (0.04, "clear"), (0.5, "unclear"), (0.001, "likely")]
    clear, qs = stats.field_test([base.model_copy(update={"p": p, "level": lvl}) for p, lvl in cells])
    assert qs == pytest.approx([0.0025, 0.1 / 3, 0.05, 0.5, 0.0025])
    assert clear == [True, True, False, False, False]


def test_field_test_holds_no_trend_maps_near_its_rate(capsys):
    cells = 48
    maps = ar1(np.random.default_rng(31), 0.17, 100 * cells).reshape(100, cells, 24)
    field, alone = [], []
    for m in maps:
        fits = [stats.trend_test(YEARS, list(y)) for y in m]
        field.append(any(stats.field_test(fits)[0]))
        up = sum(f.level == "clear" and f.z > 0 for f in fits)
        alone.append(max(up, sum(f.level == "clear" for f in fits) - up) > T.alpha * cells)
    with capsys.disabled():
        print(f"\nno-trend 8x6 maps, 100 runs: any cell clear after field_test {np.mean(field):.2f}, "
              f"more cells clear alone than chance {np.mean(alone):.2f}")
    assert np.mean(alone) > 0.15, "the premise: cells that pass alone outnumber chance on many maps"
    assert np.mean(field) <= 0.1


def test_step_rate_measured(capsys):
    series = ar1(np.random.default_rng(11), 0.3, 1000, trend=3 / 23)
    outcomes = [stats.test_claim(stats.trend_test(YEARS, list(y)), "up", YEARS, list(y)) for y in series]
    real = [o for o in outcomes if o in ("supported", "step")]
    rate = real.count("step") / len(real)
    with capsys.disabled():
        print(f"\nstep on steady AR(1) trends: {rate:.3f} of {len(real)} real trends")
    assert rate == pytest.approx(T.step_false_fire, abs=0.02)


def test_a_clean_jump_is_a_step_not_unsupported():
    y = list(np.array([0.0] * 12 + [5.0] * 12) + 0.2 * np.random.default_rng(0).standard_normal(24))
    fit = stats.trend_test(YEARS, y)
    assert stats.pettitt(YEARS, y)[1] < 0.001, "the premise: a jump Pettitt cannot miss"
    assert (fit.level, fit.direction) == ("clear", "rising")
    assert stats.test_claim(fit, "up", YEARS, y) == "step"
    assert stats.test_claim(fit, "down", YEARS, y) == "opposed"


def test_mid_record_jumps_are_seen_at_least_9_times_in_10(capsys):
    rng, seen = np.random.default_rng(12), {}
    for size in (3, 5, 8):
        series = rng.standard_normal((2000, 24)) + size * (np.arange(24) >= 12)
        outcomes = [stats.test_claim(stats.trend_test(YEARS, list(y)), "up", YEARS, list(y)) for y in series]
        seen[size] = float(np.mean([o in ("step", "supported") for o in outcomes]))
    with capsys.disabled():
        print("\nmid-record jump on white noise, n=24, 2000 runs, step or supported: "
              + ", ".join(f"{k} sd -> {v:.3f}" for k, v in seen.items()))
    assert all(v >= 0.90 for v in seen.values()), seen


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


def test_fmt_level_shows_one_level_at_three_significant_figures():
    got = [stats.fmt_level(x) for x in (27.53, 27.04, 1234.5, -0.04567, 0, math.nan)]
    assert got == ["27.5", "27.0", "1234", "−0.0457", "0", "n/a"]


def test_fmt_pair_keeps_the_gap_that_fmt_prints():
    assert stats.fmt(26.98) == stats.fmt(27.44) == "27"
    assert stats.fmt_pair(26.98, 27.44) == ("26.98", "27.44")
    assert stats.fmt_pair(1234.5, 1300.2) == ("1234", "1300")
    assert stats.fmt_pair(-0.5, 0.25) == ("−0.5", "0.25")
    assert stats.fmt_pair(math.nan, 27.44) == ("n/a", "27") and stats.fmt_pair(27.44, math.inf) == ("27", "n/a")
    for pair in ((None, 27.44), (27.44, None)):
        with pytest.raises(TypeError):
            stats.fmt(None)
        with pytest.raises(TypeError):
            stats.fmt_pair(*pair)


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


def test_level_gap_p_separates_shifted_periods_and_not_identical_ones():
    rng = np.random.default_rng(3)
    base = list(rng.normal(0, 1, 30))
    assert stats.level_gap_p([x + 3 for x in base[:15]], base) < 0.001
    assert stats.level_gap_p(base, base) == pytest.approx(1)
    assert stats.level_gap_p([1.0] * 10, [1.0] * 10) == 1.0


def test_slope_gap_is_zero_for_one_fit_and_large_for_opposite_lines():
    up = stats.trend_test(YEARS, [0.1 * i + (-1) ** i * 0.05 for i in range(24)])
    down = stats.trend_test(YEARS, [-0.1 * i + (-1) ** i * 0.05 for i in range(24)])
    assert stats.slope_gap(up, up) == (0, 0, 1)
    d, z, p = stats.slope_gap(up, down)
    assert d == pytest.approx(up.slope_per_decade - down.slope_per_decade) and z > 0 and p < T.alpha


def test_clustering_tail_is_the_hypergeometric_chance():
    c = stats.clustering(YEARS, [float(i) for i in range(24)])
    assert (c.top_k, c.window) == (6, 10)
    assert c.high == (6, pytest.approx(math.comb(10, 6) / math.comb(24, 6)))
    assert c.low == (0, 1.0)


def test_season_centre_finds_an_april_peak_and_skips_even_rain():
    peaked = [(y, m, 100 + 90 * math.cos(2 * math.pi * (m - 4) / 12)) for y in YEARS for m in range(1, 13)]
    years, days, centre, concentration = stats.season_centre(peaked)
    assert years == YEARS and 90 <= centre < 120 and concentration > T.season_concentration
    assert days == pytest.approx([centre] * 24)
    assert stats.season_centre([(y, m, 50.0) for y in YEARS for m in range(1, 13)]) is None


def test_unusual_word_cuts():
    assert [stats.unusual_word(x) for x in (0.99, -1, 1.99, -2, 3)] == \
        ["ordinary", "unusual", "unusual", "exceptional", "exceptional"]


def test_detrending_removes_a_link_made_by_two_trends(capsys):
    rng = np.random.default_rng(1)
    trend = 10 * np.arange(24) / 23
    runs = [stats.relation(YEARS, list(trend + rng.standard_normal(24)), list(trend + rng.standard_normal(24)))
            for _ in range(500)]
    rate = np.mean([r.rho_raw > 0.5 and r.rho < 0.3 for r in runs])
    with capsys.disabled():
        print(f"\ntwo trends 10x noise, 500 runs: rho_raw > 0.5 and detrended rho < 0.3 in {rate:.3f}")
    assert rate >= 0.9


def test_relation_memory_correction_and_cuts():
    x = [float(i % 5) for i in range(24)]
    r = stats.relation(YEARS, x, [2 * v + 1 for v in x])
    assert r.rho == pytest.approx(1) and r.p == 0 and r.share_together == 1
    assert r.sensitivity[0] == pytest.approx(2) and r.lead is not None
    assert T.neff_floor <= r.n_eff <= 24
    assert [stats.strength(v) for v in (0.19, -0.2, 0.39, 0.4, -0.6)] == ["no", "weak", "weak", "moderate", "strong"]


def test_swing_counts_a_run_of_wet_years():
    rain = [1646, 1265, 1374, 1335, 1366, 1669, 1361, 1312, 1266, 1182, 1489, 1482,
            1478, 1297, 960, 1167, 1571, 1897, 1855, 2423, 2402, 2446, 1746, 1742]
    sen = theilslopes(rain, YEARS)
    mid = (YEARS[0] + YEARS[-1]) / 2
    res = np.array(rain) - sen.slope * (np.array(YEARS) - mid)
    res -= np.median(res)
    fit = stats.trend_test(YEARS, rain)
    assert fit.swing == pytest.approx(np.std(res, ddof=1))
    assert stats.size(fit)[0] == "moderate"


def test_anomalies_take_out_the_yearly_cycle_and_keep_the_order():
    monthly = [(2001, 1, 10.0), (2001, 7, 30.0), (2002, 1, 14.0), (2002, 7, 20.0)]
    assert stats.anomalies(monthly) == [-2.0, 5.0, 2.0, -5.0]


def test_second_opinions_are_the_library_tests_and_leave_the_headline_test_alone():
    monthly = [(y, m, 5 + 3 * math.sin(m) + 0.02 * (y - 2001) + 0.1 * ((y * m) % 7)) for y in YEARS for m in range(1, 13)]
    yearly = [float(np.mean([x for yy, _, x in monthly if yy == y])) for y in YEARS]
    before = stats.trend_test(YEARS, yearly)
    got = stats.second_opinions(yearly, monthly)
    assert stats.trend_test(YEARS, yearly) == before
    assert got.plain == pytest.approx(pymannkendall.original_test(yearly).p)
    assert got.hamed_rao == pytest.approx(pymannkendall.hamed_rao_modification_test(yearly).p)
    assert got.yue_wang == pytest.approx(pymannkendall.yue_wang_modification_test(yearly).p)
    assert got.prewhitened == pytest.approx(pymannkendall.trend_free_pre_whitening_modification_test(yearly).p)
    assert got.seasonal == pytest.approx(pymannkendall.seasonal_test([x for _, _, x in monthly], period=12).p)
    assert len(got.ps) == 6 and got.found == sum(p < T.alpha for p in got.ps)
    alone = stats.second_opinions(yearly)
    assert alone.seasonal is None and alone.anomalies is None and len(alone.ps) == 4 and alone.plain == got.plain


def test_memory_is_flagged_outside_the_range_of_a_record_with_none():
    rng = np.random.default_rng(3)
    assert not stats.second_opinions(list(rng.standard_normal(24))).memory
    remembered = stats.second_opinions(list(ar1(rng, 0.8, 1)[0]))
    assert remembered.memory and remembered.lag1 > 0


def test_line_fit_is_the_least_squares_line_with_its_t_interval():
    y = [0.5 * i + (-1) ** i for i in range(24)]
    slope, lo, hi, p = stats.line_fit(YEARS, y)
    fit = linregress(YEARS, y)
    assert slope == pytest.approx(fit.slope * 10) and p == pytest.approx(fit.pvalue) and lo < slope < hi
    assert (hi - lo) / 20 == pytest.approx(2.074 * fit.stderr, rel=1e-3)   # half-width per year: t at 22 degrees of freedom


def test_spearman_and_pearson_read_the_values_as_they_are():
    xs, ys = [1.0, 2.0, 3.0, 4.0, 5.0], [1.0, 4.0, 9.0, 16.0, 26.0]
    rho, p = stats.spearman(xs, ys)
    assert rho == pytest.approx(1) and p < T.alpha
    assert 0.9 < stats.pearson(xs, ys) < 1
