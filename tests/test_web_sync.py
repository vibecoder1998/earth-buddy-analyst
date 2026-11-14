import json
import re
from typing import get_args

from earthbuddy import ROOT
from earthbuddy.analyses import ANALYSES
from earthbuddy.types import Chart, Question

WEB = ROOT / "web"
APP = (WEB / "app.js").read_text()
CHARTS = (WEB / "charts.js").read_text()
MAP = (WEB / "map.js").read_text()
EN_JSON = re.search(r"const EN = /\*json\*/(.*?)/\*end\*/", (WEB / "i18n.js").read_text(), re.S)
assert EN_JSON, "web/i18n.js must hold `const EN = /*json*/{...}/*end*/;`"
EN = json.loads(EN_JSON.group(1))
LITERAL_KEYS = {k for src in (APP, CHARTS, MAP) for k in re.findall(r'\bt\("([^"]+)"', src)}
KEY_PREFIXES = {p for src in (APP, CHARTS, MAP) for p in re.findall(r"\bt\(`([^`$]+)\$\{", src)}


def js_table(src: str, name: str) -> set[str]:
    table = re.search(rf"^const {name} = \{{\n(.*?)^\}};", src, re.S | re.M)
    assert table, f"{name} must sit between `const {name} = {{` and `}};` with one key per line"
    return set(re.findall(r"^\s+(\w+)\s*[:,]", table.group(1), re.M))


def test_editors_cover_every_field_name():
    names = {f for m in get_args(get_args(Question)[0]) for f in m.model_fields} - {"kind"}
    assert js_table(APP, "EDITORS") == names
    assert {f"field.{n}" for n in names} <= EN.keys()


def test_panels_are_known_kinds():
    assert js_table(APP, "PANELS") <= set(ANALYSES)


def test_charts_equal_chart_types():
    types = {m.model_fields["type"].default for m in get_args(get_args(Chart)[0])}
    assert js_table(CHARTS, "CHARTS") == types


def test_every_t_key_exists_in_en():
    assert LITERAL_KEYS <= EN.keys(), LITERAL_KEYS - EN.keys()
    assert all(any(k.startswith(p) for k in EN) for p in KEY_PREFIXES), KEY_PREFIXES


def test_no_unused_en_key():
    unused = [k for k in EN if k not in LITERAL_KEYS and not any(k.startswith(p) for p in KEY_PREFIXES)]
    assert not unused, unused

