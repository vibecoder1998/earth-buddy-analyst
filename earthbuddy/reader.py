"""Sentence or raw dict -> Draft -> Question. guard is the one gate for every outside dict."""
import functools
import re
from typing import Any, Callable, get_args

from pydantic import TypeAdapter, ValidationError

from . import catalog, geocode
from .analyses import ANALYSES
from .stats import T
from .types import (Country, Draft, HazeMeasure, Kind, Lang, Place, Point, Question, QuestionError, ReadResult,
                    Region, Satellite, Via, WaterMeasure, Zone)
from .words import HAS_DIGIT, Words, ascii_digits

MAX_TEXT = 600
MAX_TESTS = 8
MAX_NOTES = 3
MAX_NOTE = 80
MAX_REVISION = 99
MAX_REGIONS = 60
DIRECTIONS = ("up", "down", "any")
VIAS: tuple[Via, ...] = ("form", "link", "audit")

_QUESTION = TypeAdapter(Question)
_REGION = TypeAdapter(Region)
MODELS = {get_args(m.model_fields["kind"].annotation)[0]: m for m in get_args(get_args(Question)[0])}

RANKING = re.compile(r"\btop \d+|\bwhich (?:country|countries|province|capital|city|cities|place|region)|\bfastest\b|\brank"
                     r"|(?:ប្រទេស|ខេត្ត|រាជធានី|ទីក្រុង|កន្លែង)ណា|លឿនជាងគេ|លឿនបំផុត|ចំណាត់ថ្នាក់|កំពូល\s*\d+")
CUES: tuple[tuple[Kind, tuple[str, ...]], ...] = (
    ("rank", (RANKING.pattern, r"\bcompare\b")),
    ("relate", (r"\blinked\b", r"\brelated?\b", r"\brelates\b", r"\brelationship\b", r"\bconnected\b", r"\bcorrelat",
                r"\bgoes with\b", r"\bmove together\b", r"\b(?:more|less|fewer) .+? means? (?:more|less|fewer)\b",
                r"ទាក់ទងគ្នា", r"ពាក់ព័ន្ធគ្នា", r"ទំនាក់ទំនង", r"ប្រែប្រួលជាមួយគ្នា")),
    ("extremes", (r"\brecord\b", r"\b(?:wettest|driest|hottest|coldest) year", r"\bunusual\b", r"\bextreme",
                  r"\bwhich month", r"\bhow \w+ was (?:it )?(?:in )?(?:19|20)\d\d\b", r"កំណត់ត្រា", r"ឆ្នាំណា", r"ខែណា", r"មិនធម្មតា")),
    ("baseline", (r"\bthan (?:in )?the \d{4}", r"\bbaseline\b", r"\bcompared with\b", r"\bthan before\b",
                  r"\bsince 1981\b", r"ធៀបនឹង", r"ធៀបជាមួយ", r"តាំងពី\s*(?:ឆ្នាំ\s*)?1981", r"ជាង.*ទសវត្ស")),
    ("where", (r"\bwhere\b", r"\bwhich part", r"តំបន់ណា", r"ផ្នែកណា", r"នៅឯណា", r"ត្រង់ណា")),
    ("scan", (r"\bwhat(?: is|'s) changing in\b", r"\beverything about\b", r"អ្វី(?:ខ្លះ)?កំពុងផ្លាស់ប្[តដ]ូរ")),
)
GROUP_CUES = ((r"\bsouth-?east asia", "southeast_asia_capitals"), (r"\bprovince|\bwhich regions?\b", "cambodia_provinces"),
              (r"\bcountr", "countries"), (r"អាស៊ីអាគ្នេយ៍", "southeast_asia_capitals"),
              (r"ខេត្ត", "cambodia_provinces"), (r"ប្រទេស", "countries"))
KM_MOST = r"(?:បំផុត|ជាងគេ)"
CHANGE_CUE = re.compile(r"\b(?:fastest|faster|getting|warming|cooling|drying|wetting|chang|ris|fall|increas|decreas|trend)"
                        r"|លឿន|ផ្លាស់ប្[តដ]ូរ|កើនឡើង|ថយចុះ|ឡើងកម្[តដ]ៅ|និន្នាការ|កាន់តែ")
