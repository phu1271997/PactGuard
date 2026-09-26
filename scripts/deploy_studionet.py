#!/usr/bin/env python3
"""Deploy the PactGuard Intelligent Contract to GenLayer studionet.

Usage:
    source ~/.genlayer/env.sh
    python3 scripts/deploy_studionet.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from genlayer_py import create_account, create_client
from genlayer_py.chains import studionet

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "contracts" / "pactguard.py"


def address_from_receipt(receipt):
    if not receipt:
        return None
    if isinstance(receipt, dict):
        return (
            receipt.get("data", {}).get("contract_address")
            or receipt.get("contract_address")
            or receipt.get("contractAddress")
            or receipt.get("tx_data_decoded", {}).get("contract_address")
        )
    return getattr(receipt, "contract_address", None) or getattr(
        receipt, "contractAddress", None
    )


def main() -> int:
    key = os.environ.get("GENLAYER_PRIVATE_KEY")
    if not key or "REPLACE_ME" in key:
        print("ERROR: GENLAYER_PRIVATE_KEY not set. Run: source ~/.genlayer/env.sh", file=sys.stderr)
        return 1

    account = create_account(key)
    client = create_client(chain=studionet, account=account)
    code = CONTRACT.read_text()

    print("=" * 55)
    print("PactGuard deployment — GenLayer studionet")
    print(f"Deployer: {account.address}")
    print(f"Chain:    {studionet.name} (id={studionet.id})")
    print("=" * 55)

    try:
        client.get_contract_schema_for_code(code.encode())
        print("[+] Schema check: PASSED")
    except Exception as e:
        print(f"[!] Schema check FAILED: {e}", file=sys.stderr)
        return 1

    tx_hash = client.deploy_contract(code=code, account=account)
    print(f"[+] Deploy tx: {tx_hash}")
    receipt = client.wait_for_transaction_receipt(
        transaction_hash=tx_hash, status="FINALIZED", interval=3000, retries=80
    )
    addr = address_from_receipt(receipt)
    if not addr:
        print("[!] Could not extract deployed address", file=sys.stderr)
        return 1
    print(f"[+] PactGuard deployed at: {addr}")

    deployments = {
        "network": "studionet",
        "chainId": studionet.id,
        "deployer": account.address,
        "contracts": {
            "PactGuard": {
                "address": addr,
                "tx": tx_hash,
                "explorer": f"https://genlayer-explorer.vercel.app/address/{addr}",
            }
        },
    }
    (ROOT / "deployments.json").write_text(json.dumps(deployments, indent=2))
    print(f"[v] Wrote deployments.json")

    env_content = (
        f"VITE_PACTGUARD_CONTRACT={addr}\n"
        f"VITE_STUDIO_RPC=https://studio.genlayer.com/api\n"
        f"VITE_CHAIN_ID={studionet.id}\n"
    )
    (ROOT / "frontend" / "src" / "lib").mkdir(parents=True, exist_ok=True)
    (ROOT / "frontend" / ".env").write_text(env_content)
    (ROOT / "frontend" / ".env.example").write_text(
        env_content.replace(addr, "0x...")
    )
    addr_ts = ROOT / "frontend" / "src" / "lib" / "addresses.ts"
    addr_ts.parent.mkdir(parents=True, exist_ok=True)
    addr_ts.write_text(
        f"export const PACTGUARD_CONTRACT = (import.meta.env.VITE_PACTGUARD_CONTRACT || '{addr}') as `0x${{string}}`;\n"
        f"export const RPC_URL = import.meta.env.VITE_STUDIO_RPC || 'https://studio.genlayer.com/api';\n"
    )
    print(f"[v] Wrote frontend/.env + addresses.ts")

    print("\n" + "=" * 55)
    print("DEPLOYMENT COMPLETE")
    print(f"PactGuard: {addr}")
    print("=" * 55)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
