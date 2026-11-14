"""FastAPI routes. Routes compose; three handlers do all error mapping. Sync `def` routes run on the thread pool."""
from typing import get_args

from fastapi import Body, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ROOT, analyses, cache, catalog, explainer, geocode, net, power, reader
from .stats import T
from .types import Audience, DataSourceError, Explanation, Lang, Point, QuestionError, ReadResult, Result, Source

net.refuse_offline_on_vercel()

WEB = ROOT / "web"
app = FastAPI(title="Earth Buddy")


@app.exception_handler(QuestionError)
def _bad_question(_: Request, e: QuestionError) -> JSONResponse:
    return JSONResponse({"error": str(e), "kind": "request", "field": e.field}, status_code=400)


@app.exception_handler(RequestValidationError)
def _bad_body(_: Request, e: RequestValidationError) -> JSONResponse:
    loc = next(iter(e.errors()), {}).get("loc", ())
    field = next((str(x) for x in loc if x not in ("body", "query")), "")
    return JSONResponse({"error": "bad request", "kind": "request", "field": field}, status_code=400)


@app.exception_handler(DataSourceError)
def _source(_: Request, e: DataSourceError) -> JSONResponse:
    return JSONResponse({"error": e.message, "kind": "data_source", "url": e.url}, status_code=502)


@app.get("/api/status")
def api_status() -> dict:
    return {"ai_available": net.ai_available(), "model": net.model_id(), "offline": net.OFFLINE,
            "last_complete_year": power.last_complete_year(), "cache": cache.stats()}


@app.get("/api/catalog")
def api_catalog() -> dict:
    return {**catalog.raw(), "kinds": analyses.kinds_meta()}


@app.get("/api/sources")
def api_sources() -> list[Source]:
    return catalog.sources()


class ReadBody(BaseModel):
    text: str | None = None
    draft: dict | None = None
    lang: Lang = "en"
    ai: bool = False


@app.post("/api/read")
def api_read(body: ReadBody) -> ReadResult:
    if body.draft is not None:
        return reader.reread(body.draft, body.lang)
    return reader.read(body.text or "", body.lang, body.ai)


@app.post("/api/run")
def api_run(body: dict = Body(...)) -> Result:
    question, revision = reader.question_from(body)
    lang = body.get("lang", "en")
    if lang not in get_args(Lang):
        raise QuestionError("lang")
    return analyses.run(question, revision=revision, lang=lang)


class ExplainBody(BaseModel):
    result: Result
    audience: Audience = "student"
    lang: Lang = "en"
    ai: bool = False


@app.post("/api/explain")
def api_explain(body: ExplainBody) -> Explanation:
    return explainer.explain(body.result, body.audience, body.lang, body.ai)


@app.get("/api/geocode")
def api_geocode(q: str = Query(min_length=1, max_length=reader.MAX_TEXT)) -> dict[str, list[Point]]:
    return {"results": geocode.search(q)}


@app.get("/api/audit")
def api_audit(lang: Lang = "en") -> dict:
    frozen = catalog.audit()
    claims = []
    for c in frozen["claims"]:
        body = {"question": {"kind": "claim", "region_id": c["region"], "tests": c["tests"], "window": c["window"]},
                "via": "audit"}
        question, _ = reader.question_from(body)
        r = analyses.run(question, lang=lang)
        claims.append({**c, "question": question, "verdict": r.verdict, "verdict_word": r.facts["verdict"]})
    return {**frozen, "claims": claims}


@app.get("/data/countries.geojson")
def data_countries() -> FileResponse:
    return FileResponse(catalog.DATA / "countries.geojson", media_type="application/geo+json")


@app.get("/data/summary.json")
def data_summary() -> JSONResponse:
    return JSONResponse({v: {iso: row | {"clear": row["q"] < T.fdr_q} for iso, row in rows.items()}
                         for v, rows in catalog.summary().items()})


@app.get("/")
@app.get("/index.html")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-store"})


app.mount("/", StaticFiles(directory=WEB), name="web")
