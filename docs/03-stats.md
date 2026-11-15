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
    field_q     = 0.05   # Benjamini-Hochberg across the cells of one where map (Wilks 2016)
    min_years   = 8      # below this: refuse to compute
    reliable    = 10     # below this: compute, but the level is "too_short"
    step_ratio  = 0.8    # two-level fit SSE / straight-line SSE below this = "one jump"
    pettitt_p   = 0.05
    vif_a, vif_b, vif_cap = 3, 6, 0.9           # memory estimate, step 5
    vif_table   = [[0, 1], ..., [.9, 7.712]]    # variance factor per memory, step 5
    step_false_fire = 0.21                      # measured, see Acceptance
```

## Types

```python
Level = Literal["clear", "likely", "unclear", "too_short"]

class Fit(BaseModel):
    n: int; first_year: int; last_year: int
    slope_per_decade: float; lo_per_decade: float; hi_per_decade: float   # Sen slope, 95% interval
    intercept: float                     # Sen intercept at the median year
    mean: float
    swing: float                         # typical year-to-year swing: standard deviation of the residuals from the Sen line
    total_change: float                  # slope × (last_year − first_year)
    percent_change: float | None         # for rel variables
    p: float; z: float; tau: float
    test: Literal["mann-kendall", "mann-kendall-vif"]   # "-vif" when the memory correction widened the variance
    t_p: float                           # slope t-test p, memory-corrected; shown next to p, never sets the level
    lag1: float                          # lag-1 autocorrelation the memory correction used (step 5)
    constant: bool
    direction: Literal["rising", "falling", "flat"]
    level: Level
    clear_one_sided: bool                # step 9: a one-sided test in the direction of z would call this clear

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
3. The Sen slope comes from `scipy.stats.theilslopes(y, x)`. Its 95% interval uses the memory-corrected variance of step 5, so it agrees with `p`. Sort the `N` pairwise slopes and take `C = z · sqrt(Var(S) · vif)`, with `z` the normal quantile for `T.ci` and `Var(S)` from `pymannkendall.original_test`. The interval runs from slope rank `round((N − C)/2)` to rank `round((N + C)/2) + 1`, counted from 1 and clipped to `[1, N]` (Sen 1968, eq. 2.6). With `vif = 1` this is the `theilslopes` interval. A constant series gets the interval `[0, 0]`. Two years with the same value give a pairwise slope of exactly 0, so on a record with many ties the interval can hold 0, or the slope itself can be 0, while Mann-Kendall, which counts only the order of the untied pairs, gives `p < T.alpha`. Step 7 settles that case.
4. If every value is the same, return `p = 1`, `constant = True`, and level `unclear`.
5. Mann-Kendall `Z` comes from `pymannkendall.original_test`. Correct it for year-to-year memory with the claim desk's variance table:
   - `r` is the lag-1 autocorrelation of the Sen residuals.
   - `φ = r + (T.vif_a + T.vif_b · r) / n`, clipped to `[0, T.vif_cap]`, with `T.vif_a = 3`, `T.vif_b = 6`, and `T.vif_cap = 0.9`.
   - A jump is not memory. A straight line through a jump leaves long runs of same-sign residuals, and `r` reads them as memory. So when the step check holds (`pettitt` gives `p < T.pettitt_p` and `is_step` is true), also take `r₂`, the lag-1 autocorrelation of the residuals from two levels: one mean before the Pettitt year and one from it on. `φ₂ = r₂ + (T.vif_a + T.vif_b · r₂) / m`, clipped the same way, where `m` is the number of years in the shorter level, because each level is demeaned over its own years. Use `φ₂` when it is smaller than `φ`. `Fit.lag1` is the `r` that was used. The two levels can lower the memory estimate and never raise it, so no fit gets a larger `p` from this rule.
   - `vif` is `φ` interpolated in `T.vif_table`: `[[0,1],[.1,1.183],[.2,1.383],[.3,1.683],[.4,2.021],[.5,2.482],[.6,3.12],[.7,4],[.8,5.386],[.9,7.712]]`.
   - `Z_c = Z / sqrt(vif)` and `p = 2 · (1 − Φ(|Z_c|))`. `Fit.z` is `Z_c`. If `Z_c` is not finite, set `p = 1`.
