# Earth Buddy build plan

This plan builds the Earth Buddy app on the `eb-01` branch, one SPEC row per PR, so Cambodian students, teachers, and judges can type a claim or a question and get a verdict from NASA data by the 15 Nov 2026 23:59 submission. The program enforces two rules from `SPEC.md`. Code makes every number and every verdict, and the app answers every question with AI switched off. Every piece of data comes from NASA or a NASA partner and is cited from `data/sources.json`. The PRs run in this order. EB-01 to EB-09 are P0 and make the demo. EB-10 to EB-14 are P1. EB-15 to EB-17 are P2 and run only with time to spare.

## How to read this

One box is one unit of work. Every box names the evidence that checks it. A nested box is a sub-step of the box above it. Check a box only when its evidence exists, a file, a log line, a screenshot, a test run, or a SHA. The body is a how-to. The appendices explain and record.

The program runs `pstack/skills/poteto-mode/playbooks/autopilot-stack.md`. The root builds and verifies each PR and appends it to the stack. The operator lands every PR. EB-01 also needs the operator's deploy, because a deploy is an always-pause action.

Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

## Program checklist

### Arm the program

- [ ] State the protocol and this plan to the operator, then stop. Start execution only on the operator's explicit go.
- [x] The operator allowed copying the claim-desk data and keeping `fire`, on 14 Nov 2026. The trail records it.
- [ ] The operator confirms the Vercel project is linked, so EB-01 can deploy.
- [ ] Read these from trunk at program start. Re-read them at every tick.
  - [ ] `git show origin/main:pstack/skills/poteto-mode/playbooks/autopilot-stack.md`
  - [ ] `git show origin/main:pstack/skills/swarm/SKILL.md`
  - [ ] `git show origin/main:cursor-team-kit/skills/control-cli/SKILL.md`
  - [ ] `git show origin/main:cursor-team-kit/skills/control-ui/SKILL.md`
  - [ ] `git show origin/main:pstack/skills/poteto-mode/playbooks/opening-a-pr.md`
  - [ ] `git show origin/main:pstack/skills/principle-prove-it-works/SKILL.md`
  - [ ] `git show origin/main:pstack/skills/benchmark-checklist/SKILL.md`
  - [ ] Read `SPEC.md`, `CLAUDE.md`, and `docs/ARCHITECTURE.md` in this repo at every tick. They outrank this plan.
- [ ] On the operator's go, arm the audit tick as `/loop 1h` with the tick prompt below. Never leave the cadence to memory.
- [ ] Use this tick prompt, verbatim. "Re-read the execution playbook from trunk. Audit the operation against it and fix drift in this tick. Probe every active lane and judge progress by side effects only. Stand down a stuck lane and dispatch its replacement now. Then post a short status message to the operator in chat only when the audit found a tracked change that no earlier status message reported, such as a PR opened, a code-ready head, a round launched or closed, a verdict, a merge, a stuck agent and the action taken, a blocker added or cleared, or a decision only the operator can make. Name every such change and nothing else. Do not repeat a table, the merged list, or an unchanged blocker. If the audit found none, end the turn with no reply text. Either way, log this tick's row in your decision trail. The row names the items reported, or none."
- [ ] On the operator's hold or stand-down, send every owner a zero-writes order at once.

### Spawn owners

- [ ] Spawn one owner per PR with the full lifecycle the execution playbook names. Use `pstack:poteto-agent` on `opus high` (the `feature, refactoring` line).
- [ ] Follow this dependency graph. `CLAUDE.md` requires the SPEC table order, so start an owner only after the previous PR in the table is code-ready, and base each branch on the previous PR's branch.
  - [ ] EB-01 is first. It branches from `main`.
  - [ ] EB-02 after EB-01.
  - [ ] EB-03 after EB-02.
  - [ ] EB-04 after EB-03.
  - [ ] EB-05 after EB-04. It reads only `stats.py`, so a second owner drafts it now and rebases it on EB-04.
  - [ ] EB-06 after EB-05.
  - [ ] EB-07 after EB-06.
  - [ ] EB-08 after EB-07.
  - [ ] EB-09 after EB-08.
  - [ ] EB-10, EB-11, EB-12, EB-13, EB-14 after EB-09, in that order.
  - [ ] EB-15, EB-16, EB-17 after EB-14, in that order.
- [ ] Hold the file boundaries.
  - [ ] A kind PR (EB-07, EB-08, EB-11 to EB-13, EB-15 to EB-17) adds one `earthbuddy/analyses/<kind>.py`, one `ANALYSES` entry, its `words.EN` keys, its `PANELS` entry, and its tests. It edits nothing else in `analyses/`.
  - [ ] Only EB-05 and later stats additions edit `earthbuddy/stats.py`. Every new threshold goes into `T`.
  - [ ] No PR adds a data source, tile server, or geocoder that is not in `docs/16-data-sources.md`. Every new data file or live call names a `data/sources.json` id.
- [ ] Hold the review gate. EB-09, EB-10, EB-11, EB-12, EB-13, EB-14, EB-15, EB-16, EB-17 change an interaction. They wait for the operator's review in chat with screenshots and a video before merge.

### PR mechanics, for every PR

- [ ] Resolve the forge once. Default to `gh`; if `command -v origin` succeeds and Origin can resolve the repository, use `origin pr` for every PR operation. Record any fallback to `gh`. Never require `gt`.
- [ ] Push as `vibecoder1998`. SSH logs in as `dara-ling`, which cannot push. Run `GH_TOKEN=$(gh auth token --user vibecoder1998) git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push https://github.com/vibecoder1998/earth-buddy-analyst.git <branch>`. Run every `gh` command with the same `GH_TOKEN`.
- [ ] Open the PR ready, never draft, per **Opening a PR**. Use the run's built-in PR tool when it has one, else `origin pr create --status open --base <base-branch>` or `gh pr create --base <base-branch>` according to the resolved forge. A stack child targets its parent branch.
- [ ] Run `.venv/bin/python -m pytest -q` once before the PR-facing push. The repo has no linter or typechecker yet. Push with hooks on.
- [ ] Run `/deslop` before each commit and `/no-comments` before review.
- [ ] Triage every Bugbot and security-reviewer comment per `../references/bugbot-triage.md`.
- [ ] Rebase onto current trunk before the code-ready report and babysit. Keep that merge base in fix rounds. Rebase again only at merge prep, on a `git merge-tree` conflict with trunk, on a CI failure that comes from a change on trunk, or when a known concurrent change to the same files lands.

### Verdict and merge, for every PR

- [ ] A full swarm runs once, at the code-ready head. Another full swarm runs only for new behavior, a redesign, or a large new diff. A rebase, a merge-conflict resolution, or a minor fix gets a single verifier at the new head, and a wording-only change gets none. Run each full swarm per `pstack/skills/swarm/SKILL.md`. One gates lane. The ten live lanes from the PR's **Verify, live** block. The perf lane from its **Verify, perf** block. Two or more audit lanes, each with its own focus, that read the diff and the receipts and distrust the PR body. The root audits the receipts in the merge-ready report before the verdict.
- [ ] Judge every finding by the execution playbook's blocking rule. The verdict is clean when none blocks. A failure on trunk behavior in a lane marked `Regression lane against trunk.` is recorded against trunk and does not block the PR. A new head gets a fresh verdict, except for results that stay valid under the patch-id rule in `playbooks/shipping.md`.
- [ ] On a clean verdict, the root appends the PR to the stack and reports it merge-ready. The operator lands the stack bottom-up. A rebase that keeps the patch-id keeps the verdict, per `playbooks/shipping.md`.

### Boot recipe, for every live lane

Each live lane runs in its own git worktree at the PR head. Drive the HTTP API through `control-cli` from `cursor-team-kit`, and the page through `control-ui`.

- [ ] `git fetch origin <head-branch> && git checkout <head SHA>`.
- [ ] Run `uv venv -q --python 3.12 .venv && uv pip install -q --python .venv -r requirements.txt`. Then start the server with `EB_OFFLINE=1 EB_PORT=<8100 + lane> .venv/bin/python run.py`. A lane marked live drops `EB_OFFLINE`. Never set `EB_OFFLINE` and `VERCEL` together. Wait until `curl -s localhost:<port>/api/status` returns JSON.
- [ ] Send input only through `curl` under `control-cli` or the page under `control-ui`. Read-only diagnostics are `/api/status`, the server log, and the browser console.
- [ ] Save every screenshot to `/tmp/swarm-<pr-id>/worker-<n>/<slug>.png` and return the paths with the report. For an API lane, the screenshot is the terminal capture of the `curl` command and its output.

## Land the scaffold and deploy it (EB-01)

**Depends on.** None.

**Files.**

- [ ] Edit `vercel.json`.
- [ ] Create `tests/test_deploy.py`.

**Build.**

- [ ] Open the PR from the pushed `eb-01` branch (commit `53a7a78`, rebased onto the data-rule `main`) into `main`. Add `"includeFiles": "{data,web}/**"` to `vercel.json` so the function bundle carries `data/` and `web/`.

**You see.**

