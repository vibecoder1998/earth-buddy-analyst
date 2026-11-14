# Scan and audit strip

Two features that show the method is honest. **Scan** tests every variable for one region. The **audit strip** shows claims that were written down before any data existed, with their live verdicts. Priority P1. Estimate 1.5 hours.

## Scan

`ScanQ(region)`, where the region is a country or a place.

1. Run `trend_test` on every regional variable for the region, with direction `any`.
2. Run `bh` across all of them.
3. `Result.detail.rows` holds one row per variable: `{variable, slope_per_decade, lo, hi, p, q, survives, level}`. Sort the rows by p.
4. Headline: "{n} of 27 measures in {region} show a clear change after the check for many tests."
5. Each row has a **Try it as a claim** button. It opens the card with a `ClaimQ` for that variable and its observed direction, at `revision = 1`. Picking a claim after seeing its result is exactly the second look that the note warns about.

## Audit strip

`data/audit.json` holds 8 claims. The team wrote and committed them on 10 Nov 2026, before the 27-variable series existed. Commit `06844b4` in `~/earth-buddy` proves the order.

```python
class AuditClaim: id: str; quote: L10n; region: str; tests: list[Test]; window: None; known_before: bool
class Audit:      frozen: str; note: L10n; claims: list[AuditClaim]
```

| id | Region | Tests |
|---|---|---|
| khm-hotter | KHM | heat up (`known_before`: the old app already showed it) |
| khm-nights | KHM | tmin up |
| khm-dry-season | KHM | rain_dry down, soil down |
| pp-air | p.phnom-penh | aerosol up |
| delta-drying | p.mekong-delta | rain down, soil down |
| sahara-hotter | p.sahara | heat up, tmax up |
| amazon-drying | p.amazon | rain down, soil down, humid down |
| arctic-ice | p.arctic | seaice down |

`GET /api/audit` runs each claim through the claim check (`docs/05-claim-check.md`) with `via: "audit"`. The strip shows each quote and its verdict. A click opens the full board.

### Recorded verdicts

With the claim desk's statistics, 7 of 8 claims came out **not supported**, and arctic-ice came out **a real change, in one jump**. The claim desk recorded Cambodia's heat at −0.07 °C per decade, p 0.68 (`~/earth-buddy/docs/decisions.tsv`, row 24). That is a surprising result. Check it against the raw series before the pitch.

This spec changes the trend test (`docs/03-stats.md`). After the first run, compare every verdict with the list above. Record each change and its cause in the README. Never edit the frozen claims to change a verdict. Never add claims after seeing results.

### What to tell judges

- The claims are paraphrases of common claims, not quotations. Replace them with real headlines only through a new frozen file with a new date, committed before its verdicts are run.
- The original contract used a one-sided test. It changed to two-sided after the first verdicts were seen. The change only made verdicts stricter. The README says so.

## Case files

A case is a short story told as questions. It is an ordered list of prepared questions about one topic, such as fire and haze in Cambodia. The sidebar shows each case under **Case files**, above the audit strip. A click on a step runs its question through `POST /api/run` and adds a normal answer to the thread, in English or Khmer.

`data/cases.json` holds the cases. It holds questions, not data, so it names no source.

```python
class Bilingual: en: str; km: str          # both required and not blank
class CaseStep:  ask: Bilingual; question: Question
class Case:      id: str; title: Bilingual; note: Bilingual; steps: list[CaseStep]
```

`GET /api/cases` returns `{cases}`. Each step's question goes through the share-link reader, so a step and a share link of the same question carry the same question. The route runs nothing. The text ships in both languages, so the route takes no `lang`.

A new case is a data-only change. Add an entry to `data/cases.json`. It needs no code and no new question kind. Write its text with no numbers, because only code makes numbers. `tests/test_cases.py` checks this.

## Acceptance

- `ScanQ(Country KHM)` returns 27 rows sorted by p, and each row has a q-value.
- **Try it as a claim** opens a card with `revision = 1`, and its result shows the second-look note.
- `GET /api/audit` returns 8 verdicts with no network call.
- `GET /api/cases` returns Fire Watch Cambodia with 4 steps, and each step runs in English and Khmer with no network call.

## Reference

`~/earth-buddy/js/caseview.js` functions `viewScan` and `viewAsk` (the audit strip). `~/earth-buddy/data/audit.json`.
