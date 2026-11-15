"""Merge tools/grids/<family>.json into catalog.src.json, data/sources.json and docs/16. Safe to re-run.

  .venv/bin/python tools/grids/merge.py gldas grace ...
  then: .venv/bin/python tools/build_catalog.py --extend
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1].parent
SRC, SOURCES, DOC = ROOT / "tools/catalog.src.json", ROOT / "data/sources.json", ROOT / "docs/16-data-sources.md"
ANCHOR = "| `giovanni` |"  # new reference rows go just above this row


def merge(family: str) -> None:
    frag = json.loads((ROOT / "tools/grids" / f"{family}.json").read_text())
    if missing := [v for s in frag["stores"].values() if not (ROOT / "tools/cache/grids" / s["grid"]).exists()
                   for v in [s["grid"]]]:
        sys.exit(f"{family}: grid not written yet: {missing}")
    # catalog.src.json is hand-formatted, so insert text at the end of each object instead of re-dumping it
    text = SRC.read_text()
    have = json.loads(text)
    for key, nxt in (("stores", "variables"), ("variables", "country_aliases")):
        new = {k: x for k, x in frag[key].items() if k not in have[key]}
        if new:
            block = ",\n".join(f"  {json.dumps(k)}: " + json.dumps(x, indent=1, ensure_ascii=False).replace("\n", "\n  ")
                               for k, x in new.items())
            end = f'\n }},\n "{nxt}": '
            assert text.count(end) == 1, f"catalog.src.json layout changed near {key}"
            text = text.replace(end, ",\n" + block + end)
    assert json.loads(text) == have | {k: have[k] | frag[k] for k in ("stores", "variables")}
    SRC.write_text(text)

    reg = json.loads(SOURCES.read_text())
    have = {s["id"] for s in reg}
    reg += [s for s in frag["sources"] if s["id"] not in have]
    SOURCES.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")

    doc = DOC.read_text()
    rows = [r for r in frag["docs16_rows"] if r.split("|")[1].strip() not in doc]
    if rows:
        doc = doc.replace(ANCHOR, "\n".join(rows) + "\n" + ANCHOR, 1)
        DOC.write_text(doc)
    print(f"{family}: {len(frag['variables'])} variables, {len(rows)} doc rows")


if __name__ == "__main__":
    for f in sys.argv[1:]:
        merge(f)
