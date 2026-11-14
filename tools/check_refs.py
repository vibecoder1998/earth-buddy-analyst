"""Resolve every DOI in data/sources.json through doi.org. --markdown prints the README reference list instead."""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

SOURCES = Path(__file__).resolve().parent.parent / "data" / "sources.json"


def resolves(doi: str) -> bool:
    try:
        with urllib.request.urlopen(f"https://doi.org/api/handles/{doi}", timeout=30) as r:
            return r.status == 200 and json.load(r).get("responseCode") == 1
    except (urllib.error.URLError, TimeoutError):
        return False


def markdown(sources: list[dict]) -> str:
    lines = []
    for s in sources:
        link = f"https://doi.org/{s['doi']}" if s["doi"] else s["url"]
        via = f" Read through {s['via']}." if s["via"] else ""
        lines.append(f"- {s['citation']} {link}{via}")
    return "\n".join(lines)


def main() -> int:
    sources = json.loads(SOURCES.read_text())
    if "--markdown" in sys.argv[1:]:
        print(markdown(sources))
        return 0
    failed = 0
    for s in sources:
        if s["doi"]:
            ok = resolves(s["doi"])
            failed += not ok
            print(f"{'resolved' if ok else 'FAILED  '} {s['doi']}  {s['id']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