- [ ] `vercel --prod` prints a production URL, and `curl <url>/api/status` returns `{"ai_available": false, ...}`.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_deploy.py` gains `test_vercel_json_configures_main_function`, which loads `vercel.json` and asserts `maxDuration == 300`, `includeFiles` covers `data` and `web`, and no catch-all rewrite: the Vercel FastAPI preset routes every path to `app` in `main.py`. Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Trunk `main` has no app, so record that. Gate `GET /api/status` at head. Save `status.png`. Pass when it returns 200 with a boolean `ai_available`.
- [ ] Lane 2. `GET /` at head. Save `index.png`. Pass when the body holds `<title>Earth Buddy</title>` and the header `cache-control: no-store`.
- [ ] Lane 3. `GET /data/cache.sqlite` and `GET /data/catalog.json`. Save `data-hidden.png`. Pass when both return 404.
- [ ] Lane 4. `GET /styles.css`. Save `css.png`. Pass when it returns 200 with `text/css`.
- [ ] Lane 5. Start with `ANTHROPIC_API_KEY=x`. Save `ai-on.png`. Pass when `/api/status` shows `ai_available: true`.
- [ ] Lane 6. Start with `EB_OFFLINE=1` and `ANTHROPIC_API_KEY=x`. Save `offline.png`. Pass when `/api/status` shows `offline: true` and `ai_available: false`.
- [ ] Lane 7. Write `.env` with `EB_MODEL=from-file` and start with `EB_MODEL=from-env`. Save `env-wins.png`. Pass when `/api/status` shows `model: "from-env"`.
- [ ] Lane 8. Start with `EB_HOST=0.0.0.0 EB_PORT=8199`. Save `host-port.png`. Pass when `curl localhost:8199/api/status` answers.
- [ ] Lane 9. On the deployed URL, `GET /api/status`. Save `vercel-status.png`. Pass when it returns 200 within 10 s cold.
- [ ] Lane 10. On the deployed URL, `GET /`. Save `vercel-index.png`. Pass when the page title is `Earth Buddy`.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. The Vercel function bundle size in MB, and the cold `/api/status` latency on the deployed URL. Trunk has no deploy, so both are absolute budgets.
- [ ] Probe. Read the bundle size from the `vercel --prod` build log. Time `curl -w '%{time_total}'` on `/api/status` five times after a fresh deploy, interleaved with five calls to the local head server.
- [ ] Baseline. Record the local head latency first. The local site-packages measured 248 MB on 14 Nov 2026 with pandas and statsmodels included.
- [ ] Rule. Fail when the bundle exceeds Vercel's Python limit or the build log reports it too large. Fail when the cold deployed latency exceeds 10 s. If the bundle fails, drop `statsmodels` from `requirements.txt` (STL becomes `None`, per `docs/ARCHITECTURE.md`) and re-measure.

**Review gate.** None. EB-01 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up. The operator runs `vercel --prod`.

## Register every data source with its citation (EB-02)

**Depends on.** EB-01.

**Files.**

- [ ] Create `data/sources.json`, `tools/check_refs.py`, `tests/test_sources.py`.
- [ ] Edit `earthbuddy/types.py` (`Source`, `Series.sources`), `earthbuddy/catalog.py` (`ALLOWED_AGENCIES`, `sources()`), `earthbuddy/server.py` (`GET /api/sources`), `docs/ARCHITECTURE.md`.

**Build.**

- [ ] Write `data/sources.json` with the 14 entries in `docs/16-data-sources.md` "References", each with its full citation, DOI, and the POWER and GIBS acknowledgement texts.
- [ ] Replace `types.Source` with the registry shape in `docs/16`, and `Series.source` with `Series.sources: list[Source]`. Fix every caller in the scaffold.
- [ ] Add `ALLOWED_AGENCIES = {"NASA", "NASA/JAXA"}` and `catalog.sources()` to `catalog.py`. Add `GET /api/sources`.
- [ ] Write `tools/check_refs.py`, which resolves each DOI through `https://doi.org/api/handles/<doi>`, and its `--markdown` mode for the README section.
- [ ] Update `docs/ARCHITECTURE.md`. Change the `Source` shape, the local gazetteer in `geocode`, and `net` reaching only allowed hosts.

**You see.**

- [ ] `.venv/bin/python tools/check_refs.py` prints one `resolved` line per DOI and exits 0.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_sources.py` gains `test_every_agency_is_allowed`, `test_every_entry_has_citation_and_doi_or_acknowledgement`, and `test_no_url_outside_allowed_hosts` (greps `earthbuddy/` and `web/` for hosts outside `*.nasa.gov`, `nasa-power.s3.amazonaws.com`, `api.anthropic.com`). The variable and result checks in `docs/16` "Checks" join in EB-03 and EB-07. Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run `GET /api/status` at trunk and head. Save `status.png`. Pass when both return 200. Then gate `GET /api/sources` at head and pass when it returns 14 entries.
- [ ] Lane 2. Run `tools/check_refs.py`. Save `dois.png`. Pass when every DOI reports resolved.
- [ ] Lane 3. Run `tools/check_refs.py --markdown`. Save `markdown.png`. Pass when it prints one reference line per entry with a `https://doi.org/` link.
- [ ] Lane 4. Add an entry with `agency: "Natural Earth"` to a copy of the registry and run the tests against it. Save `bad-agency.png`. Pass when `test_every_agency_is_allowed` fails naming it.
- [ ] Lane 5. Add `https://nominatim.openstreetmap.org` to a scratch file in `earthbuddy/`. Save `bad-host.png`. Pass when `test_no_url_outside_allowed_hosts` fails naming the file.
- [ ] Lane 6. Search the repo for `naturalearth`, `nominatim`, `open-meteo`, and `openstreetmap` outside `docs/`. Save `grep.png`. Pass when nothing matches.
- [ ] Lane 7. Read the `power` entry. Save `power-cite.png`. Pass when its citation is the POWER referencing text from `docs/16`.
- [ ] Lane 8. Read the `gibs-bluemarble` entry. Save `gibs-cite.png`. Pass when its citation is the GIBS acknowledgement.
- [ ] Lane 9. Read `docs/ARCHITECTURE.md`. Save `arch.png`. Pass when the `Source` shape and the geocode row match `docs/16` and SPEC.
- [ ] Lane 10. Run the full `pytest`. Save `pytest.png`. Pass when it passes with no skipped test except those marked for EB-03.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. `/api/status` latency at trunk and head as the shared scenario, plus `/api/sources` latency at head.
- [ ] Probe. 20 interleaved `curl -w '%{time_total}'` calls of `/api/status` at trunk and head, then 20 calls of `/api/sources`.
- [ ] Baseline. Record trunk `/api/status` first.
- [ ] Rule. Fail when head `/api/status` is more than 10% slower or `/api/sources` exceeds 50 ms.

**Review gate.** None. EB-02 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Build the catalog, country series, and gazetteer from NASA data (EB-03)

**Depends on.** EB-02.

**Files.**

- [ ] Create `tools/build_catalog.py`, `tools/catalog.src.json`.
- [ ] Create `data/catalog.json`, `data/audit.json`, `data/gazetteer.json`, `data/countries.geojson`, `data/summary.json`, and `data/v/*.json` (27 files), all written by the tool.
- [ ] Edit `earthbuddy/catalog.py`.
- [ ] Create `tests/test_catalog.py`.

**Build.**

- [ ] Download the two SEDAC grids with the Earthdata login in `~/.netrc` into `tools/cache/` (git-ignored). They are `gpw-natid` (National Identifier Grid, 30 arc-second) and `gpw-adm-points` (Administrative Unit Center Points).
- [ ] Write `tools/build_catalog.py --adapt ~/earth-buddy-claimdesk-snapshot`, per `docs/01-catalog-and-data.md` "Build the data".
  - [ ] Copy the 27 variables, the 43 places, and `audit.json` from the snapshot. Rename `warmUp` to `warm_up` and `knownBefore` to `known_before`. Drop `gridded` and `icon`.
  - [ ] Keep only the `p.*` entries of each snapshot `data/v` file.
  - [ ] Rebuild every country series from the NASA POWER Zarr stores with `gpw-natid` cell ownership. A 1° cell belongs to the country owning most of its land pixels. Port the cell binning and the cos(latitude) mean from `~/earth-buddy-claimdesk-snapshot/tools/catalog_build.py` (`area_series` 163, `members` 144).
  - [ ] Write `countries.geojson` as the union of each country's 1° cells, with `{id: ISO3, name}`.
  - [ ] Write `gazetteer.json` with levels 0 to 2 from `gpw-adm-points`.
  - [ ] Write `tools/catalog.src.json` with the 11 capital names and the 25 province names. Resolve them against the gazetteer, and fail on a name with no match.
  - [ ] Set `point_param`, `first_year` (Appendix A, finding 3), `regional`, `season`, `per_day`, `aggregate: "max"` for `hottest`, `source.ids`, and `countries[*].name` as `{en, km}` with `km` from `~/earth-buddy-claimdesk-snapshot/js/names.km.js`.
  - [ ] Write `summary.json` once EB-05's `trend_test` exists. Until then, write `{}`.
- [ ] Fill the `catalog.py` bodies `raw`, `variable`, `name`, `centre`, `cells`, `find_region`, `group`, `regional_values`, `audit`.
- [ ] Add `--check`, which re-runs the acceptance checks below.

**You see.**

