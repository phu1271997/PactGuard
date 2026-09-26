"""Challenge flow: a triaged verdict is disputed, re-triaged, and finalized."""

import json
import pytest
from gltest import get_contract_factory
from genlayer_py import create_client
from genlayer_py.chains import studionet


def _mocks(admin, verdict, severity, confidence):
    client = create_client(chain=studionet, account=admin)
    try:
        client.provider.make_request(
            method="sim_installMocks",
            params={
                "llm_mocks": {".*": json.dumps({
                    "verdict": verdict, "severity": severity,
                    "confidence": confidence, "reason": "mock reason"})},
                "web_mocks": {".*": {"status": 200, "body": "mock evidence body"}},
            },
        )
    except Exception:
        pass


def test_rejected_then_challenged_then_retriaged(admin, provider, claimant):
    c = get_contract_factory("Contract").deploy(account=admin)

    c.connect(provider).register_program(
        args=["Acme Cloud API", "https://example.com/sla", 9990]
    ).transact(value=3_000_000_000_000_000_000)

    c.connect(claimant).file_claim(
        args=["1", "2026-09-20T14:00Z .. 14:07Z", "Latency blip 7 min",
              ["https://example.com/status"]]
    ).transact(value=200_000_000_000_000_000)

    # First pass: REJECTED
    _mocks(admin, "REJECTED", "NONE", 80)
    c.connect(claimant).triage(args=["1"]).transact()
    claim = json.loads(c.get_claim(args=["1"]).call())
    assert claim["verdict"] == "REJECTED"
    assert claim["state"] == "REJECTED"

    # Claimant challenges (bond >= claim bond)
    c.connect(claimant).challenge(
        args=["1", "https://example.com/rebuttal", "Latency was actually a full 503 outage"]
    ).transact(value=200_000_000_000_000_000)
    claim = json.loads(c.get_claim(args=["1"]).call())
    assert claim["state"] == "CHALLENGED"
    assert claim["challenged_once"] is True

    # Re-triage flips to UPHELD and settles (final)
    _mocks(admin, "UPHELD", "MAJOR", 85)
    c.connect(admin).retriage(args=["1"]).transact()
    claim = json.loads(c.get_claim(args=["1"]).call())
    assert claim["verdict"] == "UPHELD"
    assert claim["state"] == "SETTLED"
    assert claim["payout_done"] is True


def test_wrong_party_cannot_challenge(admin, provider, claimant):
    c = get_contract_factory("Contract").deploy(account=admin)
    c.connect(provider).register_program(
        args=["Acme", "https://example.com/sla", 9990]
    ).transact(value=3_000_000_000_000_000_000)
    c.connect(claimant).file_claim(
        args=["1", "w", "d", ["https://example.com/status"]]
    ).transact(value=200_000_000_000_000_000)

    _mocks(admin, "UPHELD", "MAJOR", 88)
    c.connect(claimant).triage(args=["1"]).transact()

    # On an UPHELD claim, only the provider may challenge — claimant must fail
    with pytest.raises(Exception):
        c.connect(claimant).challenge(
            args=["1", "https://example.com/x", "no"]
        ).transact(value=200_000_000_000_000_000)