6. Slope t-test, shown next to Mann-Kendall because the challenge names both. It never sets the level or the verdict. Fit `scipy.stats.linregress(x, y)`. Shrink `n` with the same `φ` as step 5: `n_eff = min(n, max(T.neff_floor, n · (1 − φ) / (1 + φ)))`, with `T.neff_floor = 4`. Then `t = |slope| / stderr · sqrt((n_eff − 2) / (n − 2))` and `t_p = 2 · (1 − F_t(t; n_eff − 2))`. A zero `stderr` gives `t_p = 0`. A constant series gives `t_p = 1`.
7. Level: `too_short` if `n < T.reliable`. Otherwise start from `p`: `clear` if `p < T.alpha`, `likely` if `p < T.likely`, and `unclear` for anything else. Then make the level agree with the slope and its interval:
   - a slope of exactly 0 is `unclear`, whatever `p` is;
   - `clear` needs 0 strictly outside the interval of step 3. With `p < T.alpha` and an interval that holds 0, the level is `likely`.

   `p` itself is never changed. Every caller reads the level, not `p`, to decide whether a trend is clear: the trend headline, `test_claim`, the scan, the ranking, the monthly trends, the grid cells, and the coin word.
8. Direction: `flat` if the slope is 0. Otherwise the sign of the slope. A `flat` fit is never `clear` or `likely`.
9. One-sided: `clear_one_sided` is true when `n >= T.reliable`, the series is not constant, the slope is not 0, `p / 2 < T.alpha`, and 0 lies strictly outside a second Sen interval. That interval is the one of step 3 with `z` the normal quantile for `1 − T.alpha`, so it leaves `T.alpha` in each tail. `_sen_interval` takes the probability in each tail: step 3 passes `(1 − T.ci) / 2` and step 9 passes `T.alpha`. Only `test_claim` reads `clear_one_sided`. `p`, `level`, and every trend, scan, rank, and grid answer stay two-sided.

### Tied records

Rounded data ties. Aerosol optical depth is stored to 2 decimals, and Cairo's albedo is 0.20, 0.21 or 0.22 in every year. On the 11,348 region series in `data/v` (15 November 2026), 100 had `p < T.alpha` beside an interval that holds 0, and 9 of those had a slope of exactly 0. Before step 7 checked the interval, Cairo's albedo read "clearly flat" with `p = 0.029`. Now 91 of the 100 are `likely`, 9 are `unclear`, and 11 more with `T.alpha <= p < T.likely` and a slope of 0 moved from `likely` to `unclear`. A claim on any of them is `unsupported`.

A claim that names the direction the record runs in is a one-sided test (see Claim test). On the 12,354 series in `data/v` today, 101 have `p < T.alpha` beside an interval that holds 0. For 49 of them the one-sided interval of step 9 leaves out 0, so a claim that names their direction reads `supported` or `step`. Siem Reap's aerosol is one of the 49. A claim of `any` change on any of the 101 is still `unsupported`.

The person is told three things. The headline follows the level ("probably rising" or "No clear change"). The p-value is shown as computed. A trend result adds the note `note.tied` whenever the level is lower than `p` alone would give: the order of the years gives this p-value, the range of the change still includes zero, this happens when many years share one value, and we do not call such a change clear.

### The autocorrelation check

Year-to-year memory inflates false trends. A test must show that the correction holds:

- Simulate 2,000 AR(1) series with no trend, n = 24, φ ∈ {0, 0.3, 0.5}.
- The share with `p < 0.05` must be at most 0.08 for each φ.

Hamed-Rao failed this check at n = 24, with rates of 0.058, 0.113, and 0.197 (`docs/PLAN.md` Appendix A, finding 1). The other `pymannkendall` corrections failed too or lost most of their power. The claim desk's table with its original bias fix, `φ = r + (1 + 3r)/n`, gave 0.093 and 0.102 at φ = 0.5 on two seeds. The stronger fix in step 5 gave 0.028, 0.048, and 0.073 in the prototype, with power 0.39 on a trend of 0.8 standard deviations per decade. `tests/test_stats.py` measures 0.037, 0.059, and 0.079 (seed 4), and 0.028 on white noise (seed 7). Before step 5 allowed for a jump it measured 0.036, 0.057, and 0.071, and 0.025.

