"""The only network door: HTTP (cache, retries, 3 in flight) and the self-hosted model at EB_LLM_URL. Offline and tests swap the transport."""
import functools
import json
import os
import threading
import time
from typing import Callable, NamedTuple
from urllib.parse import urlsplit

import httpx

from . import SOURCES, cache, fixtures
from .types import AIFailed, DataSourceError

OFFLINE: bool = os.environ.get("EB_OFFLINE") == "1"
MAX_INFLIGHT = 3          # NASA POWER politeness, not a statistic
ATTEMPTS = 4
BACKOFF_S = 1.5
AI_TIMEOUT_S = 30         # a local model may load on the first call, not a statistic

_slots = threading.BoundedSemaphore(MAX_INFLIGHT)
_transport: httpx.BaseTransport | None = httpx.MockTransport(fixtures.handler) if OFFLINE else None   # the one offline branch
_client: httpx.Client | None = None
_model: Callable[[str, str, dict, int], str] | None = None
sleep = time.sleep        # tests replace with a no-op


@functools.cache
def _registered() -> frozenset[str]:
    return frozenset(s["id"] for s in json.loads(SOURCES.read_text()))


def is_data_host(host: str) -> bool:
    host = host.lower()
    return host.endswith(".nasa.gov") or host == "nasa-power.s3.amazonaws.com"


class Fetched(NamedTuple):
    payload: dict
    cached: bool
    url: str


def get_json(url: str, *, ttl_days: float, source: str, headers: dict | None = None) -> Fetched:
    """Cache hit, else GET with retries. Raises DataSourceError(message, status, url). The only HTTP call in the package."""
    if source not in _registered():
        raise ValueError(f"source {source!r} is not in data/sources.json")
    if not is_data_host(urlsplit(url).hostname or ""):
        raise ValueError(f"{url} is not on an allowed data host")
    if (hit := cache.get(url, ttl_days)) is not None:
        return Fetched(hit, True, url)
    status = None
    for n in range(ATTEMPTS):
        if n:
            sleep(BACKOFF_S * 2 ** (n - 1))
        try:
            with _slots:
                r = _http().get(url, headers=headers)
        except httpx.TransportError:
            status = None
            continue
        status = r.status_code
        if status == 200:
            try:
                payload = r.json()
            except ValueError:
                raise DataSourceError("the response is not JSON", status, url) from None
            cache.put(url, payload, source)
            return Fetched(payload, False, url)
        if status != 429 and status < 500:
            raise DataSourceError(f"HTTP {status}", status, url)
    raise DataSourceError(f"unavailable after {ATTEMPTS} attempts", status, url)


def refuse_offline_on_vercel() -> None:
    if OFFLINE and os.environ.get("VERCEL"):
        raise SystemExit("refusing to start: EB_OFFLINE=1 serves synthetic data, which must never reach the Vercel deploy")


def ai_available() -> bool:
    return bool(os.environ.get("EB_LLM_URL")) and not OFFLINE


def model_id() -> str:
    return os.environ.get("EB_MODEL", "qwen3:8b")


def ask_model(system: str, user: str, schema: dict, max_tokens: int) -> dict:
    """One OpenAI-style chat completion with a strict JSON schema.
    Raises AIFailed on no EB_LLM_URL, HTTP error, finish_reason != "stop", or a reply that is not a JSON object."""
    if _model is not None:
        text = _model(system, user, schema, max_tokens)
    else:
        if not ai_available():
            raise AIFailed("no model server")
        key = os.environ.get("EB_LLM_KEY")
        try:
            r = _http().post(
                f"{os.environ['EB_LLM_URL'].rstrip('/')}/chat/completions",
                timeout=AI_TIMEOUT_S,
                headers={"Authorization": f"Bearer {key}"} if key else None,
                json={
                    "model": model_id(),
                    "max_tokens": max_tokens,
                    "temperature": 0,
                    "reasoning_effort": "none",
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "response_format": {"type": "json_schema",
                                        "json_schema": {"name": "reply", "strict": True, "schema": schema}},
                },
            )
            r.raise_for_status()
            choice = r.json()["choices"][0]
            finish, text = choice["finish_reason"], choice["message"]["content"]
        except (httpx.HTTPError, ValueError, LookupError, TypeError) as e:
            raise AIFailed(type(e).__name__) from None
        if finish != "stop":
            raise AIFailed(f"finish_reason {finish}")
    try:
        out = json.loads(text)
    except (TypeError, ValueError):
        raise AIFailed("the reply is not JSON") from None
    if not isinstance(out, dict):
        raise AIFailed("the reply is not a JSON object")
    return out


def stub(transport: httpx.BaseTransport | None = None, model: Callable[[str, str, dict, int], str] | None = None) -> None:
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
