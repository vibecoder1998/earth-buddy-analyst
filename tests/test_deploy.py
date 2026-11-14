import json

from earthbuddy import ROOT


def test_vercel_json_configures_main_function():
    # The Vercel FastAPI preset routes every path to `app` in main.py; a rewrite breaks paths.
    cfg = json.loads((ROOT / "vercel.json").read_text())
    fn = cfg["functions"]["main.py"]
    assert fn["maxDuration"] == 300
    assert "data" in fn["includeFiles"] and "web" in fn["includeFiles"]
    assert "rewrites" not in cfg