The Sen interval must pass it too. On 2,000 seed-4 series at each of φ = 0.3 and 0.5, the interval excludes 0 in 0.063 and 0.077 of runs, the same share as `p < 0.05`. Before the interval used `Var(S) · vif`, `theilslopes` excluded 0 in 0.134 and 0.209 of them. On 1,000 random series with φ from 0 to 0.6 and trends from 0 to 1.5 noise units per decade (seed 8), "the interval excludes 0" and "`p < T.alpha`" agree on every series.

The slope t-test must pass the same check on `t_p`. Uncorrected, `linregress` gave 0.054, 0.132, and 0.239. With `n_eff` from the plain lag-1 `r` (Santer et al. 2008) it gave 0.048, 0.088, and 0.106. With `φ` from step 5, `tests/test_stats.py` measures 0.042, 0.057, and 0.070 (seed 4).

### The jump check

A clean jump must not read as memory, and plain memory must not read as a jump. Twelve years at 0 then twelve at 5 with noise 0.2 has a raw Mann-Kendall `p` of 0.00005 and a Pettitt `p` of 0.00035. Its Sen residuals have `r = 0.74`, which put `φ` at the cap and gave `p = 0.145`, so the claim read `unsupported`. With the two-level residuals of step 5, `r₂ = 0.19`, `p = 0.014`, and the claim reads `step`.

Each share below comes from 2,000 series per cell and 3 seeds, 6,000 in all, with a standard error of about 0.003 near 0.07 and 0.004 near 0.92. "Before" is the same series without the two-level rule.

| Series, n = 24 unless said | Share | Before | Now |
| --- | --- | --- | --- |
| No change, φ = 0 | `p < 0.05` | 0.033 | 0.033 |
| No change, φ = 0.3 | `p < 0.05` | 0.059 | 0.061 |
| No change, φ = 0.5 | `p < 0.05` | 0.073 | 0.077 |
| No change, n = 44, φ = 0, 0.3, 0.5 | `p < 0.05` | 0.040, 0.055, 0.064 | 0.040, 0.055, 0.065 |
| Jump of 3 noise standard deviations, mid-record, white noise | claim reads `step` or `supported` | 0.747 | 0.919 |
| Jump of 5, mid-record | the same | 0.489 | 0.935 |
| Jump of 8, mid-record | the same | 0.158 | 0.924 |
| Jump of 3, 5, 8 in year 6 | the same | 0.241, 0.059, 0.002 | 0.313, 0.205, 0.149 |
| Jump of 3, 5, 8 in year 20 | the same | 0.233, 0.064, 0.003 | 0.300, 0.205, 0.136 |
| Jump of 3, 5, 8, mid-record, on φ = 0.3 noise | the same | 0.529, 0.348, 0.136 | 0.700, 0.703, 0.664 |

These shares were measured while claims used the two-sided test. A one-sided claim can only see more of each jump: `tests/test_stats.py` now measures 0.964, 0.973, and 0.981 for mid-record jumps of 3, 5, and 8 (seed 12).

What this leaves. The margin at φ = 0.5 is thin: 0.077 against the limit of 0.08, and one of the three seeds measured 0.082. A jump within about five years of either end of a 24-year record is still missed most of the time: with 5 years on one side, Mann-Kendall `Z` cannot pass 2.33 and Pettitt `p` cannot go under 0.047. Outside the range this spec checks, the rule costs a little: at φ = 0.5 the share rises from 0.071 to 0.079 at n = 12 and from 0.077 to 0.085 at n = 16, and at φ = 0.7 and n = 24 from 0.092 to 0.105.

Three other designs were measured on the same series and rejected. Always using `φ₂` when the step check holds keeps the no-change share at 0.074 for φ = 0.5, but it raises `p` whenever one level is short, and the Arctic sea ice claim in `data/audit.json` went from `step` (`p = 0.035`) to `unsupported` (`p = 0.12`). Dividing by `n` instead of `m` gave 0.093 at φ = 0.5. A separate route in `test_claim` with a memory-corrected Pettitt test gave 0.092 at a cut of 0.05, saw 8-standard-deviation jumps only 0.87 of the time at a cut of 0.01, and left the trend, scan, and rank answers reading "no clear change" on a clean jump.