- [ ] `.venv/bin/python tools/build_catalog.py --check` prints `catalog ok: 27 variables, 43 places, <N> countries, 4 groups`, with N of at least 200. Record N in the README.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_catalog.py` gains `test_counts`, `test_series_lengths_match_years`, `test_khm_heat_within_0_2_of_snapshot`, `test_variable_source_ids_in_registry`, `test_cambodia_has_25_province_entries`, `test_find_region_phnom_penh_offline`, `test_khmer_falls_back_to_english`, and `test_summary_has_every_regional_variable` (skipped until EB-05). Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Trunk has no catalog, so record that. Gate `catalog.load()` at head. Save `load.png`. Pass when it prints 27, 43, at least 200, and 4.
- [ ] Lane 2. Run `tools/build_catalog.py --adapt` twice. Save `idempotent.png`. Pass when `git status --short data/` is empty after the second run.
- [ ] Lane 3. Compare the new KHM `heat` series with the snapshot's. Save `khm-heat.png`. Pass when every year is within 0.2 °C.
- [ ] Lane 4. `catalog.find_region("is it hot in phnom penh", "en")`. Save `find-pp.png`. Pass when it returns `Place(id="p.phnom-penh")`.
- [ ] Lane 5. `catalog.find_region("ukraine rain", "en")`. Save `find-ukr.png`. Pass when it returns `Country(iso3="UKR")`.
- [ ] Lane 6. `catalog.name(Country(iso3="KHM"), "km")`. Save `name-km.png`. Pass when it returns `កម្ពុជា`.
- [ ] Lane 7. `catalog.group("cambodia_provinces")`. Save `provinces.png`. Pass when it has 25 `Point` members, each with latitude 10 to 15 and longitude 102 to 108.
- [ ] Lane 8. Open `countries.geojson` and read Cambodia's feature. Save `khm-shape.png`. Pass when its cell count equals `countries.KHM.cells`.
- [ ] Lane 9. `catalog.variable("aerosol")`. Save `aerosol.png`. Pass when `point_param == "AOD_55_ADJ"`, `first_year == 2001`, and `source.ids` includes `ceres-syn1deg`.
- [ ] Lane 10. Search `data/` for `naturalearth`. Save `no-ne.png`. Pass when nothing matches.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Time of the first `catalog.load()` plus one `regional_values` call in a fresh process, and the full `--adapt` build time. Trunk has no catalog, so both are absolute budgets.
- [ ] Probe. 5 runs of the load at head, interleaved with 5 runs of `python -c "import earthbuddy"` as the floor. Then one timed `--adapt` run with a warm `tools/cache/`.
- [ ] Baseline. Record the `import earthbuddy` floor first.
- [ ] Rule. Fail when the load plus lookup exceeds the floor by more than 300 ms, or the warm build exceeds 30 minutes.

**Review gate.** None. EB-03 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Fetch series from files and NASA POWER, and find places offline (EB-04)

**Depends on.** EB-03.

**Files.**

- [ ] Edit `earthbuddy/net.py`, `earthbuddy/power.py`, `earthbuddy/fixtures.py`, `earthbuddy/series.py`, `earthbuddy/geocode.py`, `earthbuddy/server.py`.
- [ ] Create `tests/test_series.py`, `tests/test_net.py`, `tests/test_geocode.py`.

**Build.**

- [ ] Fill `net.get_json` per its pseudocode, with retry on 429, 5xx, and transport errors, and an immediate raise on other 4xx.
- [ ] Fill `power.point`. POWER publishes 2025 in full (Appendix A, finding 4), so the 422 retry is a fallback.
- [ ] Fill `fixtures.handler`. Seed by `zlib.crc32(url)`, and give `T2M` a clear rise and `PRECTOTCORR` a small fall.
- [ ] Fill `series.get_series` and `series.annualise`, including `season`, `per_day`, and `max`. Every `Series` carries its registry `sources`, and `power` when read through POWER.
- [ ] Fill `geocode.search` with no network, per `docs/02-series.md` "Geocoding". Coordinates first, then catalog places, countries, and `gazetteer.json`. Return at most 5, exact matches first, provinces before districts.
- [ ] Make `server.py` refuse to start when both `EB_OFFLINE=1` and `VERCEL` are set.

**You see.**

- [ ] `EB_OFFLINE=1 .venv/bin/python -c "from earthbuddy import series, types; print(len(series.get_series(types.Point(lat=11.55, lon=104.92, name='Phnom Penh'), 'heat', None).years))"` prints `45`.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_series.py` gains `test_country_reads_file_with_no_network`, `test_point_offline_keeps_monthly`, `test_constant_one_mm_per_day_gives_365_or_366`, `test_rain_dry_counts_nov_dec_toward_next_year`, `test_window_outside_record_is_400_window`, `test_no_point_param_is_400`, and `test_every_series_has_registry_sources`.
- [ ] `tests/test_net.py` gains `test_second_point_call_reads_cache`, `test_503_retries_then_raises_with_url`, and `test_422_raises_at_once`.
- [ ] `tests/test_geocode.py` gains `test_coordinates_parse`, `test_battambang_offline`, `test_unknown_name_returns_empty`, and `test_offline_on_vercel_refuses_to_start`.
- [ ] Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Trunk has no series layer, so record that. Gate `get_series(Country KHM, heat)` at head. Save `khm.png`. Pass when it returns 24 values and the transport counter stays 0.
- [ ] Lane 2. Live, without `EB_OFFLINE`. `get_series(Point Phnom Penh, heat)`. Save `live-pp.png`. Pass when it returns years 1981 to 2025, `cached` is false, and `sources` holds `power` and a MERRA-2 entry.
- [ ] Lane 3. Live. Repeat lane 2 in the same process. Save `live-cached.png`. Pass when `cached` is true and no HTTP request leaves the process.
- [ ] Lane 4. Live. `get_series(Point Phnom Penh, rain)`. Save `live-rain.png`. Pass when every yearly value lies between 800 and 3,000 mm.
- [ ] Lane 5. Live. `get_series(Point Phnom Penh, aerosol)`. Save `live-aod.png`. Pass when the first year is 2001.
- [ ] Lane 6. Offline. A point at latitude 89, longitude 0, for `heat`. Save `pole.png`. Pass when it returns a full series.
- [ ] Lane 7. `geocode.search("Battambang")` with the network blocked. Save `battambang.png`. Pass when the first result is "Battambang, Cambodia" within 0.5° of 13.1 N, 103.2 E.
- [ ] Lane 8. `geocode.search("Xyzzyville")`. Save `no-match.png`. Pass when it returns an empty list with no request.
- [ ] Lane 9. Point the transport at a stub that answers 503 four times. Save `retry.png`. Pass when `DataSourceError.url` names the POWER URL and the stub saw 4 calls.
- [ ] Lane 10. Start the server with `EB_OFFLINE=1 VERCEL=1`. Save `refuse.png`. Pass when it exits with an error naming the rule.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Wall time of a cold live `get_series(Point, heat)`, of the same call from the cache, and of `geocode.search("Battambang")`. Trunk has none of these, so all are absolute budgets.
- [ ] Probe. Alternate a cold call (fresh `EB_DB`) and a warm call, 5 times each, against live POWER. Then 20 geocode calls.
- [ ] Baseline. Record the warm time first.
- [ ] Rule. Fail when a warm call exceeds 50 ms, a cold call exceeds 30 s, or a geocode call exceeds 50 ms.

**Review gate.** None. EB-04 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Build the statistics engine with a memory-corrected trend test (EB-05)

**Depends on.** EB-04.

**Files.**

- [ ] Edit `earthbuddy/stats.py`, `earthbuddy/words.py` (`number_tokens` only).
- [ ] Edit `tools/build_catalog.py` to write `data/summary.json`, and edit `data/summary.json`.
- [ ] Create `tests/test_stats.py`.
- [ ] Edit `docs/03-stats.md`.

**Build.**

- [ ] Fill every `stats.py` body. For step 5 of `trend_test`, use the claim desk's variance-inflation correction, not Hamed-Rao. Estimate φ as `r + (T.vif_a + T.vif_b · r) / n` with `T.vif_a = 3` and `T.vif_b = 6`, clipped to `[0, T.vif_cap]` with `T.vif_cap = 0.9`. Put the inflation table in `T.vif_table`.
- [ ] Record the measured step false-fire rate in `docs/03-stats.md` and in `words.EN["claim.step.headline"]`'s companion step text.
- [ ] Update `docs/03-stats.md` step 5 to the corrected φ formula with the numbers from Appendix A, finding 1.
- [ ] Regenerate `data/summary.json`.

**You see.**

