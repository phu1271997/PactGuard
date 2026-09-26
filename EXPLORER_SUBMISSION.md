# GENLAYER PROJECT EXPLORER — SUBMISSION DRAFT
**Project:** PactGuard · **Prepared:** 2026-09-26 · **Status: READY (Preview)**

> Paste each field below into the matching Portal Explorer form field. English, within the verified character caps. Logo is the only TO-BE-PROVIDED item.

---

## Section 01 — IDENTITY

### Project name
```
PactGuard
```

### Primary category
```
Dispute Resolution
```
Why: the core is an adjudication with money at stake and a challenge/re-triage path — exactly GenLayer's "adjudication layer" positioning. Not `AI & Agents` (too generic, every catalog entry is AI-powered — it would sink the listing). There is no `Escrow` primary option, so escrow is captured as a tag below.

### Category tag 1 — `Escrow Claims`
Maps to real functions: `register_program` (payable provider bond vault), `file_claim` (payable claim bond), `settle` → `_settle` releases a bond-funded service credit to the winner on a conditional verdict. Two-sided escrow with conditional disbursement. This is what every user meets first.

### Category tag 2 — `Evidence Assessment`
Maps to `triage`/`retriage` → `_adjudicate`: the nondet block fetches the pinned SLA terms URL + the claimant's evidence URLs via `gl.nondet.web.get/render` and weighs them in `gl.nondet.exec_prompt` to reach the verdict.

**Rejected tags (reviewer may check):** `Appeal Review` is defensible (challenge → re-triage is a second ruling) but it is an optional secondary branch, so it is not one of the two primary tags. `License Claims` / `Moderation Appeals` / `Jury Selection` — not implemented (validator selection is GenLayer's, not the app's).

### Logo — TO BE PROVIDED
Spec: PNG/JPEG/WebP, 128–2048 px, max 2 MB, opaque background.
Concept: a single mark — a shield silhouette with an uptime/heartbeat line clipped inside it, on a dark card, teal/emerald accent (`#10b981`) to match the app. (I can generate this on request via the qlmanage recipe.)

---

## Section 02 — PROJECT SUMMARY

### One-liner  (172 / cap 180)
```
File a bonded claim when a service breaks its uptime promise; a decentralized AI jury reads the SLA terms and status pages on-chain and rules whether you are owed a credit.
```

### Description  (971 / cap 1000)
```
PactGuard turns SLA enforcement into an autonomous escrow. A provider registers a service, deposits a GEN bond, and pins its public SLA terms URL. A customer files a bonded breach claim with links to status or incident pages. GenLayer validators fetch the pinned terms and the evidence pages on-chain, and an LLM rules UPHELD or REJECTED with a severity tier — MINOR, MAJOR or CRITICAL — mapping to a 10%, 25% or 50% service credit paid from the provider bond.

Built for SaaS, API and infrastructure providers and their customers, who today argue over downtime by email with no neutral referee and no enforceable payout.

No oracle or admin decides. Reading messy status pages and interpreting SLA language — "excludes scheduled maintenance", "measured monthly" — is a subjective judgment Solidity cannot make. Either side can post a bonded challenge that forces an independent re-triage, and the validator consensus, not our server, produces the verdict and its reason.
```

---

## How to try it

**Prerequisites:** MetaMask. Browsing existing claims needs no wallet. To file/triage you need a GEN balance on GenLayer studionet — fund your address from the Studio **Accounts** panel (studio.genlayer.com → Accounts → transfer from a pre-funded account). Do NOT use a testnet faucet. Budget ~1 GEN total (0.5 GEN provider bond OR 0.1 GEN claim bond + gas).

**Step 1 — Browse seeded claims.**
Open https://pactguard-three.vercel.app and go to "Breach Claims". You'll see pre-seeded claims in UPHELD, REJECTED and SETTLED states, each showing the AI verdict, severity, credit %, confidence and the written reason. No wallet needed.

**Step 2 — Connect wallet + switch network.**
Click "Connect Wallet". Approve MetaMask; the app auto-switches/adds GenLayer studionet (chain 61999). Confirm your GEN balance shows top-right.

**Step 3 — File a bonded breach claim.**
"File Claim" → pick a program, enter the incident window, a description, and 1–3 evidence URLs (a real status/incident page). Set the claim bond (≥0.1 GEN) and submit. Sign in MetaMask.

**Step 4 — Trigger AI triage.**
Open your claim and click "Triage". A consensus-waiting overlay appears (nondet txs are slower — validators fetch the web + run the LLM). When it finalizes, the claim shows verdict + severity + credit % + confidence + reason.

**Step 5 (optional) — Challenge or settle.**
The losing side can post a bonded "Challenge" → "Retriage" for an independent second ruling. Otherwise click "Settle" to disburse.

**Expected end state:** your claim reaches UPHELD or REJECTED with an on-chain AI reason; SETTLED after payout.

**If something goes wrong:**
- MetaMask "from" / wrong-network error → re-run Step 2 (must be on studionet).
- Write rejected / insufficient funds → wallet not funded on studionet; see Prerequisites.
- Triage seems stuck → nondet consensus takes longer than a normal tx; wait, don't resend.

---

## Expected verification outcome  (492 / cap 500)
```
Reading requires no wallet: seeded claims already show verdicts UPHELD, REJECTED and SETTLED, each with an AI severity, credit percentage, confidence score and a written reason produced by validator consensus — not by our backend. Trigger Triage on an OPEN claim and, after consensus, it gains an on-chain verdict + reason. The studionet explorer page for the contract lists the transaction with GENVM RESULT SUCCESS and CONSENSUS RESULT Accepted, proving the LLM+web decision ran on-chain.
```

---

## Contract link
```
https://explorer-studio.genlayer.com/address/0xb2cA43d78aaaE0B8888767f2E143321BBced2fEe
```
- **Address:** `0xb2cA43d78aaaE0B8888767f2E143321BBced2fEe`
- **Network:** studionet  → **Status: Preview**
- **Deploy tx:** `0x6694355bd283cde18543488d747ee49a2f565fda0f1d048f235cf33b42610060` (deployer `0x8b563A8c9eeF530300e92E26457D1AB001daEcC7`)
- Verified live: `gen_getContractSchema` returns the full method list; real multi-wallet lifecycle (register → file → triage → settle) executed with GENVM RESULT SUCCESS.
- Alt explorer (also works): https://genlayer-explorer.vercel.app/address/0xb2cA43d78aaaE0B8888767f2E143321BBced2fEe

## Website
```
https://pactguard-three.vercel.app
```

## GitHub
```
https://github.com/phu1271997/PactGuard
```

## Community links (optional)
Leave blank.

---

### Pre-submission checklist
- [x] Live URL returns 200, no login wall (verified: bundle carries the final contract address + studionet RPC)
- [x] Contract schema live on studionet; real tx with SUCCESS/Accepted
- [x] Status marked **Preview** (studionet), not Live
- [x] Every tag maps to a named contract function
- [x] One-liner 172 ≤ 180 · Description 971 ≤ 1000 · Expected outcome 490 ≤ 500
- [ ] Logo uploaded (TO BE PROVIDED)
- [ ] (recommended) Re-seed if Studio storage was reset before review — `scripts/seed_demo_data.py`
```
```