## Change point and step

```python
def pettitt(years, values) -> tuple[int, float]     # (first year of the new regime, p)
def is_step(years, values, cp) -> bool              # two-level fit SSE < T.step_ratio × Sen line SSE
```

Pettitt p is `min(1, 2 · exp(−6K² / (n³ + n²)))`.

## Monthly anomalies

```python
def anomalies(monthly: list[tuple[int, int, float]]) -> list[float]   # each month minus the mean of its calendar month
```

The Analyze panels use it to take the yearly cycle out of a monthly series before they relate two of them (`docs/21-haze.md`).

## Fire province gate

A province's fire trend is tested only when the span holds at least `T.reliable` seasons, at least `T.fire_min_total` (200) detections, and at least `T.fire_min_distinct` (4) different season counts (`docs/20-fire.md`).

## The Analyze panels

`trend_test` is the only test that sets a level, a verdict or a headline in the three panels. Everything else on a panel is one of the items below.

- Every headline trend is `trend_test` on one yearly series of 8 to 24 values: fire seasons, dry-season means, or yearly means.
- The same test runs on three yearly series: whole year, dry season and wet season (`analyses/monthly.by_part`). A note fires when the parts that can be judged reach different levels.
- A panel names a jump in the chosen span only when `pettitt` gives a p-value under `T.pettitt_p` and `is_step` agrees. No year is typed in. A test card also prints the most likely jump and its p-value whatever the p-value is, as the branch did. The card says "most likely jump after YEAR", the last year before the new level.
- A link to fire is `relation`. Month to month, `anomalies` takes the yearly cycle out of both series first, and the link runs only with at least `T.stl_min_months` months.
- Province trends use `bh` at `T.fdr_q`, the one false discovery rate. The branch used 0.05.
- Sen slopes match the branch. `docs/20-fire.md`, `docs/21-haze.md` and `docs/22-water.md` list the reference numbers.

### Second opinions

The branch `feat/fire-watch-cambodia` showed Mann-Kendall run several other ways. The panels show the same numbers, as second opinions. `second_opinions(yearly, monthly)` returns one `Opinions` value, and every one of its p-values comes from `pymannkendall`:

| Field | Test | Library call |
|---|---|---|
| `plain` | Mann-Kendall with the tie correction, no correction for memory | `original_test` |
| `prewhitened` | trend-free pre-whitening (Yue et al. 2002) | `trend_free_pre_whitening_modification_test` |
| `hamed_rao` | Hamed and Rao variance correction | `hamed_rao_modification_test` |
| `yue_wang` | Yue and Wang variance correction | `yue_wang_modification_test` |
| `seasonal` | each calendar month against the same month of other years | `seasonal_test(period=12)` |
| `anomalies` | the plain test on every month minus its calendar month's mean | `original_test` on `anomalies` |

`lag1` is the lag-1 autocorrelation of the yearly values around their Sen line. `memory` is true when `lag1` is outside the `T.ci` range of a record with no memory, which is the rule the branch used to choose between the plain and the pre-whitened p-value. `found` counts the p-values under `T.alpha`. `seasonal` and `anomalies` are `None` when there are no monthly values, as for the fire seasons.

Rules:

- A second opinion never sets a level, a verdict, a headline or a tile. `tests/test_panels.py` checks that the level is `trend_test`'s for every measure.
- The screen says so next to the numbers: the card names the headline test first and the others as "second opinions", the six-test card ends with "the headline test alone sets the level", and the method step `step.opinions` says why.
- They are not calibrated here and they are not used to decide anything. Hamed-Rao failed the false-positive check above at n = 24, with rates of 0.058, 0.113 and 0.197 where 0.05 is the target. The other corrections failed too or lost most of their power. That is why none of them is the headline test, and why a card that counts "k of 6" is a description of disagreement and not a vote.
- `T.alpha` is the only cut-off they use.

Three more functions give figures the branch printed. None sets a level.

- `line_fit(years, values)`: the least-squares slope per decade, its Student t interval at `T.ci`, and the t-test p-value, with no correction for memory. `trend_test`'s own `t_p` is corrected for memory, so the two differ.
- `spearman(xs, ys)`: rho and p of the values as they are. `relation` detrends first and corrects for memory, so its rho and p differ. The haze panel prints both and labels this one "plain".
- `pearson(xs, ys)`: r between two monthly series, for the month-to-month links of the water panel.

