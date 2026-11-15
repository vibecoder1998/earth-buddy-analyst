# Claim check

A person types a claim. The app tests each part against NASA data and shows an evidence board with one verdict. This is the headline feature for the pitch. Priority P0. Estimate 2 hours for the analysis. The board screen is in `docs/14-web-ui.md`.

## Input and output

`ClaimQ(region, tests, window)`, where `tests` has 1 to 8 entries with unique variables.

`Result.detail` for a claim:

```python
{
  "evidence": [ {
      "variable": VariableId, "direction": Direction,
      "series": Series, "fit": Fit | None,
      "outcome": Outcome,           # before the multiple-test check
      "p": float | None,            # the p the claim used: stats.claim_p, None with no fit
      "one_sided": bool,            # the part names a direction and its trend runs that way
      "survives": bool,             # q < T.fdr_q across this claim's tests
      "final": Outcome,             # after the check: a non-surviving supported, opposed or step becomes unsupported
      "break_year": int | None,     # Pettitt year when p < T.pettitt_p
      "caveat": "doubt" | None,     # the variable's doubt direction matches a clear trend
  } ],
  "counts": {"supported": int, "opposed": int, "step": int, "unsupported": int, "insufficient": int},
  "second_look": bool               # revision > 0
}
```

## Steps

1. Get every series with `get_series(region, variable, window)`.
2. Fit each with `trend_test`. Catch `TooShort` as `fit = None`.
3. Score each with `test_claim`, then `claim_verdict` across the claim with `claim_p` for each test (`docs/03-stats.md`). A part that names a direction is a one-sided test. A part that says `any` is two-sided.
4. Build the headline from the verdict key. Example for `claim.supported`: "**Supported.** Every part of this claim that could be measured shows a clear trend the way it says."
5. Tiles: the verdict, how many parts hold (`n_holding`), the years tested, and the region's cell count (or "one point").
6. Facts, per test: `<id>_change_per_decade`, `<id>_95pct_range`, `<id>_p`, `<id>_p_sides`, and `<id>_outcome`. `<id>_p` is the p the claim used. `<id>_p_sides` is `word.sides.one` ("one-sided") or `word.sides.two` ("two-sided"), and `word.slope` shows it, as in "one-sided p-value 0.031". Plus `region`, `years`, `verdict`, and `n_holding`, the parts that are `supported` or `step` after the check. The researcher text uses `n_holding` for the parts that hold.
7. Charts: one line chart per test, with the series, the Sen line, and the break year if any.
8. Method: the trend test, the false-discovery check, and the step check, each with one "did" and one "why" sentence.

## Rules

- The quote and `via` never change a number. A test proves it: two claims that differ only in `quote` and `via` give deep-equal results once those two fields are removed.
- **Second look.** When the person edits a claim after seeing its result, `revision` goes up by 1. A claim with `revision > 0` shows a note: "You changed this claim after seeing results. A second look at the same data finds patterns by chance more often." Opening the card and changing nothing keeps the revision.
- **Doubt.** When a variable's `doubt` direction matches a clear trend, the row shows its caveat. An example is a falling fire count, because MODIS Terra drifts after 2020.
- A constant series (snow in Cambodia, for example) is `insufficient`, not `unsupported`.
- **Support that needs the named direction says so.** When a supporting part is clear one-sided but its two-sided level is not `clear`, the result carries the note `note.one_sided`. The trend screen reads that record as "probably", and the note tells the person why the two screens differ.
- **A jump is support.** A part whose final outcome is `step` moved the way the claim says, in one jump. When the verdict is `claim.supported` and a part is a step, the result carries the note `note.jump`. It names those parts and says that the step check sees a jump in about `T.step_false_fire` of steady trends. The jump gets no verdict of its own beside a supported part, because that rate is too high to tell a jump from a steady trend.
- A claim on a `Point` uses live POWER data and its longer record. The method says so.

## Error rates

`tools/error_audit.py` runs "hotter and drier" on simulated records: heat with memory 0.17 claimed up, rain with memory 0.04 claimed down, 24 years, 4,000 runs per row. Trends are in standard deviations per decade. "Before" is the two-sided test with the old verdict order, where `[step, unsupported]` read `claim.step`.

| Truth | `claim.supported`, before | `claim.supported`, now | `claim.step`, now |
| --- | --- | --- | --- |
| Both parts false | 0.0% | 0.1% | 0.0% |
| Heat true at 1.0, rain false | 0.8% | 2.9% | 0.0% |
| Both true at 0.6 | 7.9% | 21.7% | 0.5% |
| Both true at 1.0 | 36.6% | 66.8% | 1.8% |

Before, the row with rain false read `claim.step` at level `clear` in 10.8% of runs, because a jump in heat beside a part with no trend was enough. Now `[step, unsupported]` is `claim.unsupported`, and that row reads `claim.step` in 0.0% of runs.

The one-sided test costs a little on a single part. A one-part claim "rising" on a series with no trend reads `supported` or `step` in 3.6%, 4.3%, 4.6%, 5.2%, and 6.3% of 4,000 runs at memory 0, 0.04, 0.17, 0.33, and 0.5. Before, it was 1.6%, 1.7%, 2.3%, 2.9%, and 3.3%.

## Acceptance

- "Cambodia is getting hotter and drier" returns a verdict with two evidence rows, heat and rain.
- An edited claim (`revision = 1`) shows the second-look note. The same claim at `revision = 0` does not.
- `ClaimQ(KHM, [snow any])` returns `claim.nothing`.
- `tools/error_audit.py` passes: "hotter and drier" reads `claim.supported` in at most 5% of runs with both parts false or with one part false, and in at least 52% with both true at 1.0.
- A part that names its direction carries `<id>_p_sides` "one-sided", and a `claim.supported` result with a step part carries `note.jump`.
- The verdict for each claim in `data/audit.json` matches the verdict recorded in `docs/12-scan-and-audit.md`, or the change is written down there with a reason.

## Reference

`~/earth-buddy/js/case.js` (`Case.build`) and `~/earth-buddy/js/caseview.js` (`viewBoard`).
