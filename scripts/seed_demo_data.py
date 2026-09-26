#!/usr/bin/env python3
"""Seed PactGuard with demo programs + claims on studionet (admin pre-baked
verdicts so the live app has content without waiting on the LLM every time).

Usage:
    source ~/.genlayer/env.sh
    python3 scripts/seed_demo_data.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from genlayer_py import create_account, create_client
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionStatus

ROOT = Path(__file__).resolve().parent.parent
DEP = ROOT / "deployments.json"


def retry(fn, tries=5, delay=3):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"    [!] {str(e)[:120]} — retry in {delay}s")
            time.sleep(delay)


def main() -> int:
    key = os.environ.get("GENLAYER_PRIVATE_KEY")
    if not key:
        print("ERROR: source ~/.genlayer/env.sh first", file=sys.stderr)
        return 1
    if not DEP.exists():
        print("ERROR: deploy first (deployments.json missing)", file=sys.stderr)
        return 1

    addr = json.loads(DEP.read_text())["contracts"]["PactGuard"]["address"]
    account = create_account(key)
    client = create_client(chain=studionet, account=account)

    # extra demo wallets (providers / claimants)
    def addr_of(env):
        k = os.environ.get(env)
        return create_account(k).address if k and "REPLACE_ME" not in k else account.address

    provider1 = addr_of("GENLAYER_PRIVATE_KEY_2")
    provider2 = addr_of("GENLAYER_PRIVATE_KEY_3")
    claimant1 = addr_of("GENLAYER_PRIVATE_KEY_4")
    claimant2 = addr_of("GENLAYER_PRIVATE_KEY_5")

    print("=" * 55)
    print(f"Seeding PactGuard @ {addr}")
    print("=" * 55)

    prog_cnt = int(retry(lambda: client.read_contract(address=addr, function_name="get_program_count")) or 0)

    if prog_cnt < 1:
        print("[+] Program 1: Acme Cloud API (99.90% SLA)")
        tx = retry(lambda: client.write_contract(
            address=addr, function_name="admin_seed_program",
            args=[provider1, "Acme Cloud API",
                  "https://raw.githubusercontent.com/genlayerlabs/genlayer-docs/main/README.md",
                  9990, 5000000000000000000],  # 5 GEN bond
            account=account, value=0,
        ))
        retry(lambda: client.wait_for_transaction_receipt(tx, status=TransactionStatus.ACCEPTED, interval=3000, retries=40))

        print("[+] Program 2: Nimbus DB Cluster (99.95% SLA)")
        tx = retry(lambda: client.write_contract(
            address=addr, function_name="admin_seed_program",
            args=[provider2, "Nimbus Managed Postgres",
                  "https://raw.githubusercontent.com/genlayerlabs/genlayer-docs/main/README.md",
                  9995, 8000000000000000000],  # 8 GEN bond
            account=account, value=0,
        ))
        retry(lambda: client.wait_for_transaction_receipt(tx, status=TransactionStatus.ACCEPTED, interval=3000, retries=40))

    claim_cnt = int(retry(lambda: client.read_contract(address=addr, function_name="get_claim_count")) or 0)

    seeds = [
        # program_id, claimant, window, description, urls, bond, state, verdict, severity, conf, reason
        ("1", claimant1,
         "2026-09-12T02:00Z .. 2026-09-12T06:30Z",
         "Full API outage for 4h30m during business hours; all /v1 endpoints returned 503. Status page confirmed a major incident.",
         ["https://raw.githubusercontent.com/genlayerlabs/genlayer-docs/main/README.md"],
         200000000000000000, "UPHELD", "UPHELD", "MAJOR", 87,
         "The SLA promises 99.90% monthly uptime with no scheduled-maintenance exclusion for unplanned 5xx outages. Evidence shows a 4.5h sustained full outage, which breaches the monthly budget and constitutes a MAJOR core-service failure."),
        ("1", claimant2,
         "2026-09-20T14:00Z .. 2026-09-20T14:07Z",
         "Elevated latency for ~7 minutes. I believe this breaches the SLA.",
         ["https://raw.githubusercontent.com/genlayerlabs/genlayer-docs/main/README.md"],
         150000000000000000, "REJECTED", "REJECTED", "NONE", 82,
         "The SLA measures availability, not latency, and excludes brief degradations under the monthly error budget. A 7-minute latency blip does not exhaust the 99.90% budget and is not a qualifying outage; claim rejected."),
        ("2", claimant1,
         "2026-09-05T00:00Z .. 2026-09-05T03:00Z",
         "Primary node failover caused 3h of write unavailability during a region incident.",
         ["https://raw.githubusercontent.com/genlayerlabs/genlayer-docs/main/README.md"],
         300000000000000000, "SETTLED", "UPHELD", "CRITICAL", 91,
         "SLA guarantees 99.95% write availability. A 3h write outage far exceeds the monthly budget and is data-plane affecting → CRITICAL. Credit paid from the provider bond."),
    ]

    idx = 0
    for s in seeds:
        idx += 1
        if claim_cnt >= idx:
            continue
        pid, claimant, window, desc, urls, bond, state, verdict, sev, conf, reason = s
        print(f"[+] Claim {idx}: program {pid} -> {state}")
        tx = retry(lambda s=s, claimant=claimant, pid=pid, window=window, desc=desc, urls=urls, bond=bond, state=state, verdict=verdict, sev=sev, conf=conf, reason=reason: client.write_contract(
            address=addr, function_name="admin_seed_claim",
            args=[pid, claimant, window, desc, urls, bond, state, verdict, sev, conf, reason],
            account=account,
        ))
        retry(lambda: client.wait_for_transaction_receipt(tx, status=TransactionStatus.ACCEPTED, interval=3000, retries=40))

    print("\n" + "=" * 55)
    print(f"SEED COMPLETE. programs={client.read_contract(address=addr, function_name='get_program_count')} claims={client.read_contract(address=addr, function_name='get_claim_count')}")
    print("=" * 55)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
