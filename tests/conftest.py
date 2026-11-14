import httpx
import pytest

from earthbuddy import cache, net


def _refuse(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected network call: {request.url}")


def _refuse_model(*_):
    raise AssertionError("unexpected model call")


@pytest.fixture(autouse=True)
def sealed(monkeypatch):
    """Every test: in-memory cache, no backoff sleeps, no network, no model. Ask for a stub to allow traffic."""
    monkeypatch.setenv("EB_DB", ":memory:")
    cache.reset()
    monkeypatch.setattr(net, "sleep", lambda s: None)
    net.stub(transport=httpx.MockTransport(_refuse), model=_refuse_model)
    yield
    cache.reset()