## Multiple tests

```python
def bh(ps: list[float]) -> list[float]   # Benjamini-Hochberg q-values; step-up, monotone, capped at 1, NaN kept as NaN
```

A test "survives" when `q < T.fdr_q`.

```python
def field_test(fits: list[Fit]) -> tuple[list[bool], list[float]]   # (clear per cell, q per cell)
```

A where map is one family of tests (Wilks 2016). `field_test` runs `bh` over the two-sided `p` of every cell. A cell is clear when `q < T.field_q` and its own level is `clear`. The level keeps the tie rule of step 7, so a map can never read clear with no clear cell. `where.py` and `tools/error_audit.py` both call it, and nothing else holds the rule.

## Claim test

```python
Outcome = Literal["insufficient", "unsupported", "opposed", "step", "supported"]
def test_claim(fit: Fit | None, direction: Direction, years, values) -> Outcome
```

A claim that names a direction in advance is a one-sided test. The trend running the other way was never claimed, so it is tested two-sided.

```python
def one_sided(fit: Fit, direction: Direction) -> bool   # direction is up or down and the sign of fit.z matches it
def claim_p(fit: Fit, direction: Direction) -> float    # fit.p / 2 when one_sided, else fit.p
```

- `insufficient`: no fit (fewer than `T.min_years`), a constant series, or level `too_short`.
- `opposed`: the direction is `up` or `down`, `z` runs against it, and the level is `clear`. `any` never opposes.
- `unsupported`: `z` runs against the named direction and the level is not `clear`. Or, for a named direction, `clear_one_sided` (step 9) is false. Or, for `any`, the level is not `clear` (step 7).
- `step`: the part passes, and Pettitt `p < T.pettitt_p` and `is_step` is true. The board says "A jump, not a trend".
- `supported`: the part passes and is not a step.

```python
def claim_verdict(tests: list[tuple[Outcome, float]]) -> Scored   # (verdict, survives, final)
```

`claim.py` passes `claim_p` for each test, or NaN when there is no fit.

1. Run `bh` on the p-values of the tests that are not `insufficient`.
2. A `supported`, `opposed`, or `step` test that does not survive counts as `unsupported`.
3. A jump in the claimed direction is support. With `pro` the set of `supported` and `step`, the verdict key is the first of these that holds:
   - `claim.nothing` if every test is `insufficient`.
   - `claim.step` if every live test is a step.
   - `claim.supported` if every live test is in `pro`.
   - `claim.opposed` if every live test is opposed.
   - `claim.mixed` if some live tests are in `pro` and some are opposed.
   - `claim.unsupported` for anything else.

So `[supported, step]` is `claim.supported`, `[step, opposed]` is `claim.mixed`, and `[step, unsupported]` is `claim.unsupported`. A jump beside a supported part gets no verdict of its own, because the step check calls about one steady trend in five a jump (`T.step_false_fire`). `claim.py` names those parts in a note instead (`docs/05-claim-check.md`).

## Plain-language size and certainty

The trend result shows these two lines. They come from `~/earth-buddy/earth-buddy-analyst/earthbuddy/analyses.py`.

- Size: `years = swing / (|slope_per_decade| / 10)` is the number of years the trend takes to move one typical swing. At 30 years or more the size is `small`, and above 200 years the text says "more than 200". From 10 to under 30 years it is `moderate`. Under 10 years it is `large`. A slope of 0 gives `none`.
- Certainty, as a coin: the word follows the level (`clearly` for `clear`, `probably` for `likely`, `cant_tell` for anything else). `heads = −log2(p)`. Under 0.75 the text says "not surprising at all". Otherwise it says "like N heads in a row", with N rounded and capped at 10. The text adds that 4 or 5 heads in a row is where scientists start calling a change real.

## Number formatting