- [ ] `.venv/bin/python -m pytest -q tests/test_stats.py -k ar1` prints the three false-positive rates, each at most 0.08.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_stats.py` gains the 8 checks in `docs/03-stats.md` "Acceptance", named `test_sen_recovers_known_slope`, `test_agrees_with_pymannkendall_and_scipy`, `test_ar1_false_positive_at_most_0_08` (2,000 runs per φ, seeded), `test_white_noise_at_most_7_percent`, `test_bh_worked_example`, `test_claim_verdict_all_six_keys`, `test_step_rate_measured`, and `test_fmt_minus_sign`. Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Trunk has no statistics, so record that. Gate `trend_test` on the KHM heat series at head. Save `khm-heat.png`. Pass when it returns a `Fit` with n 24 and a finite p.
- [ ] Lane 2. Compare KHM heat with the claim desk's recorded −0.07 °C per decade, p 0.68 (`docs/12-scan-and-audit.md`). Save `khm-vs-desk.png`. Pass when the slope is within 0.02 of −0.07, or the lane records the difference and its cause.
- [ ] Lane 3. `trend_test` on 7 years. Save `too-short-7.png`. Pass when it raises `TooShort` with `field == "window"`.
- [ ] Lane 4. `trend_test` on 9 years. Save `too-short-9.png`. Pass when `level == "too_short"`.
- [ ] Lane 5. `trend_test` on a constant series. Save `constant.png`. Pass when `p == 1`, `constant` is true, and the level is `unclear`.
- [ ] Lane 6. `bh([0.01, 0.04, 0.03, 0.005])`. Save `bh.png`. Pass when it returns `[0.02, 0.04, 0.04, 0.02]`.
- [ ] Lane 7. `pettitt` on a series with a jump of 3 swings at 2012. Save `pettitt.png`. Pass when it returns 2012 or 2013 with p below 0.05, and `is_step` is true.
- [ ] Lane 8. `fmt` on −0.01234, 1234.5, and 0.000012. Save `fmt.png`. Pass when it returns `−0.012`, `1200`, and `0.00001`, each with a U+2212 minus where negative.
- [ ] Lane 9. `stl` on 45 years of offline Phnom Penh `heat` months. Save `stl.png`. Pass when the trend, seasonal, and residual shares sum to 1 within 0.01.
- [ ] Lane 10. `summary.json` for `heat`. Save `summary.png`. Pass when every country with a series has `trend_per_decade`, `p`, `q`, and `direction`.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Mean time of one `trend_test` on a 24-year series, and of a scan's 27 tests plus `bh`. Trunk has no statistics, so both are absolute budgets.
- [ ] Probe. `timeit` with 200 repeats on the KHM series at head, interleaved with 200 repeats of `numpy.polyfit` on the same series as the floor.
- [ ] Baseline. Record the `polyfit` floor first.
- [ ] Rule. Fail when one `trend_test` exceeds 5 ms or the 27-test scan exceeds 150 ms.

**Review gate.** None. EB-05 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Read a sentence into a question with keywords or AI (EB-06)

**Depends on.** EB-05.

**Files.**

- [ ] Edit `earthbuddy/reader.py`, `earthbuddy/net.py` (`ask_model` body), `earthbuddy/server.py`.
- [ ] Create `tests/test_reader.py`.

**Build.**

- [ ] Fill `guard` and the 13 `FILL` entries.
- [ ] Fill `read_keywords`. Port the year patterns and Khmer digit handling from `~/earth-buddy-claimdesk-snapshot/js/intake.js` lines 58 to 87.
- [ ] Fill `read_ai`, `schema`, and `net.ask_model`, using the call in `docs/04-reader.md`.
- [ ] Fill `read`, `reread`, and `question_from`.
- [ ] Add `POST /api/read` and `GET /api/geocode` to `server.py`.

**You see.**

- [ ] `curl -s localhost:8000/api/read -d '{"text":"Cambodia is getting hotter and drier","lang":"en","ai":false}' -H 'content-type: application/json'` returns a `question` with `kind: "claim"`, region `KHM`, and tests `heat up` and `rain down`.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_reader.py` gains every check in `docs/04-reader.md` "Acceptance", named `test_demo_sentences_parse_without_edits` (5 sentences), `test_hotter_and_drier`, `test_ukraine_is_not_rain`, `test_guard_drops_digit_lead_unknown_variable_ninth_test_and_clamps_revision`, `test_bad_model_json_falls_back_to_keywords`, and `test_ai_and_keyword_drafts_give_same_question`. Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Trunk has no `/api/read`, so record that. Gate demo sentence 1 at head with AI off. Save `demo1.png`. Pass when it returns the claim in **You see**.
- [ ] Lane 2. Demo sentence 2, "How is rain changing in Siem Reap?". Save `demo2.png`. Pass when `kind` is `trend`, the variable is `rain`, and the region resolves to Siem Reap.
- [ ] Lane 3. Demo sentence 3, "Where around Phnom Penh is it warming?". Save `demo3.png`. Pass when `kind` is `where` and `point` is near 11.5 N, 104.9 E.
- [ ] Lane 4. Demo sentence 4, "Which Southeast Asian capital is warming fastest?". Save `demo4.png`. Pass when `kind` is `rank` and `among` is `southeast_asia_capitals`. `question` stays null until EB-13, and `missing` is empty.
- [ ] Lane 5. Demo sentence 5, "What is changing in the Mekong Delta?". Save `demo5.png`. Pass when `kind` is `scan` and the region is `p.mekong-delta`.
- [ ] Lane 6. A 601-character text. Save `too-long.png`. Pass when it returns 400 with `field: "text"`.
- [ ] Lane 7. Live, with a real `ANTHROPIC_API_KEY` and `ai: true`, demo sentence 1. Save `ai-demo1.png`. Pass when `via` is `ai`, `ai_failed` is false, and the question equals lane 1's.
- [ ] Lane 8. `ai: true` with an invalid key. Save `ai-fail.png`. Pass when `ai_failed` is true and the keyword question comes back.
- [ ] Lane 9. Khmer text "កម្ពុជាកាន់តែក្តៅឡើង". Save `km.png`. Pass when it returns a claim on `KHM` with `heat up`.
- [ ] Lane 10. `POST /api/run`-shaped body through `reread` with an unknown variable and revision 500. Save `guard.png`. Pass when the variable is dropped and `revision == 99`.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Server time of `/api/read` with AI off, and with AI on against the live model. Trunk has no reader, so both are absolute budgets.
- [ ] Probe. 10 `curl -w '%{time_total}'` calls per mode on demo sentence 1, alternating modes.
- [ ] Baseline. Record AI off first.
- [ ] Rule. Fail when AI off exceeds 100 ms, or AI on exceeds the 10 s timeout on any call.

**Review gate.** None. EB-06 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Test a claim and build its evidence board (EB-07)

**Depends on.** EB-06.

**Files.**

- [ ] Edit `earthbuddy/analyses/claim.py`, `earthbuddy/analyses/base.py`, `earthbuddy/words.py`, `earthbuddy/server.py`.
- [ ] Create `tests/test_claim.py`, `tests/test_words.py`, `tests/test_ai_off.py`.

**Build.**

- [ ] Fill `claim.claim` per its pseudocode, plus `base.per_decade` and `base.line_chart`.
- [ ] Fill `Words.headline`, `Words.tile`, `Words.step`, `Words.template`, and `number_tokens`. Add every `claim.*` key to `words.EN`, with student, policymaker, and researcher templates.
- [ ] Add `POST /api/run` and `GET /api/catalog` (with `kinds`) to `server.py`.

**You see.**

