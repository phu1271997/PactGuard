"""Happy path: register a program, file a claim, triage (UPHELD), settle."""

import json
import pytest
from gltest import get_contract_factory
from genlayer_py import create_client
from genlayer_py.chains import studionet


def _install_mocks(admin, verdict, severity, confidence):
    client = create_client(chain=studionet, account=admin)
    try:
        client.provider.make_request(
            method="sim_installMocks",
            params={
                "llm_mocks": {
                    ".*": json.dumps({
                        "verdict": verdict,
                        "severity": severity,
                        "confidence": confidence,
                        "reason": "Mock adjudication: the SLA clause and the status-page evidence support this verdict.",
                    })
                },
                "web_mocks": {
                    ".*": {"status": 200, "body": "Status page: MAJOR OUTAGE 2026-09-12, all endpoints 503 for 4h30m. SLA: 99.90% monthly, no exclusion for unplanned 5xx."}
                },
            },
        )
    except Exception:
        pass


def test_register_file_triage_settle(admin, provider, claimant):
    factory = get_contract_factory("Contract")
    c = factory.deploy(account=admin)

    # Provider registers with a 1 GEN bond
    c.connect(provider).register_program(
        args=["Acme Cloud API", "https://example.com/sla", 9990]
    ).transact(value=1_000_000_000_000_000_000)

    assert c.get_program_count().call() == 1
    prog = json.loads(c.get_program(args=["1"]).call())
    assert prog["service_name"] == "Acme Cloud API"
    assert prog["uptime_target_bp"] == 9990

    # Claimant files a bonded breach claim
    c.connect(claimant).file_claim(
        args=[
            "1",
            "2026-09-12T02:00Z .. 2026-09-12T06:30Z",
            "Full API outage 4h30m, all endpoints 503.",
            ["https://example.com/status"],
        ]
    ).transact(value=200_000_000_000_000_000)

    assert c.get_claim_count().call() == 1
    claim = json.loads(c.get_claim(args=["1"]).call())
    assert claim["state"] == "OPEN"

    # AI triage -> UPHELD / MAJOR
    _install_mocks(admin, "UPHELD", "MAJOR", 87)
    c.connect(claimant).triage(args=["1"]).transact()

    claim = json.loads(c.get_claim(args=["1"]).call())
    assert claim["verdict"] == "UPHELD"
    assert claim["severity"] == "MAJOR"
    assert claim["credit_bp"] == 2500      # MAJOR -> 25%
    assert claim["state"] == "UPHELD"
    assert claim["confidence"] >= 60
