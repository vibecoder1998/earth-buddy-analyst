import json

from earthbuddy import ROOT


def test_vercel_json_routes_everything_to_main():
    cfg = json.loads((ROOT / "vercel.json").read_text())
    assert cfg["functions"]["main.py"]["maxDuration"] == 300
    assert {"source": "/(.*)", "destination": "/main.py"} in cfg["rewrites"]