- [ ] `POST /api/run` with the claim from EB-06 returns a `Result` with two evidence rows (`heat`, `rain`), a headline, and 4 tiles.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_claim.py` gains `test_hotter_and_drier_has_two_rows`, `test_revision_1_shows_second_look`, `test_revision_0_does_not`, `test_snow_in_cambodia_is_nothing`, and `test_detail_round_trips_through_claim_detail`.
- [ ] `tests/test_words.py` gains `test_every_declared_verdict_has_headline_and_student_templates`.
- [ ] `tests/test_ai_off.py` gains `test_quote_and_via_never_change_a_result`. A stubbed model and the keyword reader give `Result`s that compare equal.
- [ ] Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Trunk has no `/api/run`, so record that. Gate demo sentence 1 through `/api/read` then `/api/run` at head. Save `claim-khm.png`. Pass when the result has 2 evidence rows and a verdict key from `claim.VERDICTS`.
- [ ] Lane 2. The same claim with `revision: 1`. Save `second-look.png`. Pass when `notes[0]` is the second-look note.
- [ ] Lane 3. `ClaimQ(KHM, [snow any])`. Save `nothing.png`. Pass when the verdict key is `claim.nothing`.
- [ ] Lane 4. A claim of 8 tests on `KHM`. Save `eight.png`. Pass when 8 rows return and each row's `survives` matches `q < 0.10` from its own BH q.
- [ ] Lane 5. `fire down` on a country where fire falls clearly. Save `doubt.png`. Pass when the row's `caveat` is `doubt` and a caveat note shows.
- [ ] Lane 6. A claim on the Point Phnom Penh, offline. Save `point-claim.png`. Pass when the method has the live-record step and the years start in 1981.
- [ ] Lane 7. A claim with `window: [2001, 2005]`, sent through `/api/run`. Save `window-short.png`. Pass when `guard` drops the window, because it is shorter than `T.reliable`, and the result covers 2001 to 2024.
- [ ] Lane 8. A share-link body with an unknown region id. Save `bad-region.png`. Pass when it returns 400 with `field: "region"`.
- [ ] Lane 9. `GET /api/catalog`. Save `catalog.png`. Pass when `kinds.claim.fields` lists `region`, `tests`, `window` with `required` true, true, false.
- [ ] Lane 10. Every number in `facts` for lane 1. Save `facts.png`. Pass when every value is a string, int, bool, or null.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. `/api/run` server time for the two-test KHM claim. Trunk has no route, so this is an absolute budget.
- [ ] Probe. 20 `curl -w '%{time_total}'` calls at head, alternating with 20 calls to `/api/status` as the floor.
- [ ] Baseline. Record the `/api/status` floor first.
- [ ] Rule. Fail when the claim's median exceeds the floor by more than 300 ms.

**Review gate.** None. EB-07 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Answer how one variable is changing at one place (EB-08)

**Depends on.** EB-07.

**Files.**

- [ ] Edit `earthbuddy/analyses/trend.py`, `earthbuddy/words.py`.
- [ ] Create `tests/test_trend.py`.

**Build.**

- [ ] Fill `trend.trend` per its pseudocode and `docs/06-trend.md` steps 1 to 8. Add every `trend.*` key to `words.EN`.

**You see.**

- [ ] With `EB_OFFLINE=1`, `POST /api/run` with `TrendQ(Point Phnom Penh, heat)` returns the headline "Phnom Penh's average air temperature is **clearly rising** ..." and 5 charts.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_trend.py` gains `test_point_offline_clear_rise_with_stl_and_cycle`, `test_country_has_no_decomposition_and_no_network`, `test_nine_years_is_too_short_headline`, `test_seven_years_is_400_window`, and `test_facts_cover_docs_06_step_6`. Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run the EB-07 claim scenario at trunk and head. Save `claim-still.png`. Pass when both return the same verdict. Then gate `TrendQ(Point Phnom Penh, heat)` at head and pass when the level is `clear`.
- [ ] Lane 2. Live. `TrendQ(Point Phnom Penh, heat)`. Save `live-trend.png`. Pass when the period is 1981 to 2025 and the facts hold `peak_month`.
- [ ] Lane 3. `TrendQ(Country KHM, heat)`. Save `country-trend.png`. Pass when `decomposition` is null and the transport counter is 0.
- [ ] Lane 4. `TrendQ(Place p.siem-reap, rain)`. Save `siem-reap.png`. Pass when `percent_change` is in facts, since `rain` is relative.
- [ ] Lane 5. A 9-year window. Save `nine.png`. Pass when the headline is "**Too few years** to judge."
- [ ] Lane 6. A 7-year window. Save `seven.png`. Pass when it returns 400 with `field: "window"`.
- [ ] Lane 7. An unclear series, for example `TrendQ(KHM, wind)`. Save `unclear.png`. Pass when the method includes the step saying no clear change does not mean nothing is happening.
- [ ] Lane 8. Live. `TrendQ(Point Phnom Penh, aerosol)`. Save `aod.png`. Pass when the period starts in 2001.
- [ ] Lane 9. Demo sentence 2 through `/api/read` then `/api/run`. Save `demo2.png`. Pass when a trend result returns with no card edits.
- [ ] Lane 10. `TrendQ(KHM, fire)` on a point. Save `no-point.png`. Pass when it returns 400 with `field: "variable"`.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. `/api/run` server time for the cached Point trend, which includes STL. Trunk has no trend kind, so this is an absolute budget, and the EB-07 claim time is the shared scenario.
- [ ] Probe. 20 calls per scenario, alternating the trunk claim, the head claim, and the head trend.
- [ ] Baseline. Record the trunk claim time first.
- [ ] Rule. Fail when the head claim is more than 10% slower than trunk, or the cached trend median exceeds 1.5 s.

**Review gate.** None. EB-08 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Build the ask, card, and result screens with share links (EB-09)

**Depends on.** EB-08.

**Files.**

- [ ] Edit `web/index.html`, `web/styles.css`.
- [ ] Create `web/app.js`, `web/charts.js`, `web/i18n.js`.
- [ ] Create `web/vendor/fonts/` from `~/earth-buddy-claimdesk-snapshot/vendor/fonts/`.
- [ ] Create `tests/test_web_sync.py`.

**Build.**

- [ ] Write `app.js` with `S`, `VIEWS`, `EDITORS` keyed by field name, `PANELS` with `claim` and `trend`, the `call` sequence guard, and `#q=` share links, per `docs/14-web-ui.md` and `docs/ARCHITECTURE.md` "Frontend".
- [ ] Write `charts.js` with `CHARTS` for `line`, `bars`, `scatter`, `cells`, and `intervals`, each with a text alternative.
- [ ] Write `i18n.js` with `EN` and an empty `KM`, inside `/*json*/ ... /*end*/` markers.
- [ ] Route every interpolated value through `esc()` or `t()`.

**You see.**

