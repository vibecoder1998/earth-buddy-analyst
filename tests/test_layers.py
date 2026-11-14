"""The module map's "never imports" column (docs/ARCHITECTURE.md), plus the one-home rule for thresholds."""
import ast
import re
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "earthbuddy"
ALL = {"types", "stats", "words", "cache", "fixtures", "net", "catalog", "power", "geocode", "series",
       "analyses", "reader", "explainer", "voice", "server"}

NEVER = {
    "types": ALL,
    "stats": ALL - {"types"},
    "words": ALL - {"types"},
    "cache": ALL,
    "fixtures": ALL,
    "net": {"catalog", "power", "series", "analyses", "reader", "explainer", "server"},
    "catalog": {"net", "power", "series", "stats", "analyses", "reader"},
    "power": {"catalog", "series", "stats", "analyses"},
    "geocode": {"net", "power", "series", "stats", "analyses", "reader"},
    "series": {"analyses", "reader", "net"},
    "analyses": {"reader", "explainer", "server", "power"},
    "reader": {"series", "power", "explainer", "server"},
    "explainer": {"series", "power", "reader", "server"},
    "voice": ALL - {"types", "net", "catalog"},
    "server": set(),
}


def _imports(path: Path) -> set[str]:
    out = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level == 0 and not mod.startswith("earthbuddy"):
                continue
            parts = [p for p in mod.split(".") if p and p != "earthbuddy"]
            if parts:
                out.add(parts[0])
            else:
                out |= {a.name for a in node.names}
        elif isinstance(node, ast.Import):
            out |= {a.name.split(".")[1] for a in node.names if a.name.startswith("earthbuddy.")}
    return out & ALL


def _module_of(path: Path) -> str:
    rel = path.relative_to(PKG).parts
    return rel[0] if len(rel) > 1 else path.stem


def test_layers():
    bad = []
    for path in PKG.rglob("*.py"):
        mod = _module_of(path)
        if mod in NEVER:
            hit = _imports(path) & NEVER[mod] - {mod}
            if hit:
                bad.append(f"{path.relative_to(PKG)} imports {sorted(hit)}")
    assert not bad, bad


def test_only_server_and_telegram_import_voice():
    importers = sorted(_module_of(p) for p in PKG.rglob("*.py") if "voice" in _imports(p) and p.stem != "voice")
    assert importers == ["server", "telegram"], importers


def test_voice_does_not_touch_httpx():
    assert "httpx" not in (PKG / "voice.py").read_text()


def test_thresholds_live_only_in_stats():
    pattern = re.compile(r"(?<![\w.])(0\.05|0\.10|1\.96)(?![\d])")
    bad = [str(p.relative_to(PKG)) for p in PKG.rglob("*.py") if p.name != "stats.py" and pattern.search(p.read_text())]
    assert not bad, bad
