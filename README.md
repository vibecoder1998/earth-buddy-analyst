# Earth Buddy

Earth Buddy answers questions about how the Earth is changing at a place, using NASA data. You type a claim, such as "Cambodia is getting hotter and drier", or a question, such as "Which Southeast Asian capital is warming fastest?". The app returns a verdict, the numbers behind it, a chart, the method, and the NASA sources.

Code makes every number and every verdict. A language model reads the sentence and writes plain-language text from the results, and nothing more. With AI switched off, the app still answers every question.

Built for the NASA Space Apps Challenge 2026, Phnom Penh, challenge "Be An Earth System Trend Detective".

## Status

This repository holds the build spec. It holds no code yet. The spec merges two earlier prototypes, the claim desk and the Earth Buddy analyst, into one app.

## Build it with a coding agent

1. Clone the repository.

   ```
   git clone https://github.com/vibecoder1998/earth-buddy-analyst
   cd earth-buddy-analyst
   ```

2. Open a Claude Code session in the folder. `CLAUDE.md` loads automatically and points the agent at `SPEC.md`.
3. Tell the agent: "Read SPEC.md and build row 1."
4. When the row's acceptance checks pass, ask for the next row.

The build-order table in `SPEC.md` gives each feature a priority and an estimate. P0 is the demo, about 17 hours of agent work.

## What is in the spec

| File | Contents |
|---|---|
| `SPEC.md` | The contract: the one rule, the architecture, the shared types, the HTTP API, the build order, what is cut and why, and the definition of done |
| `CLAUDE.md` | Standing instructions for a coding agent |
| `docs/00-foundation.md` | Skeleton, configuration, and the first deploy |
| `docs/01-catalog-and-data.md` | 27 NASA variables, 242 countries, 43 places, and how the data is built |
| `docs/02-series.md` | Precomputed region series, live NASA POWER points, and the cache |
| `docs/03-stats.md` | Trend test, change point, false-discovery check, and claim verdicts |
| `docs/04-reader.md` | Sentence to typed question, by keywords or by AI |
| `docs/05-claim-check.md` | Test a claim and build the evidence board |
| `docs/06-trend.md` | How one variable is changing at one place |
| `docs/07-where-map.md` | Where around a place the change is |
| `docs/08-baseline.md` | Recent years against a reference period |
| `docs/09-rank.md` | Which places lead, and when they cannot be told apart |
| `docs/10-extremes.md` | Record years, unusual years, and monthly changes |
| `docs/11-relate.md` | Whether two variables move together |
| `docs/12-scan-and-audit.md` | Every variable for one region, and claims frozen before the data existed |
| `docs/13-explainer.md` | Plain-language text with every number checked |
| `docs/14-web-ui.md` | Ask, card, and result screens, charts, map, and share links |
| `docs/15-i18n.md` | Khmer and English |

## Stack

Python 3.12 with FastAPI, numpy, scipy, statsmodels, and pymannkendall. Vanilla JavaScript with no build step, MapLibre GL for the map, and SVG charts. SQLite caches NASA responses. It deploys to Vercel.

## Data

All data is open NASA data, and no login is needed:

- NASA POWER: MERRA-2 reanalysis, CERES SYN1deg, and GPM IMERG
- MODIS active fire counts

## AI use

AI coding assistants helped write this spec. In the app, Anthropic's Claude reads a typed sentence into a structured question, and writes explanations. Both are optional and off by default. The model never produces a data value or a verdict.
