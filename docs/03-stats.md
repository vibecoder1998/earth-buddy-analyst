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
    test: Literal["mann-kendall", "hamed-rao"]
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
3. Sen slope and its 95% interval come from `scipy.stats.theilslopes(y, x, 0.95)`.
4. If every value is the same, return `p = 1`, `constant = True`, and level `unclear`.
5. Mann-Kendall comes from `pymannkendall`. Use `original_test` by default. Switch to `hamed_rao_modification_test` when `n >= T.reliable` and `|lag1| > 1.96 / sqrt(n)`. If the result is not finite, use `original_test`. If that is not finite either, set `p = 1`.
6. Level: `too_short` if `n < T.reliable`. Otherwise `clear` if `p < T.alpha`, `likely` if `p < T.likely`, and `unclear` for anything else.
7. Direction: `flat` if the slope is 0. Otherwise the sign of the slope.

### The autocorrelation check

Year-to-year memory inflates false trends. The claim desk measured this at n = 24 and corrected it with its own variance table. This spec uses Hamed-Rao instead, because it is a published method in an installed library. A test must show that it holds:

- Simulate 2,000 AR(1) series with no trend, n = 24, φ ∈ {0, 0.3, 0.5}.
- The share with `p < 0.05` must be at most 0.08 for each φ.

If the check fails, replace step 5 with the claim desk's correction. Compute `φ` as the lag-1 autocorrelation of the detrended series, plus `(1 + 3r)/n`, clipped to [0, 0.9]. Interpolate the variance factor from this table: `[[0,1],[.1,1.183],[.2,1.383],[.3,1.683],[.4,2.021],[.5,2.482],[.6,3.12],[.7,4],[.8,5.386],[.9,7.712]]`. Then compute `Z_c = Z / sqrt(vif)` and `p = 2 · (1 − Φ(|Z_c|))`. Reference: `~/earth-buddy/js/stats.js`.

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

`fmt(x)` shows about 2 significant figures, at most 4 decimals, with a Unicode minus sign. `fmt_p(p)` shows "< 0.001" or 3 decimals. Every number in `facts` passes through one of these two functions, so the explainer check compares like with like.

## Acceptance

- Sen slope recovers a known slope on a noise-free line.
- `trend_test` agrees with `pymannkendall` and `scipy` directly on 20 random series.
- The AR(1) false-positive check above passes.
- Pure white noise at n = 24 gives `p < 0.05` in at most 7% of 2,000 runs.
- `bh` matches this worked example: p = [0.01, 0.04, 0.03, 0.005] gives q = [0.02, 0.04, 0.04, 0.02].
- `claim_verdict` returns each of the six keys on a hand-built input.
- Measure how often `step` fires on a steady AR(1) trend at φ = 0.3. Write the measured rate into the board's step text. The claim desk measured about one time in six with its own test. Re-measure it, because the test changed.
- `fmt(-0.01234)` returns "−0.012".

## Reference

`~/earth-buddy/js/stats.js` and `tests/stats.test.mjs` (claim test, Pettitt, step, BH). `~/earth-buddy/earth-buddy-analyst/earthbuddy/stats.py` and `tests/test_stats.py` (Sen, Mann-Kendall, Hamed-Rao, STL, wording).
