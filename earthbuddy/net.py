"""The only network door: HTTP (cache, retries, 3 in flight), a generic POST and GET, and Claude on Amazon Bedrock. Offline and tests swap the transport."""
import functools
import json
import os
import threading
import time
from typing import Callable, Iterator, NamedTuple
from urllib.parse import urlsplit

import anthropic
import httpx

from . import SOURCES, cache, fixtures
from .types import AIFailed, DataSourceError

OFFLINE: bool = os.environ.get("EB_OFFLINE") == "1"
MAX_INFLIGHT = 3          # NASA POWER politeness, not a statistic
ATTEMPTS = 4
BACKOFF_S = 1.5
MODEL_TIMEOUT_S = 10

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
    """Cache hit, else GET with retries. Raises DataSourceError(message, status, url). The only GET for data."""
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


class Posted(NamedTuple):
    body: bytes
    content_type: str


class Streamed(NamedTuple):
    chunks: Iterator[bytes]
    content_type: str


def post(url: str, *, headers: dict, json: dict | None = None, data: dict | None = None,
         files: dict | None = None, timeout_s: float = 30) -> Posted:
    """POST, no cache, no POWER slot. One retry on a transport error or 5xx; a 4xx raises DataSourceError at once."""
    r = _send(url, headers=headers, json=json, data=data, files=files, timeout=timeout_s)
    try:
        return Posted(r.read(), r.headers.get("content-type", ""))
    finally:
        r.close()


def get(url: str, *, timeout_s: float = 30) -> Posted:
    """`post` as a GET, for message transport (a Telegram voice file), never data."""
    r = _send(url, method="GET", timeout=timeout_s)
    try:
        return Posted(r.read(), r.headers.get("content-type", ""))
    finally:
        r.close()


def post_stream(url: str, *, headers: dict, json: dict, accept: str, timeout_s: float = 30) -> Streamed:
    """`post`, with the body streamed. A reply whose content type does not start with `accept` raises DataSourceError."""
    r = _send(url, headers=headers, json=json, timeout=timeout_s)
    content_type = r.headers.get("content-type", "")
    if not content_type.startswith(accept):
        r.close()
        raise DataSourceError(f"content type {content_type!r}", r.status_code, url)
    return Streamed(_chunks(r), content_type)


def _send(url: str, method: str = "POST", **kw) -> httpx.Response:
    status = None
    for _ in range(2):
        try:
            r = _http().send(_http().build_request(method, url, **kw), stream=True)
        except httpx.TransportError:
            status = None
            continue
        status = r.status_code
        if status < 400:
            return r
        r.close()
        if status < 500:
            raise DataSourceError(f"HTTP {status}", status, url)
    raise DataSourceError("unavailable after 2 attempts", status, url)


def _chunks(r: httpx.Response) -> Iterator[bytes]:
    try:
        yield from r.iter_bytes()
    finally:
        r.close()


def refuse_offline_on_vercel() -> None:
    if OFFLINE and os.environ.get("VERCEL"):
        raise SystemExit("refusing to start: EB_OFFLINE=1 serves synthetic data, which must never reach the Vercel deploy")


def ai_available() -> bool:
    """AWS credentials as the SDK reads them: a Bedrock API key, or an access key pair."""
    env = os.environ.get
    return not OFFLINE and bool(env("AWS_BEARER_TOKEN_BEDROCK") or (env("AWS_ACCESS_KEY_ID") and env("AWS_SECRET_ACCESS_KEY")))


def model_id() -> str:
    return os.environ.get("EB_MODEL", "au.anthropic.claude-haiku-4-5-20251001-v1:0")


def ask_model(system: str, user: str, schema: dict, max_tokens: int) -> dict:
    """Raises AIFailed on no AWS credentials, timeout, API error, stop_reason != "end_turn" (incl. "refusal"), or bad JSON."""
    if _model is not None:
        text = _model(system, user, schema, max_tokens)
    else:
        if not ai_available():
            raise AIFailed("no AWS credentials")
        try:
            reply = _anthropic().messages.create(
                model=model_id(),
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
        except (anthropic.AnthropicError, RuntimeError, ImportError) as e:   # RuntimeError, ImportError: SigV4 signing (no credentials, no botocore)
            raise AIFailed(type(e).__name__) from None
        if reply.stop_reason != "end_turn":
            raise AIFailed(f"stop_reason {reply.stop_reason}")
        text = next((b.text for b in reply.content if b.type == "text"), "")
    try:
        out = json.loads(text)
    except (TypeError, ValueError):
        raise AIFailed("the reply is not JSON") from None
    if not isinstance(out, dict):
        raise AIFailed("the reply is not a JSON object")
    return out


@functools.cache
def _anthropic() -> anthropic.AnthropicBedrock:
    return anthropic.AnthropicBedrock(aws_region=os.environ.get("EB_AWS_REGION", "ap-southeast-2"),
                                      timeout=MODEL_TIMEOUT_S, max_retries=0)


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