- [ ] Clicking the chip "Cambodia is getting hotter and drier" shows the card. Clicking **Run** shows the verdict card, 4 tiles, and 2 line charts.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_web_sync.py` gains `test_editors_cover_every_field_name`, `test_panels_are_known_kinds`, `test_charts_equal_chart_types`, `test_every_t_key_exists_in_en`, and `test_no_unused_en_key`. Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Trunk shows an empty page, so record that. Gate demo chip 1 then **Run** at head. Save `demo1.png`. Pass when the verdict card and 2 charts render.
- [ ] Lane 2. Demo chip 2 then **Run**. Save `demo2.png`. Pass when a trend result with STL tabs renders.
- [ ] Lane 3. Run a claim, click **Edit**, change a direction, run again. Save `second-look.png`. Pass when the second-look note shows.
- [ ] Lane 4. Click **Share**, open the copied link in a new tab. Save `share.png`. Pass when the same headline shows.
- [ ] Lane 5. Open `#q=garbage`. Save `bad-link.png`. Pass when the ask view shows "This link could not be read".
- [ ] Lane 6. Resize to 375 px wide. Save `narrow.png`. Pass when `document.documentElement.scrollWidth <= 375`.
- [ ] Lane 7. Keyboard only. Tab from the ask box to **Run** and to the result tabs. Save `keyboard.png`. Pass when every stop shows a visible focus ring.
- [ ] Lane 8. Type `<img src=x onerror=alert(1)>` as a place name. Save `xss.png`. Pass when no script runs and the text shows escaped.
- [ ] Lane 9. Clear the region on the card. Save `missing.png`. Pass when **Run** is disabled and names the missing field.
- [ ] Lane 10. Switch the AI toggle on with no key. Save `ai-disabled.png`. Pass when the toggle is disabled and its label states the Anthropic notice.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Time from the **Run** click to the verdict card painting, for demo sentence 1. Trunk has no result view, so this is an absolute budget, plus the end-to-end time from page load to the verdict.
- [ ] Probe. `performance.now()` marks around the click and the verdict render, 10 runs at head, interleaved with 10 page loads as the floor.
- [ ] Baseline. Record the page-load floor first.
- [ ] Rule. Fail when click-to-verdict exceeds 1 s or page-load-to-interactive exceeds 2 s on the local server.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 1, 2, 3, and 6 screenshots into `docs/media/EB-09-review-<slug>.png`.
- [ ] Record a 30 to 60 second video of the change on a lane VM. Save it as `docs/media/EB-09-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Explain a result in plain words with every number checked (EB-10)

**Depends on.** EB-09.

**Files.**

- [ ] Edit `earthbuddy/explainer.py`, `earthbuddy/server.py`, `earthbuddy/words.py`, `web/app.js`.
- [ ] Create `tests/test_explainer.py`.

**Build.**

- [ ] Fill `explain` and `numbers_ok` per `docs/13-explainer.md`. Add `POST /api/explain`.
- [ ] Show the short answer, a **More** toggle, and the audience switch under the verdict.

**You see.**

- [ ] The KHM claim result shows a two-sentence student explanation with no numbers, and `via: "template"` with AI off.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_explainer.py` gains `test_every_verdict_key_has_an_english_student_template`, `test_rejects_0_3_when_facts_hold_0_28`, `test_accepts_0_28`, `test_invented_number_falls_back_to_template`, and `test_ai_off_makes_no_model_call`. Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run demo chip 1 at trunk and head. Save `explain-demo1.png`. Pass when both show the same verdict card and head adds the explanation below it.
- [ ] Lane 2. Switch the audience to researcher. Save `researcher.png`. Pass when the text names the slope, the 95% range, the test, and p.
- [ ] Lane 3. Live with a key and AI on. Save `ai-text.png`. Pass when `via` is `ai` and every number in the text appears in `facts`.
- [ ] Lane 4. Stub the model to return "about 0.3 °C". Save `rejected.png`. Pass when the screen shows the template and the server log holds the rejected text.
- [ ] Lane 5. Khmer digits in a stubbed reply ("០.២៨"). Save `km-digits.png`. Pass when the check accepts it against facts "0.28".
- [ ] Lane 6. Click **More**. Save `more.png`. Pass when 3 to 5 sentences show.
- [ ] Lane 7. A trend result explanation. Save `trend-explain.png`. Pass when the text never calls an unclear trend "nothing happening".
- [ ] Lane 8. A slow model (stub sleeps 15 s). Save `slow.png`. Pass when the verdict shows at once and the template text replaces the spinner.
- [ ] Lane 9. Post a forged `Result` with an extra fact. Save `forged.png`. Pass when the response is limited to that request and no server state changes.
- [ ] Lane 10. Every verdict key across claim and trend, rendered with AI off. Save `all-keys.png`. Pass when none shows a raw `{placeholder}`.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Click-to-verdict time (the EB-09 metric) at trunk and head, plus the explanation's arrival time at head.
- [ ] Probe. 10 interleaved runs of demo chip 1 at trunk and head.
- [ ] Baseline. Record trunk click-to-verdict first.
- [ ] Rule. Fail when head click-to-verdict is more than 10% slower than trunk, or the template explanation arrives more than 300 ms after the verdict.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 1, 2, and 3 screenshots into `docs/media/EB-10-review-<slug>.png`.
- [ ] Record a 30 to 60 second video of the change on a lane VM. Save it as `docs/media/EB-10-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Scan every measure for a region and show the frozen audit claims (EB-11)

**Depends on.** EB-10.

**Files.**

- [ ] Create `earthbuddy/analyses/scan.py`.
- [ ] Edit `earthbuddy/analyses/__init__.py`, `earthbuddy/words.py`, `earthbuddy/server.py`, `web/app.js`.
- [ ] Create `tests/test_scan.py`, `tests/test_audit.py`.
- [ ] Edit `README.md`.

**Build.**

- [ ] Add `scan` with `cue_rank=6` and its cues. Rows sort by p and each carries q.
- [ ] Add `GET /api/audit`, which runs each frozen claim through `analyses.run` with `via: "audit"`.
- [ ] Add the scan panel with **Try it as a claim**, which opens a card at `revision = 1`, and the audit strip on the ask view.
- [ ] Write each audit verdict that differs from `docs/12-scan-and-audit.md` "Recorded verdicts", with its cause, into `README.md`.

**You see.**

- [ ] Demo chip 5 shows "N of 27 measures in Mekong Delta show a clear change after the check for many tests."

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_scan.py` gains `test_khm_scan_has_27_rows_sorted_by_p_with_q`.
- [ ] `tests/test_audit.py` gains `test_audit_returns_8_verdicts_with_no_network` and `test_frozen_claims_unchanged` (a hash of `data/audit.json` claims).
- [ ] Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run demo chip 1 at trunk and head. Save `claim-still.png`. Pass when both show the same verdict. Then gate demo chip 5 at head and pass when 27 scan rows render.
- [ ] Lane 2. Click **Try it as a claim** on the top scan row, then **Run**. Save `try-claim.png`. Pass when the second-look note shows.
- [ ] Lane 3. Load the ask view. Save `audit-strip.png`. Pass when the strip shows 8 quotes with a verdict each.
- [ ] Lane 4. Click the `arctic-ice` audit item. Save `arctic.png`. Pass when its full board opens.
- [ ] Lane 5. `GET /api/audit` with the network blocked. Save `audit-offline.png`. Pass when 8 verdicts return.
- [ ] Lane 6. `ScanQ(Place p.sahara)`. Save `sahara.png`. Pass when the rows skip variables with no series and say why.
- [ ] Lane 7. `ScanQ(Point ...)` from a share link. Save `scan-point.png`. Pass when it returns 400 with `field: "region"`.
- [ ] Lane 8. The scan headline count. Save `count.png`. Pass when N equals the number of rows with `survives` true.
- [ ] Lane 9. Khmer scan sentence "អ្វីកំពុងផ្លាស់ប្តូរនៅដីសណ្តទន្លេមេគង្គ". Save `km-scan.png`. Pass when `kind` is `scan`.
- [ ] Lane 10. Compare each audit verdict with `README.md`. Save `audit-readme.png`. Pass when every changed verdict has a written cause.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. `/api/audit` server time cold, and the KHM scan's `/api/run` time. Trunk has neither, so both are absolute budgets, with the EB-07 claim time as the shared scenario.
- [ ] Probe. 10 interleaved calls each of the trunk claim, the head claim, the audit, and the scan.
- [ ] Baseline. Record the trunk claim first.
- [ ] Rule. Fail when the head claim is more than 10% slower than trunk, the cold audit exceeds 2 s, or the scan exceeds 1 s.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 1, 2, and 3 screenshots into `docs/media/EB-11-review-<slug>.png`.
- [ ] Record a 30 to 60 second video of the change on a lane VM. Save it as `docs/media/EB-11-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Show where around a place a variable is changing on the map (EB-12)

**Depends on.** EB-11.

**Files.**

- [ ] Create `earthbuddy/analyses/where.py`.
- [ ] Edit `earthbuddy/analyses/__init__.py`, `earthbuddy/power.py` (`grid`), `earthbuddy/series.py` (`get_grid`), `earthbuddy/fixtures.py`, `earthbuddy/words.py`, `earthbuddy/stats.py` (`T` additions), `earthbuddy/server.py`, `web/app.js`, `web/index.html`.
- [ ] Create `web/map.js` and `web/vendor/maplibre-gl/` from `~/earth-buddy-claimdesk-snapshot/vendor/maplibre-gl/`.
- [ ] Create `tests/test_where.py`.

**Build.**

- [ ] Fill `power.grid` and `series.get_grid`. Add `where` per `docs/07-where-map.md` with `cue_rank=5`.
- [ ] Serve `/data/countries.geojson` and `/data/summary.json` through two explicit routes.
- [ ] Write `map.js`. The background is the NASA GIBS `BlueMarble_ShadedRelief_Bathymetry` layer with the GIBS acknowledgement, and no other tile source. Idle shows each country as its 1° cells, coloured by `summary.json` (grey when not clear after BH). A result flies to the region. A `Cells` chart draws squares. A map click becomes a `Point`.

**You see.**

- [ ] Demo chip 3 paints a grid of coloured squares around Phnom Penh and the headline names the strongest direction.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_where.py` gains `test_offline_cells_cover_box_and_counts_sum`, `test_latitude_89_clamps_and_returns_cells`, and `test_variable_without_point_param_is_400`. Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run demo chip 1 at trunk and head. Save `claim-still.png`. Pass when both show the same verdict. Then gate demo chip 3 at head and pass when the cells layer renders.
- [ ] Lane 2. Load the page idle. Save `idle-map.png`. Pass when the GIBS background and its acknowledgement show, countries are coloured for `heat`, and the network panel shows no tile request outside `gibs.earthdata.nasa.gov`.
- [ ] Lane 3. Click Cambodia on the map. Save `click-khm.png`. Pass when a card opens with `TrendQ(KHM, heat)`.
- [ ] Lane 4. Live. Demo chip 3. Save `live-where.png`. Pass when the cells cover a 4° box and `counts.total` equals the number of squares.
- [ ] Lane 5. A `where` at latitude 89. Save `pole.png`. Pass when cells render without a map error.
- [ ] Lane 6. A `where` for `fire`. Save `no-point.png`. Pass when the card disables **where** for it.
- [ ] Lane 7. `GET /data/cache.sqlite`. Save `cache-hidden.png`. Pass when it returns 404.
- [ ] Lane 8. Resize to 375 px. Save `map-narrow.png`. Pass when the map sits below the panel with no horizontal scroll.
- [ ] Lane 9. The method text. Save `method.png`. Pass when it says that with 64 cells about 3 can look clear by chance.
- [ ] Lane 10. Switch the map variable to `rain`. Save `rain-map.png`. Pass when the colour scale flips warm and cool for a non-warm variable.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Page-load-to-interactive at trunk and head, now with MapLibre and the geojson, plus the cold live `where` time at head.
- [ ] Probe. 10 interleaved page loads at trunk and head, then 5 cold live `where` calls.
- [ ] Baseline. Record trunk page load first.
- [ ] Rule. Fail when head page load exceeds trunk by more than 1 s, or the cold live `where` exceeds 60 s.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 1, 2, and 4 screenshots into `docs/media/EB-12-review-<slug>.png`.
- [ ] Record a 30 to 60 second video of the change on a lane VM. Save it as `docs/media/EB-12-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Rank places and say when the leaders cannot be told apart (EB-13)

**Depends on.** EB-12.

**Files.**

- [ ] Create `earthbuddy/analyses/rank.py`.
- [ ] Edit `earthbuddy/analyses/__init__.py`, `earthbuddy/stats.py`, `earthbuddy/words.py`, `web/app.js`.
- [ ] Create `tests/test_rank.py`.

**Build.**

- [ ] Add `rank` per `docs/09-rank.md` with `cue_rank=1`. Use `series.get_many(tolerant=True)` and list failures under `skipped`. Group members are the gazetteer points EB-03 resolved, and the note says each is the POWER cell at its NASA SEDAC centre point.
- [ ] Add the leader comparison (Mann-Kendall on differences for `change`, Wilcoxon for `level`) and the shared-grid-cell check to `stats.py`.
- [ ] Add the rank panel and the `intervals` chart.

**You see.**

- [ ] Demo chip 4 shows a ranked list of 11 capitals with intervals and a headline that says whether the lead is clear.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_rank.py` gains `test_countries_top_10_with_no_network`, `test_same_cell_pair_marks_both_and_ties`, and `test_one_place_list_is_400`. Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run demo chip 1 at trunk and head. Save `claim-still.png`. Pass when both match. Then gate demo chip 4 at head and pass when 11 rows render.
- [ ] Lane 2. Live. Demo chip 4 with a cold cache. Save `live-rank.png`. Pass when it finishes and the POWER request log never shows more than 3 requests in flight.
- [ ] Lane 3. Live. Demo chip 4 again. Save `cached-rank.png`. Pass when no POWER request leaves the process.
- [ ] Lane 4. "Top 10 hottest countries". Save `top10.png`. Pass when `metric` is `level` and 10 rows render.
- [ ] Lane 5. Live. "Which Cambodian province is warming fastest?". Save `provinces.png`. Pass when 25 rows return and the provinces note shows.
- [ ] Lane 6. Two names in one grid cell. Save `same-cell.png`. Pass when both rows show `shares_grid_cell`.
- [ ] Lane 7. A list of one place from a share link. Save `one-place.png`. Pass when it returns 400.
- [ ] Lane 8. "Which Southeast Asian capital is getting drier fastest?". Save `drier.png`. Pass when `order` is `lowest` for `rain`.
- [ ] Lane 9. The tie headline. Save `tie.png`. Pass when `tied_with_first` equals the number of rows with `same_as_leader`.
- [ ] Lane 10. Resize to 375 px. Save `rank-narrow.png`. Pass when the intervals chart fits with no horizontal scroll.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. The trunk claim time as the shared scenario, the cached `countries` rank time, and the cold live `cambodia_provinces` rank time.
- [ ] Probe. 10 interleaved claim calls at trunk and head, 10 cached rank calls, then 1 cold province rank with a fresh `EB_DB`.
- [ ] Baseline. Record the trunk claim first.
- [ ] Rule. Fail when the head claim is more than 10% slower, the cached rank exceeds 2 s, or the cold province rank exceeds 240 s, which leaves margin under Vercel's 300 s.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 1, 4, and 5 screenshots into `docs/media/EB-13-review-<slug>.png`.
- [ ] Record a 30 to 60 second video of the change on a lane VM. Save it as `docs/media/EB-13-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Show every screen in Khmer (EB-14)

**Depends on.** EB-13.

**Files.**

- [ ] Edit `web/i18n.js`, `web/app.js`, `web/styles.css`, `web/index.html`, `earthbuddy/words.py`, `earthbuddy/reader.py`.
- [ ] Create `tests/test_i18n.py`.

**Build.**

- [ ] Fill `KM` in `i18n.js` from `~/earth-buddy-claimdesk-snapshot/js/i18n.km.js`, keeping only keys the new UI uses.
- [ ] Fill `words.KM` for every headline and student template.
- [ ] Add the language button, `lang="km"` on the page, the Noto Sans Khmer font, and the "Khmer is a draft" footer note.

**You see.**

- [ ] Clicking the language button turns the ask view, the card, and the KHM claim result into Khmer, with ASCII digits.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_i18n.py` gains `test_en_and_km_same_keys_and_placeholders`, `test_words_km_keys_subset_of_en_with_same_placeholders`, and `test_translated_demo_sentences_give_same_question`. Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run demo chip 1 in English at trunk and head. Save `en-still.png`. Pass when both match. Then gate the Khmer switch at head and pass when the headline is Khmer.
- [ ] Lane 2. Reload after switching. Save `remembered.png`. Pass when the page opens in Khmer.
- [ ] Lane 3. Each of the 5 translated demo sentences. Save `km-demos.png`. Pass when each runs with no card edit.
- [ ] Lane 4. A Khmer result's numbers. Save `digits.png`. Pass when every number uses ASCII digits.
- [ ] Lane 5. A missing Khmer key. Save `fallback.png`. Pass when the English string shows instead of the key.
- [ ] Lane 6. The font. Save `font.png`. Pass when computed `font-family` for Khmer text resolves to Noto Sans Khmer.
- [ ] Lane 7. The footer. Save `draft-note.png`. Pass when it says the Khmer is a draft.
- [ ] Lane 8. Khmer at 375 px. Save `km-narrow.png`. Pass when there is no horizontal scroll and no clipped Khmer line.
- [ ] Lane 9. Khmer explanation, AI off. Save `km-explain.png`. Pass when the student text is Khmer or English fallback, never a key.
- [ ] Lane 10. Keyboard only in Khmer. Save `km-keyboard.png`. Pass when every control keeps a visible focus ring.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Page-load-to-interactive at trunk and head, in English, and the Khmer font's transfer size at head.
- [ ] Probe. 10 interleaved page loads at trunk and head.
- [ ] Baseline. Record trunk first.
- [ ] Rule. Fail when head is more than 300 ms slower, or the Khmer font adds more than 200 KB.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 1, 3, and 8 screenshots into `docs/media/EB-14-review-<slug>.png`.
- [ ] Record a 30 to 60 second video of the change on a lane VM. Save it as `docs/media/EB-14-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click. Book the native Khmer reader before the pitch.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Compare recent years with a reference period (EB-15)

**Depends on.** EB-14.

**Files.**

- [ ] Create `earthbuddy/analyses/baseline.py`.
- [ ] Edit `earthbuddy/analyses/__init__.py`, `earthbuddy/stats.py`, `earthbuddy/words.py`, `web/app.js`.
- [ ] Create `tests/test_baseline.py`.

**Build.**

- [ ] Add `baseline` per `docs/08-baseline.md` with `cue_rank=4`. Add `mann_whitney` and `pace` to `stats.py` and their minimums to `T`.

**You see.**

- [ ] "Is Phnom Penh hotter than in the 1980s?" returns a level difference and, when both periods are long enough, a pace comparison.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_baseline.py` gains `test_offline_pp_heat_positive_and_clear` and `test_baseline_2018_2023_is_400`. Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run demo chip 1 at trunk and head. Save `claim-still.png`. Pass when both match. Then gate the 1980s sentence at head and pass when a baseline result renders.
- [ ] Lane 2. Live. `BaselineQ(Phnom Penh, heat)`. Save `live-baseline.png`. Pass when the recent period runs 2011 to 2025.
- [ ] Lane 3. Baseline (2018, 2023). Save `bad-baseline.png`. Pass when it returns 400 with `field: "baseline"`.
- [ ] Lane 4. A country in the draft. Save `country-centre.png`. Pass when the card offers the country's centre point.
- [ ] Lane 5. Baseline (1981, 1988). Save `short-base.png`. Pass when `pace` is null and the headline speaks of level only.
- [ ] Lane 6. The chart. Save `chart.png`. Pass when each period's mean shows as a flat segment.
- [ ] Lane 7. The method. Save `method.png`. Pass when it says the pace test is a normal approximation from two intervals.
- [ ] Lane 8. `rain` at Siem Reap. Save `rain.png`. Pass when `percent` is set.
- [ ] Lane 9. Khmer sentence for the 1980s question. Save `km.png`. Pass when `kind` is `baseline`.
- [ ] Lane 10. The share link. Save `share.png`. Pass when the reopened link shows the same result.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. The trunk claim time as the shared scenario, plus the cached baseline time at head.
- [ ] Probe. 10 interleaved claim calls at trunk and head, then 10 cached baseline calls.
- [ ] Baseline. Record the trunk claim first.
- [ ] Rule. Fail when the head claim is more than 10% slower or the cached baseline exceeds 500 ms.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 1 and 2 screenshots into `docs/media/EB-15-review-<slug>.png`.
- [ ] Record a 30 to 60 second video of the change on a lane VM. Save it as `docs/media/EB-15-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Find record years and unusual years (EB-16)

**Depends on.** EB-15.

**Files.**

- [ ] Create `earthbuddy/analyses/extremes.py`.
- [ ] Edit `earthbuddy/analyses/__init__.py`, `earthbuddy/stats.py`, `earthbuddy/words.py`, `web/app.js`.
- [ ] Create `tests/test_extremes.py`.

**Build.**

- [ ] Add `extremes` per `docs/10-extremes.md` with `cue_rank=3`. Add `clustering`, `month_trends`, and `season_timing` to `stats.py` and their thresholds to `T`.

**You see.**

- [ ] "Was 2024 Cambodia's hottest year?" names the year's rank and the word `ordinary`, `unusual`, or `exceptional`.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_extremes.py` gains `test_three_swings_above_trend_is_exceptional` and `test_trendless_clustering_chance_above_0_05`. Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run demo chip 1 at trunk and head. Save `claim-still.png`. Pass when both match. Then gate the 2024 sentence at head and pass when an extremes result renders.
- [ ] Lane 2. Live. Point Phnom Penh `heat`. Save `months.png`. Pass when 12 monthly rows return, each with a q.
- [ ] Lane 3. Live. Point Phnom Penh `rain`. Save `timing.png`. Pass when `timing` is set or skipped with the concentration reason.
- [ ] Lane 4. `KHM` `heat`. Save `country.png`. Pass when `months` is null.
- [ ] Lane 5. "Which month is changing most in Siem Reap?". Save `which-month.png`. Pass when `kind` is `extremes`.
- [ ] Lane 6. A warming place's recent year. Save `not-every-year.png`. Pass when the word comes from the trend line, so not every recent year is `exceptional`.
- [ ] Lane 7. A 9-year window. Save `short.png`. Pass when it returns 400 with `field: "window"`.
- [ ] Lane 8. The bar chart. Save `bars.png`. Pass when the focus year is highlighted.
- [ ] Lane 9. Khmer version of the 2024 sentence. Save `km.png`. Pass when `kind` is `extremes`.
- [ ] Lane 10. Resize to 375 px. Save `narrow.png`. Pass when there is no horizontal scroll.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. The trunk claim time as the shared scenario, plus the cached Point extremes time at head, which runs 12 monthly tests.
- [ ] Probe. 10 interleaved claim calls at trunk and head, then 10 cached extremes calls.
- [ ] Baseline. Record the trunk claim first.
- [ ] Rule. Fail when the head claim is more than 10% slower or the cached extremes exceeds 1 s.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 1 and 2 screenshots into `docs/media/EB-16-review-<slug>.png`.
- [ ] Record a 30 to 60 second video of the change on a lane VM. Save it as `docs/media/EB-16-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Show whether two variables move together (EB-17)

**Depends on.** EB-16.

**Files.**

- [ ] Create `earthbuddy/analyses/relate.py`.
- [ ] Edit `earthbuddy/analyses/__init__.py`, `earthbuddy/stats.py`, `earthbuddy/words.py`, `web/app.js`.
- [ ] Create `tests/test_relate.py`.

**Build.**

- [ ] Add `relate` per `docs/11-relate.md` with `cue_rank=2`. Add `relation` to `stats.py` and the strength bands to `T`. Every headline carries the "pattern, not proof" sentence.

**You see.**

- [ ] "Is rainfall linked to soil moisture in Cambodia?" returns a scatter of detrended values and a headline ending in "This is a pattern, not proof that one causes the other."

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `tests/test_relate.py` gains `test_detrending_removes_shared_trend_in_90_percent_of_500_runs` and `test_two_merra2_variables_show_shared_model_note`. Run `.venv/bin/python -m pytest -q`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `sonnet high` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run demo chip 1 at trunk and head. Save `claim-still.png`. Pass when both match. Then gate the rain and soil sentence at head and pass when a relate result renders.
- [ ] Lane 2. The headline. Save `not-proof.png`. Pass when it ends with the pattern-not-proof sentence.
- [ ] Lane 3. `rain` and `soil` on `KHM`. Save `merra.png`. Pass when the shared-model note shows.
- [ ] Lane 4. `aerosol` and `heat`. Save `mixed-source.png`. Pass when no shared-model note shows.
- [ ] Lane 5. The same variable for x and y. Save `same.png`. Pass when it returns 400.
- [ ] Lane 6. A constant series such as `snow` on `KHM`. Save `constant.png`. Pass when it returns 400 with a reason.
- [ ] Lane 7. The scatter chart. Save `scatter.png`. Pass when each point is labelled by year.
- [ ] Lane 8. `short_record` on a 2001 to 2024 country pair. Save `short.png`. Pass when it is false, because n = 24 is above 20.
- [ ] Lane 9. Khmer version of the sentence. Save `km.png`. Pass when `kind` is `relate`.
- [ ] Lane 10. Share link. Save `share.png`. Pass when the reopened link shows the same rho.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. The trunk claim time as the shared scenario, plus the relate time at head on a country pair.
- [ ] Probe. 10 interleaved claim calls at trunk and head, then 10 relate calls.
- [ ] Baseline. Record the trunk claim first.
- [ ] Rule. Fail when the head claim is more than 10% slower or relate exceeds 500 ms.

**Review gate.** The operator reviews before merge.

- [ ] Copy lane 1 and 3 screenshots into `docs/media/EB-17-review-<slug>.png`.
- [ ] Record a 30 to 60 second video of the change on a lane VM. Save it as `docs/media/EB-17-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The root appends it to the base-branch stack and the operator lands it bottom-up.

