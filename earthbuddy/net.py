"""The only network door: HTTP (cache, retries, 3 in flight) and the Anthropic model. Offline and tests swap the transport."""
import functools
import json
import os
import threading
import time
from typing import Callable, NamedTuple

import httpx

from . import SOURCES, cache, fixtures
from .types import AIFailed, DataSourceError

OFFLINE: bool = os.environ.get("EB_OFFLINE") == "1"
MAX_INFLIGHT = 3          # NASA POWER politeness, not a statistic
ATTEMPTS = 4
BACKOFF_S = 1.5

_slots = threading.BoundedSemaphore(MAX_INFLIGHT)
_transport: httpx.BaseTransport | None = httpx.MockTransport(fixtures.handler) if OFFLINE else None   # the one offline branch
_client: httpx.Client | None = None
_model: Callable[[str, str, dict, int], dict] | None = None        # set by stub(); None = real Anthropic call
sleep = time.sleep        # tests replace with a no-op


@functools.cache
def _registered() -> frozenset[str]:
    return frozenset(s["id"] for s in json.loads(SOURCES.read_text()))


class Fetched(NamedTuple):
    payload: dict
    cached: bool
    url: str


def get_json(url: str, *, ttl_days: float, source: str, headers: dict | None = None) -> Fetched:
    """Cache hit, else GET with retries. Raises DataSourceError(message, status, url). The only HTTP call in the package."""
    if source not in _registered():
        raise ValueError(f"source {source!r} is not in data/sources.json")
    # TODO row 3:
    # if hit := cache.get(url, ttl_days): return Fetched(hit, True, url)
    # for n in range(ATTEMPTS):
    #     with _slots: try r = _http().get(url, headers=headers) except httpx.TransportError: remember; sleep; continue
    #     200 -> cache.put(url, r.json(), source); return Fetched(r.json(), False, url)
    #     429 or >= 500 -> sleep(BACKOFF_S * 2 ** n); continue
    #     other 4xx (incl. 422) -> raise DataSourceError(f"HTTP {status}", status, url) at once; power reads 422
    # raise DataSourceError("unavailable after 4 attempts", last_status, url)
    raise NotImplementedError


def ai_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY")) and not OFFLINE


def model_id() -> str:
    return os.environ.get("EB_MODEL", "claude-opus-5-5")


def ask_model(system: str, user: str, schema: dict, max_tokens: int) -> dict:
    """One Messages call: cached system block, json_schema output, effort low, 10 s timeout.
    Raises AIFailed on no key, timeout, API error, stop_reason != "end_turn" (incl. "refusal"), or bad JSON."""
    if _model is not None:
        return _model(system, user, schema, max_tokens)
    # TODO row 5: anthropic.Anthropic(timeout=10).messages.create(model=model_id(), max_tokens=max_tokens,
    #   system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
    #   messages=[{"role": "user", "content": user}],
    #   output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}})
    raise AIFailed("not implemented")


def stub(transport: httpx.BaseTransport | None = None, model: Callable[[str, str, dict, int], dict] | None = None) -> None:
    """Tests only. Replace the HTTP transport and/or the model call."""
    global _transport, _client, _model
    if transport is not None:
        _transport, _client = transport, None
    if model is not None:
        _model = model


def _http() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(transport=_transport, timeout=httpx.Timeout(120, connect=20),
                               headers={"User-Agent": "earth-buddy/1.0"})
    return _client