LEVEL_CUE = re.compile(r"\b(?:hottest|warmest|coldest|coolest|wettest|driest|highest|lowest|sunniest|cloudiest|windiest)\b"
                       rf"|(?:ក្[តដ]ៅ|ត្រជាក់|សើម|ស្ងួត|ខ្ពស់|ទាប|ភ្លៀងច្រើន|ថ្ងៃច្រើន|ពពកច្រើន|ខ្យល់ខ្លាំង){KM_MOST}")
LOWEST_CUE = re.compile(rf"\b(?:lowest|least|coldest|coolest|driest|slowest)\b|(?:ទាប|តិច|ត្រជាក់|ស្ងួត|យឺត){KM_MOST}")
HOTTEST = re.compile(rf"\bhottest\b|ក្[តដ]ៅ{KM_MOST}")
HOTTEST_TIME = re.compile(r"\bhottest (?:days?|hours?)\b|(?:ថ្ងៃ|ម៉ោង)\s*(?:ដែល)?ក្[តដ]ៅ")
HOTTEST_MEANS_HEAT = ("rank", "extremes")   # "hottest year/capital" ranks yearly heat; "hottest days" stays tmax-like

# Things people ask about that no catalog variable measures: cue, then the words key that names it.
# Words a variable keyword already covers are taken out first, so adding the variable to the catalog retires its row.
NOT_MEASURED = (
    (r"\bvegetation|\bgreenness|\bndvi\b|\bforests?\b|\bdeforest|\btree cover|រុក្ខជាតិ|ព្រៃឈើ", "lead.vegetation"),
    (r"\bsea levels?\b|នីវ៉ូទឹកសមុទ្រ", "lead.sea_level"),
    (r"\bfloods?\b|\bflooding\b|ទឹកជំនន់", "lead.floods"),
    (r"\bcrop yields?\b|\bharvests?\b|ទិន្នផល", "lead.crop_yields"),
)
SINCE = re.compile(r"(?:since|ចាប់តាំងពី|តាំងពី)\s*(?:ឆ្នាំ\s*)?(\d{4})")
SPAN = (re.compile(r"from\s+(\d{4})\s+(?:to|until)\s+(\d{4})"), re.compile(r"between\s+(\d{4})\s+and\s+(\d{4})"),
        re.compile(r"ពី\s*(?:ឆ្នាំ\s*)?(\d{4})\s*(?:ដល់|ទៅ)\s*(?:ឆ្នាំ\s*)?(\d{4})"), re.compile(r"(\d{4})\s*[-–]\s*(\d{4})"))
DECADE = re.compile(r"\b(\d{3}0)s\b|ទសវត្ស(?:រ៍)?\s*(?:ឆ្នាំ\s*)?(\d{3}0)")
TOP = re.compile(r"(?:\btop |កំពូល\s*)(\d+)")
YEAR = re.compile(r"(?<!\d)((?:19|20)\d\d)(?!\d)")
PLACE_NAME = re.compile(r"\b(?:in|at|for|near)\s+([A-Z][\w'’-]*(?:\s+[A-Z][\w'’-]*)*)")


def read(text: str, lang: Lang) -> ReadResult:
    if not text.strip() or len(text) > MAX_TEXT:
        raise QuestionError("text", f"type 1 to {MAX_TEXT} characters")
    raw = read_keywords(text, lang)
    if name := raw.get("place_name"):   # set only when no catalog region matched
        if hits := geocode.search(name):
            raw["point"] = hits[0].model_dump()
        else:
            raw["unmapped"] = [*raw["unmapped"], name]
    return _finish(guard(raw, text, "keywords"))


def reread(draft: dict, lang: Lang) -> ReadResult:
    raw = {**_dict(draft.get("fields")), "revision": draft.get("revision"),
           "leads": draft.get("leads"), "unmapped": draft.get("unmapped")}
    quote = draft.get("quote")
    return _finish(guard(raw, quote if isinstance(quote, str) else "", "form"))