## Close the program

- [ ] Every box above is checked with its evidence.
- [ ] The five demo sentences run on the Vercel URL with AI on and with AI off (SPEC "Definition of done").
- [ ] `python tools/check_refs.py` resolves every DOI, and `tests/test_sources.py` passes.
- [ ] `README.md` states how AI was used, cites every dataset with its DOI, and lists the known limits.
- [ ] Reply to the operator with the report the execution playbook names.

## Appendix A. Prototype evidence

Each finding below came from a script run on 14 Nov 2026. The scripts sit in the session scratchpad and are not committed.

1. **Hamed-Rao fails the spec's memory check at n = 24.** False-positive rates over 2,000 AR(1) runs were 0.058 at φ = 0, 0.113 at φ = 0.3, and 0.197 at φ = 0.5, against a limit of 0.08. The other `pymannkendall` corrections also failed or lost too much power. Yue-Wang gave 0.43 to 0.51. Trend-free pre-whitening gave 0.25 at φ = 0.5. Plain pre-whitening passed (0.033, 0.048, 0.045) but found a real trend only 16% of the time.
2. **The claim desk's variance table passes with a stronger bias correction.** With φ = r + (1 + 3r)/n, as `docs/03-stats.md` states, the rate at φ = 0.5 was 0.093 and 0.102 on two seeds, which fails. With φ = r + (3 + 6r)/n, the rates were 0.028, 0.048, and 0.073, with power 0.39 on a trend of 0.8 standard deviations per decade. EB-05 uses the second form.
3. **Every point parameter in `docs/01` is served monthly.** A request at 11.55 N, 104.92 E returned 60 valid months from 2020 to 2024 for all 22 parameters. The first valid month is January 1981 for the MERRA-2 parameters, `TO3`, `FRSEAICE`, `SNODP`, and `FROST_DAYS`. It is January 1984 for `ALLSKY_SFC_SW_DWN` and `CLOUD_AMT`, and January 2001 for `ALLSKY_SFC_UV_INDEX`, `ALLSKY_SRF_ALB`, and `AOD_55_ADJ`. One request can carry at least 14 parameters.
4. **POWER publishes 2025 in full.** A 1981 to 2025 request for `T2M` returned 540 months with all 12 months of 2025. The point record is 45 years.
5. **The local dependency install is 248 MB.** `scipy` is 82 MB, `pandas` 45 MB (pulled in by `statsmodels`), `statsmodels` 43 MB, `numpy` 26 MB, and `anthropic` 17 MB. Whether this fits Vercel stays unproven until EB-01 deploys.
6. **The prototype repo is gone, and a snapshot survives.** `~/earth-buddy` no longer exists, and no GitHub repo holds the claim desk. A partial copy with the data files, `countries.geojson`, the vendor files, and the JS source is now at `~/earth-buddy-claimdesk-snapshot`. Its `POINTERS.md` maps each row to the source lines to port. The analyst's Python package, `places.json`, and `brain/catalog.json` survive nowhere.

