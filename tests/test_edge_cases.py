"""Edge cases and guard rails (bonds, validation, double-settle)."""

import json
import pytest
from gltest import get_contract_factory


def _deploy(admin):
    return get_contract_factory("Contract").deploy(account=admin)


def test_provider_bond_below_minimum(admin, provider):
    c = _deploy(admin)
    with pytest.raises(Exception):
        c.connect(provider).register_program(
            args=["Cheap Co", "https://example.com/sla", 9990]
        ).transact(value=1)  # below 0.5 GEN


def test_terms_url_must_be_https(admin, provider):
    c = _deploy(admin)
    with pytest.raises(Exception):
        c.connect(provider).register_program(
            args=["No TLS", "http://example.com/sla", 9990]
        ).transact(value=1_000_000_000_000_000_000)


def test_uptime_target_out_of_range(admin, provider):
    c = _deploy(admin)
    with pytest.raises(Exception):
        c.connect(provider).register_program(
            args=["Bad target", "https://example.com/sla", 20000]
        ).transact(value=1_000_000_000_000_000_000)


def test_claim_requires_evidence_and_bond(admin, provider, claimant):
    c = _deploy(admin)
    c.connect(provider).register_program(
        args=["Acme", "https://example.com/sla", 9990]
    ).transact(value=1_000_000_000_000_000_000)

    # no evidence urls
    with pytest.raises(Exception):
        c.connect(claimant).file_claim(
            args=["1", "window", "desc", []]
        ).transact(value=200_000_000_000_000_000)

    # bond below minimum
    with pytest.raises(Exception):
        c.connect(claimant).file_claim(
            args=["1", "window", "desc", ["https://example.com/status"]]
        ).transact(value=1)


def test_claim_on_missing_program(admin, claimant):
    c = _deploy(admin)
    with pytest.raises(Exception):
        c.connect(claimant).file_claim(
            args=["999", "window", "desc", ["https://example.com/status"]]
        ).transact(value=200_000_000_000_000_000)


def test_seeded_settled_claim_cannot_double_settle(admin, provider, claimant):
    c = _deploy(admin)
    prov = str(getattr(provider, "address", provider))
    clm = str(getattr(claimant, "address", claimant))

    c.connect(admin).admin_seed_program(
        args=[prov, "Acme", "https://example.com/sla", 9990, 5_000_000_000_000_000_000]
    ).transact(value=0)
    c.connect(admin).admin_seed_claim(
        args=["1", clm, "window", "desc", ["https://example.com/status"],
              200_000_000_000_000_000, "SETTLED", "UPHELD", "MAJOR", 90, "seeded"]
    ).transact()

    claim = json.loads(c.get_claim(args=["1"]).call())
    assert claim["state"] == "SETTLED"
    assert claim["payout_done"] is True

    with pytest.raises(Exception):
        c.connect(admin).settle(args=["1"]).transact()
