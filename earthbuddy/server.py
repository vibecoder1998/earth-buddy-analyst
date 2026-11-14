"""FastAPI routes. Routes compose; three handlers do all error mapping. Sync `def` routes run on the thread pool."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import ROOT, cache, catalog, net, power
from .types import DataSourceError, QuestionError, Source

WEB = ROOT / "web"
app = FastAPI(title="Earth Buddy")


@app.exception_handler(QuestionError)
def _bad_question(_: Request, e: QuestionError) -> JSONResponse:
    return JSONResponse({"error": str(e), "kind": "request", "field": e.field}, status_code=400)


@app.exception_handler(RequestValidationError)
def _bad_body(_: Request, e: RequestValidationError) -> JSONResponse:
    loc = next(iter(e.errors()), {}).get("loc", ())
    field = next((str(x) for x in loc if x != "body"), "")
    return JSONResponse({"error": "bad request", "kind": "request", "field": field}, status_code=400)


@app.exception_handler(DataSourceError)
def _source(_: Request, e: DataSourceError) -> JSONResponse:
    return JSONResponse({"error": e.message, "kind": "data_source", "url": e.url}, status_code=502)


@app.get("/api/status")
def api_status() -> dict:
    return {"ai_available": net.ai_available(), "model": net.model_id(), "offline": net.OFFLINE,
            "last_complete_year": power.last_complete_year(), "cache": cache.stats()}


@app.get("/api/sources")
def api_sources() -> list[Source]:
    return catalog.sources()


# Rows 5-10 add: POST /api/read, POST /api/run, POST /api/explain, GET /api/catalog, /api/geocode, /api/audit.
# data/ is never mounted: it holds cache.sqlite. Row 11 adds explicit routes for countries.geojson and summary.json.


@app.get("/")
@app.get("/index.html")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-store"})


app.mount("/", StaticFiles(directory=WEB), name="web")