Three facts stay unproven. They are the Vercel bundle limit (EB-01), the claim desk's KHM heat result of −0.07 °C per decade (EB-05, lane 2), and the cold time of a 25-province rank (EB-13).

## Appendix B. Alternatives rejected

- **Hamed-Rao as written in `docs/03`.** It fails the spec's own acceptance check (Appendix A, finding 1).
- **Pre-whitening.** It passes the check but misses 84% of real trends at n = 24, which makes "no clear change" the answer to almost everything.
- **Rebuilding every series from the POWER Zarr stores.** The place series in the snapshot are reusable, so EB-03 rebuilds only the country series, which the new data rule requires.
- **Parallel owners for independent rows.** `stats.py` work (EB-05) could start beside EB-03, and kind PRs after EB-09 touch separate files. `CLAUDE.md` requires the table order, so only EB-05 drafts early and still lands in order.
- **One PR per module instead of per row.** Each SPEC row already ends in its own acceptance check, so a row is the natural verifiable unit.

## Appendix C. Risks

1. **The SEDAC downloads (EB-03).** The two GPWv4.11 grids need an Earthdata login. `~/.netrc` holds one. If a download fails, EB-03 stops and reports, because no other border source is allowed.
2. **The country series change (EB-03, EB-11).** SEDAC cell ownership differs from Natural Earth borders, so the KHM heat series may move by up to 0.2 °C and the country count is not 242. The owner records the count and any audit verdict that moves.
3. **The Vercel bundle size (EB-01).** The local install is 248 MB. If the deploy fails, drop `statsmodels` and accept no STL decomposition.
4. **Audit verdicts move (EB-05, EB-11).** The corrected φ is stricter than the claim desk's. The owner records each changed verdict and its cause in `README.md` and never edits the frozen claims.
5. **The two point groups come from names (EB-03, EB-13).** `tools/catalog.src.json` lists the 11 capital and 25 province names, and the build resolves them against the SEDAC gazetteer. A spelling the gazetteer does not hold fails the build, so the owner fixes the name, never the coordinates.
6. **The Khmer is a draft (EB-14).** The prototype's Khmer was machine-drafted. Book a native reader before the 16:00 pitch.
7. **The deadline.** P0 is about 19 hours of agent work by the SPEC estimate, and this plan's live lanes add time to each PR. If P0 is not merged by Saturday night, drop P2 (EB-15 to EB-17) first, then EB-14.
8. **Push access.** SSH logs in as `dara-ling`. Every push uses the HTTPS command in "PR mechanics".

## Appendix D. Links and reading list

- Read `SPEC.md`, `CLAUDE.md`, `docs/ARCHITECTURE.md`, and the PR's own `docs/NN-*.md` before any edit.
- The port map is `~/earth-buddy-claimdesk-snapshot/POINTERS.md`.
- EB-05 and EB-09 get `pstack/skills/how/SKILL.md` before the build, since they set the statistics and the UI shape every later PR copies.
- EB-05 gets `pstack/skills/interrogate/SKILL.md` on the corrected trend test before code-ready, since every verdict depends on it.
- Keep the decision trail per `pstack/skills/show-me-your-work/SKILL.md` in `docs/trail.md`, one row per tick and per operator answer.
