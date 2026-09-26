# 🛡️ PactGuard — Autonomous SLA Breach Escrow on GenLayer

**PactGuard removes discretion from service-level agreements.** A provider posts a
collateral bond and pins its public SLA terms. When a customer claims downtime, the
decision to pay a service credit is not made by the provider — it is made by
**GenLayer validator consensus**, which reads the pinned SLA terms *and* the
provider's public status / incident pages **directly on-chain** and judges whether the
SLA was actually breached and how severely.

> **One-line pitch:** *PactGuard dies without GenLayer — deciding whether an ambiguous
> SLA ("99.9% monthly, excludes scheduled maintenance") was breached requires reading
> unstructured status pages and exercising subjective judgment on-chain, which no
> Solidity contract can do.*

- **Network:** GenLayer **studionet** (chain id `61999`) — deployed via `genlayer-py`.
- **Contract (studionet):** `0xb2cA43d78aaaE0B8888767f2E143321BBced2fEe`
  · [View on Explorer](https://genlayer-explorer.vercel.app/address/0xb2cA43d78aaaE0B8888767f2E143321BBced2fEe)
- **Live dApp:** see the deployment URL in this repo's About / release notes.

---

## Why this needs GenLayer (Axis 1 — GenLayer Fit)

Remove the AI + web-reading and the project collapses: you would be back to a human
support agent deciding claims, i.e. exactly the discretionary denial PactGuard exists to
eliminate. The core decision is **subjective**, has **real money staked**, and depends on
**live web data**:

1. **On-chain web reading** — the contract runs `gl.nondet.web.get` / `web.render` to
   fetch the pinned SLA terms **and** the provider's status / incident pages. No oracle.
2. **Subjective judgment** — an LLM jury interprets the terms (monthly vs per-incident
   budget? scheduled-maintenance exclusion? latency vs availability?) and grades severity
   `MINOR / MAJOR / CRITICAL`.
3. **Money at stake** — provider bond + claimant bond, paid out by the contract.

## Contract design (Axis 2 — Contract Quality)

`contracts/pactguard.py` — a single `gl.Contract` with a full claim lifecycle:

```
OPEN ──triage──▶ UPHELD / REJECTED ──challenge──▶ CHALLENGED ──retriage──▶ SETTLED
                        └───────────────── settle (after window) ─────────▶ SETTLED
```

**Semantic consensus, not schema consensus.** The non-deterministic block returns a JSON
verdict, but the custom `validator_fn` (via `gl.vm.run_nondet`) compares the **meaning**:

```python
if str(mine["verdict"]) != str(leader["verdict"]):        return False  # verdict must agree
if str(mine["severity"]) != str(leader["severity"]):      return False  # credit tier must agree
if (mine_conf >= FLOOR) != (leader_conf >= FLOOR):        return False  # settle-vs-hold threshold
if abs(mine_conf - leader_conf) > 15:                     return False  # confidence proximity
```

Two validators that disagree on the *outcome* (verdict or severity tier) can **never**
reach consensus, even though they phrase their `reason` differently. This is the line
between a toy `strict_eq` contract and a real adjudicator.

**Advanced non-determinism (Axis 2 → 5):** multi-source cross-check — every triage fetches
the SLA terms plus up to three independent evidence pages, and a **bonded challenge +
final re-triage** appeal flow is implemented at the contract level (a rebuttal URL is read
on-chain during re-triage).

**Edge cases handled** (each raises `gl.vm.UserError`): bond below minimum, non-`https`
terms URL, out-of-range uptime target, empty/oversized fields, zero evidence URLs,
double-settle, settling inside an open challenge window, wrong-party challenge, and
low-confidence verdicts (which get a longer challenge window before becoming final).

**Storage safety** (per the GenLayer field rules): `bigint` for money, sized ints for
bounded values, all `TreeMap` keys are `str`, custom structs are `@allow_storage @dataclass`,
and no stored `DynArray` field is mutated in place.

## Architecture

```
contracts/pactguard.py     # the Intelligent Contract
tests/                     # gltest suite (happy path, edge cases, challenge flow)
scripts/deploy_studionet.py
scripts/seed_demo_data.py  # admin-seeded demo programs + claims
scripts/live_test.py       # real multi-wallet end-to-end lifecycle
frontend/                  # Vite + React + Tailwind dApp (genlayer-js)
```

The frontend calls the deployed contract for real: MetaMask signs writes
(`createClient({ chain: studionet, account })`), reads go through `genlayer-js`, the AI
`reason` and confidence are shown for every verdict, and each pending consensus tx links to
the Explorer.

## Deploy to studionet

```bash
source ~/.genlayer/env.sh            # loads GENLAYER_PRIVATE_KEY (+ extra funded wallets)
python3 scripts/deploy_studionet.py  # deploys, writes deployments.json + frontend/.env
python3 scripts/seed_demo_data.py    # optional: seed demo programs/claims
```

`deploy_studionet.py` runs a schema pre-flight, waits for `FINALIZED`, and writes the
contract address into `frontend/.env` and `frontend/src/lib/addresses.ts`.

## Run the frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build      # production build (Vercel: buildCommand in vercel.json)
```

Connect a MetaMask wallet **already funded on studionet** (fund it from the GenLayer
Studio → Accounts panel — never the testnet faucet).

## Tests

```bash
source ~/.genlayer/env.sh
gltest --network studionet          # or localnet for a fast loop
```

`tests/` mocks the LLM/web layer (`sim_installMocks`) before running non-deterministic
transactions, and covers the happy path, guard rails, and the challenge → re-triage flow.

## Verified live

`scripts/live_test.py` was run against studionet with two funded wallets: the provider
(wallet 2) registered a program, the claimant (wallet 3) filed a bonded claim, **real
on-chain AI consensus** produced a verdict + reason, and the claim was settled with a
native payout — end to end, no mocks.
