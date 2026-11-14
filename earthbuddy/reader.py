"""Sentence or raw dict -> Draft -> Question. guard is the one gate for every outside dict."""
from typing import Any, Callable

from .types import Draft, Lang, Question, ReadResult, Via

MAX_TEXT = 600


def read(text: str, lang: Lang, ai: bool) -> ReadResult:
    # TODO row 5:
    # 1 empty or > MAX_TEXT -> QuestionError("text")
    # 2 if ai and net.ai_available(): try raw, via = read_ai(text, lang), "ai" except AIFailed: ai_failed = True
    # 3 else raw, via = read_keywords(text, lang), "keywords"
    # 4 raw has place_name and no region: raw["point"] = geocode.search(place_name)[0] (empty -> missing)
    # 5 return _finish(guard(raw, text, via), ai_failed)
    raise NotImplementedError


def reread(draft: dict, lang: Lang) -> ReadResult:
    """Card kind switch: guard(draft fields + revision, draft quote, "form"), then _finish."""
    raise NotImplementedError


def question_from(body: dict) -> tuple[Question, int]:
    """POST /api/run and share links: guard(via=body.via in {"form","link","audit"}), parse, or QuestionError(first field)."""
    raise NotImplementedError


def guard(raw: object, quote: str, via: Via) -> Draft:
    """Never raises; drops what it does not know (docs/04 "The guard").
    kind = raw kind if in ANALYSES else ("claim" if any test has a direction else "trend");
    fields = {name: FILL[name](raw) for name in ANALYSES[kind].fields if not None};
    leads/unmapped: no digits (words.HAS_DIGIT), <= 80 chars, first 3; revision clamped 0..99, forced 0 for via "ai"."""
    raise NotImplementedError


# One filler per FIELD NAME. Each accepts the flat reader shape AND the Question shape; returns JSON-ready data or None.
# Keys must equal the union of all Question fields (tests/test_registry.py).
FILL: dict[str, Callable[[dict], Any]] = {
    "region": lambda r: _todo(),     # region dict checked against catalog | region_id
    "point": lambda r: _todo(),      # point | catalog.centre of region (country -> centre point)
    "tests": lambda r: _todo(),      # known variable, unique, direction valid, first 8
    "variable": lambda r: _todo(),   # variable | tests[0].variable
    "x": lambda r: _todo(),          # x | tests[0].variable
    "y": lambda r: _todo(),          # y | tests[1].variable
    "window": lambda r: _todo(),     # window | (window_from, window_to); inside the variable's years, >= T.reliable, else None
    "baseline": lambda r: _todo(),   # two ints or None (model default applies)
    "among": lambda r: _todo(),      # group id | 2..60 regions | places (catalog names)
    "metric": lambda r: _todo(),     # "change" | "level"
    "order": lambda r: _todo(),      # "highest" | "lowest"
    "top_n": lambda r: _todo(),      # int 1..60
    "year": lambda r: _todo(),       # int
}


def read_keywords(text: str, lang: Lang) -> dict:
    """Pure, no network. Flat shape: kind (first cue hit by cue_rank, else None), tests, region_id | place_name,
    window_from/to, among, top_n, metric, order. Latin keywords match at a word start ("rain" not in "Ukraine")."""
    raise NotImplementedError


def read_ai(text: str, lang: Lang) -> dict:
    """net.ask_model(SYSTEM, <sentence lang=..>stripped</sentence>, schema(), 2048). Raises AIFailed."""
    raise NotImplementedError


def schema() -> dict:
    """JSON schema from catalog ids and list(ANALYSES); all fields required and nullable; byte-stable."""
    raise NotImplementedError


def _todo() -> Any:
    raise NotImplementedError
