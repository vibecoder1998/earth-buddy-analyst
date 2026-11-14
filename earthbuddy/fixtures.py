"""Synthetic POWER-shaped responses for EB_OFFLINE=1 and tests. Deterministic per request."""
import math
import random
import zlib

import httpx

FILL = -999.0

PARAMS: dict[str, tuple[float, float, float, float]] = {
    "T2M": (27.5, 2.0, 0.4, 0.3),
    "T2M_MAX": (32.5, 2.5, 0.4, 0.4),
    "T2M_MIN": (23.5, 2.0, 0.35, 0.4),
    "T2M_RANGE": (9.0, 2.0, 0.0, 0.4),
    "TS": (28.5, 2.5, 0.4, 0.4),
    "RH2M": (76.0, 8.0, -0.5, 2.0),
    "QV2M": (17.0, 2.0, 0.2, 0.5),
    "PRECTOTCORR": (4.5, 4.0, -0.1, 1.0),
    "GWETROOT": (0.6, 0.1, 0.0, 0.03),
    "GWETTOP": (0.55, 0.15, 0.0, 0.04),
    "EVLAND": (3.2, 1.0, 0.0, 0.3),
    "WS10M": (2.6, 0.8, 0.0, 0.2),
    "TQV": (48.0, 8.0, 0.4, 2.0),
    "TO3": (265.0, 8.0, 0.0, 3.0),
    "SNODP": (0.0, 0.0, 0.0, 0.0),
    "FROST_DAYS": (0.0, 0.0, 0.0, 0.0),
    "FRSEAICE": (0.0, 0.0, 0.0, 0.0),
    "ALLSKY_SFC_SW_DWN": (5.2, 0.8, 0.0, 0.3),
    "CLOUD_AMT": (60.0, 20.0, 0.0, 5.0),
    "AOD_55_ADJ": (0.35, 0.15, 0.0, 0.06),
    "ALLSKY_SRF_ALB": (0.15, 0.02, 0.0, 0.01),
    "ALLSKY_SFC_UV_INDEX": (9.5, 2.0, 0.0, 0.5),
}


def _monthly(rng: random.Random, param: str, start: int, end: int) -> dict[str, float]:
    mean, amp, trend, noise = PARAMS[param]
    out: dict[str, float] = {}
    for year in range(start, end + 1):
        months = []
        for month in range(1, 13):
            v = mean + amp * math.cos(2 * math.pi * (month - 4) / 12) + trend * (year - 2000) / 10 + rng.gauss(0, noise)
            months.append(v if param.startswith(("T2M", "TS")) else max(v, 0.0))
            out[f"{year}{month:02d}"] = round(months[-1], 3)
        out[f"{year}13"] = round(sum(months) / 12, 3)
    return out


def handler(request: httpx.Request) -> httpx.Response:
    url = request.url
    if url.host != "power.larc.nasa.gov" or not url.path.endswith("/temporal/monthly/point"):
        return httpx.Response(503, json={"messages": ["synthetic POWER serves monthly points only"]})
    q = url.params
    params = q["parameters"].split(",")
    if not set(params) <= PARAMS.keys():
        return httpx.Response(422, json={"messages": [f"unknown parameter in {q['parameters']}"]})
    rng = random.Random(zlib.crc32(str(url).encode()))
    start, end = int(q["start"]), int(q["end"])
    lat, lon = float(q["latitude"]), float(q["longitude"])
    return httpx.Response(200, json={
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat, 0.0]},
        "properties": {"parameter": {p: _monthly(rng, p, start, end) for p in params}},
        "header": {"title": "Synthetic data, not NASA", "fill_value": FILL,
                   "start": f"{start}0101", "end": f"{end}1231"},
    })
