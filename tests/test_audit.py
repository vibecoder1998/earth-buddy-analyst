import hashlib
import json

from fastapi.testclient import TestClient

from earthbuddy import catalog
from earthbuddy.analyses import claim
from earthbuddy.server import app

client = TestClient(app)
FROZEN = "17187732ed64d135822627d82964b44b532fe563a4e1cc74aaaab29230ec3721"


def test_audit_returns_8_verdicts_with_no_network():
    claims = client.get("/api/audit").json()["claims"]
    assert len(claims) == 8
    assert all(c["verdict"]["key"] in claim.VERDICTS and c["verdict_word"] for c in claims)


def test_frozen_claims_unchanged():
    claims = json.dumps(catalog.audit()["claims"], sort_keys=True, ensure_ascii=False)
    assert hashlib.sha256(claims.encode()).hexdigest() == FROZEN
