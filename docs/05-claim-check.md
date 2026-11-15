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
3. Score each with `test_claim`, then `claim_verdict` across the claim (`docs/03-stats.md`).
4. Build the headline from the verdict key. Example for `claim.supported`: "**Supported.** Every part of this claim that could be measured shows a clear trend the way it says."
5. Tiles: the verdict, how many parts match, the years tested, and the region's cell count (or "one point").
6. Facts, per test: `<id>_change_per_decade`, `<id>_95pct_range`, `<id>_p`, and `<id>_outcome`. Plus `region`, `years`, and `verdict`.
7. Charts: one line chart per test, with the series, the Sen line, and the break year if any.
8. Method: the trend test, the false-discovery check, and the step check, each with one "did" and one "why" sentence.

## Rules

- The quote and `via` never change a number. A test proves it: two claims that differ only in `quote` and `via` give deep-equal results once those two fields are removed.
- **Second look.** When the person edits a claim after seeing its result, `revision` goes up by 1. A claim with `revision > 0` shows a note: "You changed this claim after seeing results. A second look at the same data finds patterns by chance more often." Opening the card and changing nothing keeps the revision.
- **Doubt.** When a variable's `doubt` direction matches a clear trend, the row shows its caveat. An example is a falling fire count, because MODIS Terra drifts after 2020.
- A constant series (snow in Cambodia, for example) is `insufficient`, not `unsupported`.
- A claim on a `Point` uses live POWER data and its longer record. The method says so.

## Acceptance

- "Cambodia is getting hotter and drier" returns a verdict with two evidence rows, heat and rain.
- An edited claim (`revision = 1`) shows the second-look note. The same claim at `revision = 0` does not.
- `ClaimQ(KHM, [snow any])` returns `claim.nothing`.
- The verdict for each claim in `data/audit.json` matches the verdict recorded in `docs/12-scan-and-audit.md`, or the change is written down there with a reason.

## Reference

`~/earth-buddy/js/case.js` (`Case.build`) and `~/earth-buddy/js/caseview.js` (`viewBoard`).
