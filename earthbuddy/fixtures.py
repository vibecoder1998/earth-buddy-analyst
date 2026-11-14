"""Synthetic POWER-shaped responses for EB_OFFLINE=1 and tests. Deterministic per request."""
import httpx


def handler(request: httpx.Request) -> httpx.Response:
    """POWER point and regional JSON: rng seeded by crc32 of the URL; per-parameter mean, seasonal cycle,
    trend and noise; month 13 annual row; header.fill_value = -999. Any other host answers 503, so offline
    geocoding of an unknown name fails closed while catalog names still resolve."""
    # TODO row 3: PARAMS = {"T2M": (mean, seasonal_amp, trend_per_decade, noise), "PRECTOTCORR": ..., ...}
    raise NotImplementedError
