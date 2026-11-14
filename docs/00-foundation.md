# Foundation

Set up the skeleton that every later feature builds on: the package, the shared types, the test harness, and a working deploy. Priority P0. Estimate 1 hour.

## Build

1. Create the layout in `SPEC.md`. Add `requirements.txt` with these packages: `fastapi`, `uvicorn`, `httpx`, `pydantic>=2`, `numpy`, `scipy`, `statsmodels`, `pymannkendall`, and `pytest`.
2. Write `earthbuddy/types.py` with every type in `SPEC.md` "Core types". Add `Chart` and `Verdict` as placeholders. `docs/03-stats.md` and `docs/14-web-ui.md` define them.
3. Write `earthbuddy/server.py` with `GET /api/status` and a static mount of `web/` at `/`. Serve `index.html` with `Cache-Control: no-store`.
4. Write `run.py`. It starts uvicorn with reload on `127.0.0.1:8000`, and reads `EB_HOST` and `EB_PORT`.
5. Write `main.py`. It does `from earthbuddy.server import app`.
6. Write `vercel.json`. It sets `functions["main.py"].maxDuration = 300` and sends every path to `main.py`.
7. Write `.env.example`. Read it with a small loader in which the real environment wins over `.env`. The prototype had this backwards.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `EB_LLM_URL` | unset | Base URL of the self-hosted OpenAI-compatible model server, ending in `/v1`. Unset means AI is unavailable. The AI switch shows as off and disabled. |
| `EB_MODEL` | `qwen3:8b` | Model for the reader and the explainer |
| `EB_LLM_KEY` | unset | Bearer token for the model server. Unset sends no `Authorization` header. |
| `EB_DB` | `data/cache.sqlite`, or `/tmp/eb/cache.sqlite` on Vercel | Response cache |
| `EB_OFFLINE` | unset | `1` serves synthetic POWER-shaped data and shows a banner (`docs/02-series.md`) |
| `POWER_COMMUNITY` | `AG` | NASA POWER community |

## Acceptance

- `pytest` runs and passes with one test: `GET /api/status` returns 200 with `ai_available` set to a boolean.
- `python run.py`, then opening http://127.0.0.1:8000, shows an empty page with the app title.
- `vercel --prod` deploys, and `/api/status` answers on the deployed URL.

Deploy on hour one. A deploy problem found on Sunday afternoon costs the demo.
