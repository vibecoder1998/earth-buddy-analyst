# Statistics engine

`earthbuddy/stats.py` holds every statistical function. It does no I/O, and nothing else computes a p-value, a slope, or a verdict. Priority P0. Estimate 3 hours.

The two prototypes used different trend tests and different verdict words. This spec keeps one of each.

## Constants

Put every threshold in one object. No other file repeats a number from this table.

```python
class T:
    alpha       = 0.05   # "clear"
    likely      = 0.10   # "likely, but not certain"
    fdr_q       = 0.10   # Benjamini-Hochberg false discovery rate
    min_years   = 8      # below this: refuse to compute
    reliable    = 10     # below this: compute, but the level is "too_short"
    step_ratio  = 0.8    # two-level fit SSE / straight-line SSE below this = "one jump"
    pettitt_p   = 0.05
    vif_a, vif_b, vif_cap = 3, 6, 0.9           # memory estimate, step 5
    vif_table   = [[0, 1], ..., [.9, 7.712]]    # variance factor per memory, step 5
    step_false_fire = 0.16                      # measured, see Acceptance
```

## Types

```python
Level = Literal["clear", "likely", "unclear", "too_short"]

class Fit(BaseModel):
    n: int; first_year: int; last_year: int
    slope_per_decade: float; lo_per_decade: float; hi_per_decade: float   # Sen slope, 95% interval
    intercept: float                     # Sen intercept at the median year
    mean: float
    swing: float                         # typical year-to-year swing: MAD of residuals × 1.4826 (std if MAD is 0)
    total_change: float                  # slope × (last_year − first_year)
    percent_change: float | None         # for rel variables
    p: float; z: float; tau: float
    test: Literal["mann-kendall", "mann-kendall-vif"]   # "-vif" when the memory correction widened the variance
    t_p: float                           # slope t-test p, memory-corrected; shown next to p, never sets the level
    lag1: float                          # lag-1 autocorrelation of the Sen residuals
    constant: bool
    direction: Literal["rising", "falling", "flat"]
    level: Level

class Verdict(BaseModel):
    key: str        # an i18n key, for example "claim.supported" or "trend.clear"
    level: Level
```

## Trend test

```python
def trend_test(years: list[int], values: list[float | None]) -> Fit
```

1. Drop missing years. `n` counts the years left.
2. If `n < T.min_years`, raise `TooShort`.
3. The Sen slope comes from `scipy.stats.theilslopes(y, x)`. Its 95% interval uses the memory-corrected variance of step 5, so it agrees with `p`. Sort the `N` pairwise slopes and take `C = z · sqrt(Var(S) · vif)`, with `z` the normal quantile for `T.ci` and `Var(S)` from `pymannkendall.original_test`. The interval runs from slope rank `round((N − C)/2)` to rank `round((N + C)/2) + 1`, counted from 1 and clipped to `[1, N]` (Sen 1968, eq. 2.6). With `vif = 1` this is the `theilslopes` interval. A constant series gets the interval `[0, 0]`.
4. If every value is the same, return `p = 1`, `constant = True`, and level `unclear`.
5. Mann-Kendall `Z` comes from `pymannkendall.original_test`. Correct it for year-to-year memory with the claim desk's variance table:
   - `r` is the lag-1 autocorrelation of the Sen residuals.
   - `φ = r + (T.vif_a + T.vif_b · r) / n`, clipped to `[0, T.vif_cap]`, with `T.vif_a = 3`, `T.vif_b = 6`, and `T.vif_cap = 0.9`.
   - `vif` is `φ` interpolated in `T.vif_table`: `[[0,1],[.1,1.183],[.2,1.383],[.3,1.683],[.4,2.021],[.5,2.482],[.6,3.12],[.7,4],[.8,5.386],[.9,7.712]]`.
   - `Z_c = Z / sqrt(vif)` and `p = 2 · (1 − Φ(|Z_c|))`. `Fit.z` is `Z_c`. If `Z_c` is not finite, set `p = 1`.
6. Slope t-test, shown next to Mann-Kendall because the challenge names both. It never sets the level or the verdict. Fit `scipy.stats.linregress(x, y)`. Shrink `n` with the same `φ` as step 5: `n_eff = min(n, max(T.neff_floor, n · (1 − φ) / (1 + φ)))`, with `T.neff_floor = 4`. Then `t = |slope| / stderr · sqrt((n_eff − 2) / (n − 2))` and `t_p = 2 · (1 − F_t(t; n_eff − 2))`. A zero `stderr` gives `t_p = 0`. A constant series gives `t_p = 1`.
7. Level: `too_short` if `n < T.reliable`. Otherwise `clear` if `p < T.alpha`, `likely` if `p < T.likely`, and `unclear` for anything else.
8. Direction: `flat` if the slope is 0. Otherwise the sign of the slope.

### The autocorrelation check

Year-to-year memory inflates false trends. A test must show that the correction holds:

- Simulate 2,000 AR(1) series with no trend, n = 24, φ ∈ {0, 0.3, 0.5}.
- The share with `p < 0.05` must be at most 0.08 for each φ.

Hamed-Rao failed this check at n = 24, with rates of 0.058, 0.113, and 0.197 (`docs/PLAN.md` Appendix A, finding 1). The other `pymannkendall` corrections failed too or lost most of their power. The claim desk's table with its original bias fix, `φ = r + (1 + 3r)/n`, gave 0.093 and 0.102 at φ = 0.5 on two seeds. The stronger fix in step 5 gave 0.028, 0.048, and 0.073 in the prototype, with power 0.39 on a trend of 0.8 standard deviations per decade. `tests/test_stats.py` measures 0.036, 0.057, and 0.071 (seed 4), and 0.025 on white noise (seed 7).