`fmt(x)` shows a change, slope, difference or ratio with about 2 significant figures (`T.fmt_sig`), at most 4 decimals, with a Unicode minus sign. `fmt_level(x)` shows one level with nothing beside it (a trend's average, a record year's value, a rank by level) with 3 significant figures (`T.level_sig`) and its trailing zeros, never rounded past the units, so a trend reads "27.0 °C" and a rain total "1234 mm". `fmt_pair(a, b)` shows two levels side by side at the finest decimals `fmt` gives `a`, `b` or `b - a`, so they never print alike beside a nonzero gap. `fmt_p(p)` shows "< 0.001" or 3 decimals. Every number in `facts` passes through one of these functions, so the explainer check compares like with like.

## Acceptance

- Sen slope recovers a known slope on a noise-free line, with an interval of zero width.
- The 95% interval excludes 0 exactly when `p < T.alpha`, in at least 95% of random series without ties.
- No fit is `clear` with 0 inside its interval, and no fit with a slope of 0 is `clear` or `likely`. This holds on every one of 500 rounded random series, of which more than 50 have `p < T.alpha` beside an interval that holds 0 (`test_level_never_contradicts_the_interval_on_rounded_series`), and on the Cairo albedo and Siem Reap aerosol records.
- `trend_test` agrees with `pymannkendall` and `scipy` directly on 20 random series.
- The AR(1) false-positive check above passes.
- Pure white noise at n = 24 gives `p < 0.05` in at most 7% of 2,000 runs.
- `bh` matches this worked example: p = [0.01, 0.04, 0.03, 0.005] gives q = [0.02, 0.04, 0.04, 0.02].
- `claim_verdict` returns each of the six keys on a hand-built input, and `[supported, step]`, `[step, unsupported]`, and `[step, opposed]` give `claim.supported`, `claim.unsupported`, and `claim.mixed`.
- A series with `T.alpha <= p < 2 · T.alpha` and `clear_one_sided` reads `supported` for the direction it runs in, and `unsupported` for `any` and for the other direction. `claim_p` halves `p` only for the matching direction, and `Fit.p` matches `2 · (1 − Φ(|z|))` on the 20 agreement series. On all 12,354 series in `data/v`, `p`, `z`, the interval, and the level are the same as before `clear_one_sided` existed.
- `field_test` gives the q-values of `bh` and needs both `q < T.field_q` and level `clear` (a hand-built list of five cells). On 100 no-trend 8 × 6 maps (seed 31), at most 0.10 have a cell clear after `field_test`. The rule it replaced fires on more than 0.15 of the same maps.
- `tools/error_audit.py` holds the error rates of the where map and the claim check. It fails if a no-trend map reads clear in more than 6% of runs, if "hotter and drier" reads `claim.supported` in more than 5% of runs with both parts or one part false, or in fewer than 52% with both true at 1.0 standard deviations per decade (`docs/05-claim-check.md`, `docs/07-where-map.md`).
- Measure how often `step` fires on a steady AR(1) trend at φ = 0.3. Write the measured rate into the board's step text. The claim desk measured about one time in six with its own test. Re-measured with this test on 1,000 series rising 3 units over 24 years (seed 11): 844 came out as real trends, and 0.192 of those were called a step. On 6,000 more series (seeds 12 to 17), 0.209 of 5,028 real trends were. `T.step_false_fire = 0.21` holds the number, and `test_step_rate_measured` fails if a re-measure drifts more than 0.02 from it. The one-sided claim test of step 9 admits weaker trends, and the step check calls 0.36 of the 672 it adds on seeds 12 to 17 a step. Before that rule, the two rates were 0.174 of 730 and 0.180 of 4,469, and the constant was 0.18. Before step 5 allowed for a jump they were 0.155 of 714 and 0.164 of 4,384, and the constant was 0.16.
- A mid-record jump of 3, 5, or 8 noise standard deviations on white noise at n = 24 reads as `step` or `supported` in at least 0.90 of 2,000 runs each. `tests/test_stats.py` measures 0.964, 0.973, and 0.981 (seed 12), and measured 0.923, 0.936, and 0.940 before the one-sided claim test. Twelve years at 0 then twelve at 5 reads `step`.
- `fmt(-0.01234)` returns "−0.012".

## Reference

`~/earth-buddy/js/stats.js` and `tests/stats.test.mjs` (claim test, Pettitt, step, BH). `~/earth-buddy/earth-buddy-analyst/earthbuddy/stats.py` and `tests/test_stats.py` (Sen, Mann-Kendall, STL, wording).