def question_from(body: dict) -> tuple[Question, int]:
    via = body.get("via") if body.get("via") in VIAS else "link"
    draft = guard({**_dict(body.get("question")), "revision": body.get("revision")}, "", via)
    question, missing = _parse(draft)
    if question is None:
        raise QuestionError(missing[0] if missing else "kind")
    return question, draft.revision


def guard(raw: object, quote: str, via: Via) -> Draft:
    """Never raises; drops what it does not know (docs/04 "The guard")."""
    r = _dict(raw)
    kind = r.get("kind")
    if kind not in MODELS:
        kind = "claim" if any(t["direction"] != "any" for t in FILL["tests"](r) or []) else "trend"
    fields = {"kind": kind}
    for name in MODELS[kind].model_fields:
        if name != "kind" and (value := FILL[name](r)) is not None:
            fields[name] = value
    revision = r.get("revision")
    revision = min(max(revision, 0), MAX_REVISION) if _int(revision) else 0
    return Draft(fields=fields, quote=quote, via=via, leads=_notes(r.get("leads")),
                 unmapped=_notes(r.get("unmapped")), revision=revision)


def _finish(draft: Draft) -> ReadResult:
    question, missing = _parse(draft)
    if question is not None and question.kind not in ANALYSES:
        question = None
    return ReadResult(draft=draft, question=question, missing=missing)


def _parse(draft: Draft) -> tuple[Question | None, list[str]]:
    try:
        return _QUESTION.validate_python(draft.fields), []
    except ValidationError as e:
        names = [str(err["loc"][1]) for err in e.errors() if len(err["loc"]) > 1]
        return None, list(dict.fromkeys(names)) or ["kind"]


def _dict(x: object) -> dict:
    return x if isinstance(x, dict) else {}


def _list(x: object) -> list:
    return x if isinstance(x, list) else []