The Sen interval must pass it too. On 2,000 seed-4 series at each of φ = 0.3 and 0.5, the interval excludes 0 in 0.062 and 0.069 of runs, the same share as `p < 0.05`. Before the interval used `Var(S) · vif`, `theilslopes` excluded 0 in 0.134 and 0.209 of them. On 1,000 random series with φ from 0 to 0.6 and trends from 0 to 1.5 noise units per decade (seed 8), "the interval excludes 0" and "`p < T.alpha`" agree on every series.

The slope t-test must pass the same check on `t_p`. Uncorrected, `linregress` gave 0.054, 0.132, and 0.239. With `n_eff` from the plain lag-1 `r` (Santer et al. 2008) it gave 0.048, 0.088, and 0.106. With `φ` from step 5, `tests/test_stats.py` measures 0.042, 0.051, and 0.061 (seed 4).

## Change point and step

```python
def pettitt(years, values) -> tuple[int, float]     # (first year of the new regime, p)
def is_step(years, values, cp) -> bool              # two-level fit SSE < T.step_ratio × Sen line SSE
```

Pettitt p is `min(1, 2 · exp(−6K² / (n³ + n²)))`.

## Multiple tests

```python
def bh(ps: list[float]) -> list[float]   # Benjamini-Hochberg q-values; step-up, monotone, capped at 1, NaN kept as NaN
```

A test "survives" when `q < T.fdr_q`.

## Claim test

```python
Outcome = Literal["insufficient", "unsupported", "opposed", "step", "supported"]
def test_claim(fit: Fit | None, direction: Direction, years, values) -> Outcome
```

- `insufficient`: no fit (fewer than `T.min_years`), a constant series, or level `too_short`.
- `unsupported`: `p >= T.alpha`.
- `opposed`: a clear trend in the other direction. `any` never opposes.
- `step`: a clear trend in the claimed direction, where Pettitt `p < T.pettitt_p` and `is_step` is true. The board says "A real change, in one jump".
- `supported`: a clear trend in the claimed direction.

```python
def claim_verdict(tests: list[tuple[Outcome, float]]) -> tuple[Verdict, list[bool]]
```

1. Run `bh` on the p-values of the tests that are not `insufficient`.
2. A `supported`, `opposed`, or `step` test that does not survive counts as `unsupported`.
3. The verdict key, in order:
   - `claim.nothing` if every test is `insufficient`.
   - `claim.supported` if every live test is supported.
   - `claim.opposed` if every live test is opposed.
   - `claim.mixed` if some tests are supported and some are opposed.
   - `claim.step` if no test is supported or opposed and at least one is a step.
   - `claim.unsupported` for anything else.

## Plain-language size and certainty

The trend result shows these two lines. They come from `~/earth-buddy/earth-buddy-analyst/earthbuddy/analyses.py`.

- Size: `years = swing / (|slope_per_decade| / 10)` is the number of years the trend takes to move one typical swing. At 30 years or more the size is `small`, and above 200 years the text says "more than 200". From 10 to under 30 years it is `moderate`. Under 10 years it is `large`. A slope of 0 gives `none`.
- Certainty, as a coin: `heads = −log2(p)`. Under 0.75 the text says "not surprising at all". Otherwise it says "like N heads in a row", with N rounded and capped at 10. The text adds that 4 or 5 heads in a row is where scientists start calling a change real.

## Number formatting

`fmt(x)` shows a change, slope, difference, or ratio with about 2 significant figures (`T.fmt_sig`), at most 4 decimals, with a Unicode minus sign. `fmt_level(x)` shows a level with 3 significant figures (`T.level_sig`) and keeps trailing zeros, so a baseline reads "27.5 °C to 28.4 °C" next to a difference of "0.93 °C". A level is a period mean, a year's value, a trend-line value, or a rank by level. `fmt_p(p)` shows "< 0.001" or 3 decimals. Every number in `facts` passes through one of these three functions, so the explainer check compares like with like.

## Acceptance

- Sen slope recovers a known slope on a noise-free line, with an interval of zero width.
- The 95% interval excludes 0 exactly when `p < T.alpha`, in at least 95% of random series.
- `trend_test` agrees with `pymannkendall` and `scipy` directly on 20 random series.
- The AR(1) false-positive check above passes.
- Pure white noise at n = 24 gives `p < 0.05` in at most 7% of 2,000 runs.
- `bh` matches this worked example: p = [0.01, 0.04, 0.03, 0.005] gives q = [0.02, 0.04, 0.04, 0.02].
- `claim_verdict` returns each of the six keys on a hand-built input.
- Measure how often `step` fires on a steady AR(1) trend at φ = 0.3. Write the measured rate into the board's step text. The claim desk measured about one time in six with its own test. Re-measured with this test on 1,000 series rising 3 units over 24 years: 714 came out as real trends, and 0.155 of those were called a step, so about one time in six still holds. `T.step_false_fire = 0.16` holds the number, and `test_step_rate_measured` fails if a re-measure drifts more than 0.02 from it.
- `fmt(-0.01234)` returns "−0.012".

## Reference

`~/earth-buddy/js/stats.js` and `tests/stats.test.mjs` (claim test, Pettitt, step, BH). `~/earth-buddy/earth-buddy-analyst/earthbuddy/stats.py` and `tests/test_stats.py` (Sen, Mann-Kendall, STL, wording).