def _int(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _str(x: object, allowed) -> str | None:
    return x if isinstance(x, str) and x in allowed else None


def _notes(x: object) -> list[str]:
    kept = [s.strip() for s in _list(x) if isinstance(s, str)]
    return [s for s in kept if s and len(s) <= MAX_NOTE and not HAS_DIGIT.search(s)][:MAX_NOTES]


def _known_variable(x: object) -> str | None:
    return x if isinstance(x, str) and x in _variable_ids() else None


@functools.cache
def _variable_ids() -> frozenset[str]:
    return frozenset(v.id for v in catalog.variables())


def _known_region(x: object) -> Region | None:
    try:
        region = _REGION.validate_python(x)
        catalog.name(region)
        return region
    except (ValidationError, QuestionError):
        return None


def _region_id(x: object) -> Region | None:
    if not isinstance(x, str):
        return None
    return _known_region({"kind": "place", "id": x} if x.startswith("p.") else {"kind": "country", "iso3": x})


def _fill_region(r: dict) -> dict | None:
    region = _known_region(r.get("region")) or _region_id(r.get("region_id")) or _known_region(r.get("point"))
    return None if region is None else region.model_dump()


def _fill_point(r: dict) -> dict | None:
    point = _known_region(r.get("point")) or _known_region(_fill_region(r))
    return None if point is None else catalog.centre(point).model_dump()


def _fill_tests(r: dict) -> list[dict] | None:
    tests, seen = [], set()
    for t in _list(r.get("tests")):
        t = _dict(t)
        v, d = _known_variable(t.get("variable")), _str(t.get("direction"), DIRECTIONS)
        if v and d and v not in seen and len(tests) < MAX_TESTS:
            seen.add(v)
            tests.append({"variable": v, "direction": d})
    return tests or None


def _nth_test(r: dict, n: int) -> str | None:
    tests = _fill_tests(r) or []
    return tests[n]["variable"] if len(tests) > n else None


def _fill_window(r: dict) -> list[int] | None:
    w = r.get("window")
    a, b = (w if isinstance(w, (list, tuple)) and len(w) == 2 else (r.get("window_from"), r.get("window_to")))
    if a is None and b is None:
        return None
    names = {t["variable"] for t in _fill_tests(r) or []} | {FILL[k](r) for k in ("variable", "x", "y")} - {None}
    lo, hi = catalog.years()
    if not isinstance(_known_region(_fill_region(r)), (Country, Place)):
        lo = max((catalog.variable(v).first_year for v in names), default=lo)
    a, b = lo if a is None else a, hi if b is None else b
    if not (_int(a) and _int(b)) or a < lo or b > hi or b - a + 1 < T.reliable:
        return None
    return [a, b]


def _years(x: object) -> list[int] | None:
    """A forward pair of years. No clamp: a baseline and a span reach outside the catalog's years."""
    return list(x) if isinstance(x, (list, tuple)) and len(x) == 2 and all(map(_int, x)) and x[0] <= x[1] else None


def _fill_baseline(r: dict) -> list[int] | None:
    """An explicit baseline, else the window years a reader found ("than the 1981-2010 average")."""
    return _years(r.get("baseline")) or _years((r.get("window_from"), r.get("window_to")))


@functools.cache
def _group_ids() -> frozenset[str]:
    return frozenset(g.id for g in catalog.load().groups)


def _fill_among(r: dict) -> str | list[dict] | None:
    if group := _str(r.get("among"), _group_ids()):
        return group
    regions = map(_known_region, _list(r.get("among")))
    unique = list({repr(x): x for x in regions if x is not None}.values())[:MAX_REGIONS]
    return [x.model_dump() for x in unique] if len(unique) >= 2 else None


def _fill_top_n(r: dict) -> int | None:
    n = r.get("top_n")
    return n if _int(n) and 1 <= n <= MAX_REGIONS else _whole_group_size(_fill_among(r))


def _whole_group_size(among: str | list[dict] | None) -> int | None:
    size = len(catalog.group(among).members) if isinstance(among, str) else len(among or [])
    return size if 2 <= size <= MAX_REGIONS else None


# One filler per FIELD NAME. Each accepts the flat reader shape AND the Question shape; returns JSON-ready data or None.
# Keys must equal the union of all Question fields (tests/test_registry.py).
FILL: dict[str, Callable[[dict], Any]] = {
    "region": _fill_region,
    "point": _fill_point,
    "tests": _fill_tests,
    "variable": lambda r: _known_variable(r.get("variable")) or _nth_test(r, 0),
    "x": lambda r: _known_variable(r.get("x")) or _nth_test(r, 0),
    "y": lambda r: _known_variable(r.get("y")) or _nth_test(r, 1),
    "window": _fill_window,
    "baseline": _fill_baseline,
    "among": _fill_among,
    "metric": lambda r: _str(r.get("metric"), ("change", "level")),
    "order": lambda r: _str(r.get("order"), ("highest", "lowest")),
    "top_n": _fill_top_n,
    "year": lambda r: r.get("year") if _int(r.get("year")) else None,
    "satellite": lambda r: _str(r.get("satellite"), get_args(Satellite)),
    "zone": lambda r: _str(r.get("zone"), get_args(Zone)),
    "measure": lambda r: _str(r.get("measure"), get_args(HazeMeasure) + get_args(WaterMeasure)),
    "span": lambda r: _years(r.get("span")),
}


def _word_at(s: str, w: str) -> int:
    i = s.find(w)
    while i >= 0:
        if i == 0 or not w[0].isascii() or not w[0].isalpha() or not (s[i - 1].isascii() and s[i - 1].isalpha()):
            return i
        i = s.find(w, i + 1)
    return -1


def _starts_word(s: str, w: str) -> bool:
    return _word_at(s, w) >= 0


def _words(d: dict[str, list[str]]) -> list[str]:
    return [w.casefold() for lg in ("en", "km") for w in d.get(lg, [])]


def _tests(s: str, sentence_order: bool) -> list[dict]:
    hits = {v.id: {w: i for w in _words(v.keywords) if (i := _word_at(s, w)) >= 0} for v in catalog.variables()}
    every = {w for h in hits.values() for w in h}
    found = []
    for v in catalog.variables():
        up = {w for w in _words(v.up) if _starts_word(s, w)}
        down = {w for w in _words(v.down) if _starts_word(s, w)}
        # an English keyword inside a longer hit loses to it: "wet-bulb heat" names wetbulb, not heat
        found.append((v.id, [i for w, i in hits[v.id].items() if not (w.isascii() and any(w != x and w in x for x in every))],
                      up, down))
    named = {w for _, hit, up, down in found if hit for w in up | down}
    taken: set[str] = set()
    tests = []
    for vid, hit, up, down in found:
        # a cue word inside another variable's keyword hit belongs to it: "sea getting warmer" is sst, not heat
        up, down = (ws if hit else {w for w in ws - named - taken if not any(w in x for x in every)} for ws in (up, down))
        taken |= up | down
        if hit or up or down:
            tests.append((min(hit + [_word_at(s, w) for w in up | down]),
                          {"variable": vid, "direction": "up" if up and not down else "down" if down and not up else "any"}))
    return [t for _, t in (sorted(tests, key=lambda p: p[0]) if sentence_order else tests)]


def _window(s: str) -> tuple[int | None, int | None]:
    if m := next((m for m in (p.search(s) for p in SPAN) if m), None):
        return int(m[1]), int(m[2])
    if m := SINCE.search(s):
        return int(m[1]), None
    if m := DECADE.search(s):
        start = int(m[1] or m[2])
        return start, start + 9
    return None, None


def _group(s: str) -> str | None:
    aliases = sorted(((a, g.id) for g in catalog.load().groups for a in _words(g.aliases)), key=lambda h: -len(h[0]))
    return next((g for a, g in aliases if _starts_word(s, a)), None) or next((g for p, g in GROUP_CUES if re.search(p, s)), None)


def _leads(s: str, lang: Lang) -> list[str]:
    for known in sorted((k for v in catalog.variables() for k in _words(v.keywords)), key=len, reverse=True):
        s = s.replace(known, " ")
    w = Words(lang)
    return [w(key) for cue, key in NOT_MEASURED if re.search(cue, s)]


def read_keywords(text: str, lang: Lang) -> dict:
    s = ascii_digits(" ".join(text.casefold().split()))
    kind = next((k for k, cues in CUES if any(re.search(c, s) for c in cues)), None)
    tests = _tests(s, sentence_order=kind == "relate")   # relate reads the first variable named as x
    regions = catalog.find_regions(s, "km")
    region = regions[0] if regions else None
    place = None if region else PLACE_NAME.search(ascii_digits(text))
    window_from, window_to = _window(s)
    group = _group(s)
    one_place = len(regions) == 1 or (not regions and place)
    if kind == "rank" and window_to is not None and one_place and group is None and not RANKING.search(s):
        kind = "baseline"
    if kind in HOTTEST_MEANS_HEAT and HOTTEST.search(s) and not HOTTEST_TIME.search(s):
        tests = [{**t, "variable": "heat"} if t["variable"] == "hottest" else t for t in tests]
    year = next((int(y) for y in YEAR.findall(s) if int(y) not in (window_from, window_to)), None)
    top = TOP.search(s)
    return {
        "kind": kind,
        "tests": tests,
        "region": None if region is None else region.model_dump(),
        "place_name": place[1] if place else None,
        "window_from": window_from,
        "window_to": window_to,
        "year": year,
        "among": group if kind == "rank" else None,
        "top_n": int(top[1]) if top else None,
        "metric": "level" if kind == "rank" and LEVEL_CUE.search(s) and not CHANGE_CUE.search(s) else None,
        "order": "lowest" if kind == "rank" and (LOWEST_CUE.search(s) or tests[:1] and tests[0]["direction"] == "down") else None,
        "leads": _leads(s, lang),
        "unmapped": [],
    }
