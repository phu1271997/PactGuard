# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *

from dataclasses import dataclass
import json


# ---------------------------------------------------------------------------
# Runtime helpers
# ---------------------------------------------------------------------------
def _run_nondet(leader_fn, validator_fn):
    """Prefer the sandboxed ``run_nondet``; fall back only if the Studio build
    on this network does not expose it (see GEN_RULES Rule #7)."""
    fn = (
        getattr(gl.vm, "run_nondet_default", None)
        or getattr(gl.vm, "run_nondet", None)
        or gl.vm.run_nondet_unsafe
    )
    return fn(leader_fn, validator_fn)


def _addr_str(addr: Address) -> str:
    try:
        return addr.as_hex
    except Exception:
        return str(addr)


def _now_epoch() -> bigint:
    try:
        return bigint(int(gl.vm.get_timestamp().timestamp()))
    except Exception:
        return bigint(0)


# Credit tiers: severity -> % of the provider bond paid as a service credit,
# expressed in basis points of 10000 (2500 = 25%).
SEVERITY_CREDIT_BPS = {
    "MINOR": 1000,     # 10%
    "MAJOR": 2500,     # 25%
    "CRITICAL": 5000,  # 50%
}

MIN_PROVIDER_BOND = 500000000000000000    # 0.5 GEN
MIN_CLAIM_BOND = 100000000000000000       # 0.1 GEN
CHALLENGE_WINDOW_SECS = 120               # dispute window after triage
CONFIDENCE_FLOOR = 60                     # below this the verdict is not auto-final


# ---------------------------------------------------------------------------
# Storage structs
# ---------------------------------------------------------------------------
@allow_storage
@dataclass
class Program:
    provider: str
    service_name: str
    sla_terms_url: str        # pinned public SLA / terms page read on-chain
    uptime_target_bp: u16     # promised uptime, basis points of 10000 (9990 = 99.90%)
    bond: bigint              # provider collateral vault (pays out credits)
    active: bool


@allow_storage
@dataclass
class Claim:
    claimant: str
    program_id: str
    incident_window: str      # e.g. "2026-09-01T00:00Z .. 2026-09-03T00:00Z"
    description: str
    evidence_urls: DynArray[str]
    claim_bond: bigint
    state: str                # OPEN | UPHELD | REJECTED | CHALLENGED | SETTLED
    verdict: str              # "" | UPHELD | REJECTED
    severity: str             # "" | NONE | MINOR | MAJOR | CRITICAL
    credit_bp: u16            # resolved credit (bp of provider bond)
    confidence: u8
    reason: str
    challenge_deadline: bigint
    challenger: str
    challenge_bond: bigint
    rebuttal_url: str
    challenged_once: bool
    payout_done: bool


class Contract(gl.Contract):
    admin: Address
    programs: TreeMap[str, Program]
    claims: TreeMap[str, Claim]
    next_program_id: bigint
    next_claim_id: bigint

    def __init__(self):
        self.admin = gl.message.sender_address
        self.next_program_id = bigint(1)
        self.next_claim_id = bigint(1)

    # -------------------------------------------------------------------
    # Provider onboarding
    # -------------------------------------------------------------------
    @gl.public.write.payable
    def register_program(
        self,
        service_name: str,
        sla_terms_url: str,
        uptime_target_bp: int,
    ) -> str:
        if gl.message.value < u256(MIN_PROVIDER_BOND):
            raise gl.vm.UserError("Provider bond below minimum (0.5 GEN)")
        if not service_name or len(service_name.strip()) == 0:
            raise gl.vm.UserError("Service name cannot be empty")
        if len(service_name) > 120:
            raise gl.vm.UserError("Service name too long")
        if not sla_terms_url.startswith("https://"):
            raise gl.vm.UserError("SLA terms URL must be a public https:// link")
        if uptime_target_bp <= 0 or uptime_target_bp > 10000:
            raise gl.vm.UserError("uptime_target_bp must be in 1..10000")

        pid = int(self.next_program_id)
        self.next_program_id = bigint(pid + 1)
        pid_str = str(pid)

        self.programs[pid_str] = Program(
            provider=_addr_str(gl.message.sender_address),
            service_name=service_name.strip(),
            sla_terms_url=sla_terms_url.strip(),
            uptime_target_bp=u16(uptime_target_bp),
            bond=bigint(int(gl.message.value)),
            active=True,
        )
        return pid_str

    @gl.public.write.payable
    def top_up_bond(self, program_id: str) -> None:
        if program_id not in self.programs:
            raise gl.vm.UserError("Program not found")
        p = self.programs[program_id]
        if _addr_str(gl.message.sender_address).lower() != p.provider.lower():
            raise gl.vm.UserError("Only the provider can top up the bond")
        if gl.message.value <= u256(0):
            raise gl.vm.UserError("Top-up must be positive")
        p.bond = p.bond + bigint(int(gl.message.value))

    # -------------------------------------------------------------------
    # Claim lifecycle
    # -------------------------------------------------------------------
    @gl.public.write.payable
    def file_claim(
        self,
        program_id: str,
        incident_window: str,
        description: str,
        evidence_urls: DynArray[str],
    ) -> str:
        if program_id not in self.programs:
            raise gl.vm.UserError("Program not found")
        p = self.programs[program_id]
        if not p.active:
            raise gl.vm.UserError("Program is not active")
        if gl.message.value < u256(MIN_CLAIM_BOND):
            raise gl.vm.UserError("Claim bond below minimum (0.1 GEN)")
        if len(incident_window.strip()) == 0:
            raise gl.vm.UserError("Incident window cannot be empty")
        if len(description.strip()) == 0:
            raise gl.vm.UserError("Description cannot be empty")
        if len(description) > 800:
            raise gl.vm.UserError("Description exceeds 800 characters")
        if len(evidence_urls) == 0:
            raise gl.vm.UserError("At least one evidence URL is required")
        if len(evidence_urls) > 3:
            raise gl.vm.UserError("Maximum 3 evidence URLs allowed")

        cid = int(self.next_claim_id)
        self.next_claim_id = bigint(cid + 1)
        cid_str = str(cid)

        self.claims[cid_str] = Claim(
            claimant=_addr_str(gl.message.sender_address),
            program_id=program_id,
            incident_window=incident_window.strip(),
            description=description.strip(),
            evidence_urls=evidence_urls,
            claim_bond=bigint(int(gl.message.value)),
            state="OPEN",
            verdict="",
            severity="",
            credit_bp=u16(0),
            confidence=u8(0),
            reason="",
            challenge_deadline=bigint(0),
            challenger="",
            challenge_bond=bigint(0),
            rebuttal_url="",
            challenged_once=False,
            payout_done=False,
        )
        return cid_str

    @gl.public.write
    def triage(self, claim_id: str) -> None:
        """Run the AI jury over the pinned SLA terms + the claimant's evidence."""
        if claim_id not in self.claims:
            raise gl.vm.UserError("Claim not found")
        c = self.claims[claim_id]
        if c.state != "OPEN":
            raise gl.vm.UserError("Claim is not awaiting triage")
        self._adjudicate(claim_id, is_retriage=False)

    @gl.public.write.payable
    def challenge(self, claim_id: str, rebuttal_url: str, note: str) -> None:
        """The losing side posts a bonded rebuttal before the deadline.

        UPHELD -> the provider challenges. REJECTED -> the claimant challenges.
        The challenge bond must at least match the claim bond.
        """
        if claim_id not in self.claims:
            raise gl.vm.UserError("Claim not found")
        c = self.claims[claim_id]
        if c.state not in ["UPHELD", "REJECTED"]:
            raise gl.vm.UserError("Only a triaged claim can be challenged")
        if c.challenged_once:
            raise gl.vm.UserError("Claim has already been challenged once")
        if _now_epoch() > c.challenge_deadline and int(c.challenge_deadline) != 0:
            raise gl.vm.UserError("Challenge window has closed")
        if gl.message.value < u256(int(c.claim_bond)):
            raise gl.vm.UserError("Challenge bond must be >= the claim bond")

        p = self.programs[c.program_id]
        sender = _addr_str(gl.message.sender_address)
        if c.verdict == "UPHELD":
            if sender.lower() != p.provider.lower():
                raise gl.vm.UserError("Only the provider can challenge an upheld claim")
        else:  # REJECTED
            if sender.lower() != c.claimant.lower():
                raise gl.vm.UserError("Only the claimant can challenge a rejected claim")

        if rebuttal_url and not rebuttal_url.startswith("https://"):
            raise gl.vm.UserError("Rebuttal URL must be https://")

        # Store the rebuttal separately so the re-triage can read it (avoids
        # reassigning a stored DynArray field).
        c.rebuttal_url = rebuttal_url.strip() if rebuttal_url else ""
        c.challenger = sender
        c.challenge_bond = bigint(int(gl.message.value))
        c.challenged_once = True
        c.reason = f"{c.reason} | CHALLENGE by {sender}: {note[:300]}"
        c.state = "CHALLENGED"

    @gl.public.write
    def retriage(self, claim_id: str) -> None:
        """Re-run the jury on a challenged claim. The result is final."""
        if claim_id not in self.claims:
            raise gl.vm.UserError("Claim not found")
        c = self.claims[claim_id]
        if c.state != "CHALLENGED":
            raise gl.vm.UserError("Claim is not under challenge")
        self._adjudicate(claim_id, is_retriage=True)

    def _adjudicate(self, claim_id: str, is_retriage: bool) -> None:
        c = self.claims[claim_id]
        p = self.programs[c.program_id]

        # --- snapshot storage BEFORE the nondet block (no storage reads inside) ---
        terms_url = p.sla_terms_url
        uptime_target_bp = int(p.uptime_target_bp)
        service_name = p.service_name
        incident_window = c.incident_window
        description = c.description
        evidence = list(c.evidence_urls)
        rebuttal_url = c.rebuttal_url

        def leader_fn():
            sources = []
            # 1) the pinned SLA terms
            sources.append(_fetch(terms_url, "SLA_TERMS"))
            # 2) up to 3 evidence pages (status page, incident history, monitors)
            for url in evidence[:3]:
                sources.append(_fetch(url, "EVIDENCE"))
            # 3) the provider's rebuttal page, if this is a re-triage
            if rebuttal_url:
                sources.append(_fetch(rebuttal_url, "REBUTTAL"))

            target_pct = uptime_target_bp / 100.0
            prompt = f"""You are a decentralized AI adjudicator on GenLayer settling an SLA breach claim.

SERVICE: {service_name}
PROMISED UPTIME: {target_pct:.2f}% (basis points: {uptime_target_bp}/10000)
CLAIMED INCIDENT WINDOW: {incident_window}
CLAIMANT DESCRIPTION: {description}

SOURCES FETCHED LIVE ON-CHAIN (the pinned SLA terms first, then the evidence pages):
{json.dumps(sources, indent=2)[:12000]}

Decide, reading the SLA terms carefully (they may exclude scheduled maintenance,
count monthly not per-incident, measure at the edge, require a status-page
acknowledgement, etc.):
1. Did a real outage occur inside the claimed window, per the evidence pages?
2. Under THIS service's SLA terms, does that outage constitute a breach?
3. If breached, how severe: MINOR (brief/partial), MAJOR (sustained/core), CRITICAL (prolonged full outage or data-affecting)?

RESPOND WITH ONLY VALID JSON:
{{
  "verdict": "UPHELD" | "REJECTED",
  "severity": "NONE" | "MINOR" | "MAJOR" | "CRITICAL",
  "confidence": 0-100,
  "reason": "2-4 sentences citing the SLA clause and the specific evidence"
}}
A REJECTED verdict must use severity "NONE"."""
            return gl.nondet.exec_prompt(prompt, response_format="json")

        def validator_fn(leader_res) -> bool:
            # Compare MEANING (verdict + severity tier + settle threshold), never
            # the free-text `reason`. Two validators that disagree on the verdict
            # or the credit tier must NOT reach consensus.
            if not isinstance(leader_res, gl.vm.Return):
                return False
            leader = leader_res.calldata
            if not isinstance(leader, dict):
                return False
            if "verdict" not in leader or "severity" not in leader or "confidence" not in leader:
                return False
            mine = leader_fn()
            if not isinstance(mine, dict):
                return False
            if "verdict" not in mine or "severity" not in mine or "confidence" not in mine:
                return False
            if str(mine["verdict"]).upper() != str(leader["verdict"]).upper():
                return False
            if str(mine["severity"]).upper() != str(leader["severity"]).upper():
                return False
            mc = int(mine["confidence"])
            lc = int(leader["confidence"])
            # agree on whether the verdict clears the auto-final confidence floor
            if (mc >= CONFIDENCE_FLOOR) != (lc >= CONFIDENCE_FLOOR):
                return False
            if abs(mc - lc) > 15:
                return False
            return True

        result = _run_nondet(leader_fn, validator_fn)

        verdict = str(result.get("verdict", "REJECTED")).upper()
        if verdict not in ["UPHELD", "REJECTED"]:
            verdict = "REJECTED"
        severity = str(result.get("severity", "NONE")).upper()
        if severity not in ["NONE", "MINOR", "MAJOR", "CRITICAL"]:
            severity = "NONE"
        confidence = int(result.get("confidence", 70))
        confidence = max(0, min(100, confidence))
        reason = str(result.get("reason", ""))

        c.verdict = verdict
        c.severity = severity
        c.confidence = u8(confidence)
        c.reason = (c.reason + " | " if is_retriage else "") + reason

        if verdict == "UPHELD":
            bp = SEVERITY_CREDIT_BPS.get(severity, 1000)
            c.credit_bp = u16(bp)
            c.state = "UPHELD"
        else:
            c.credit_bp = u16(0)
            c.state = "REJECTED"

        if is_retriage:
            # A re-triaged verdict is final: settle immediately.
            c.challenge_deadline = bigint(0)
            self._settle(claim_id)
        else:
            # Open a challenge window. If the runtime clock is unavailable
            # (studionet's get_timestamp can return 0), fall back to deadline 0,
            # meaning "no timed lock — the window stays open until someone settles".
            now = _now_epoch()
            if int(now) > 0:
                window = CHALLENGE_WINDOW_SECS * (2 if confidence < CONFIDENCE_FLOOR else 1)
                c.challenge_deadline = now + bigint(window)
            else:
                c.challenge_deadline = bigint(0)

    @gl.public.write
    def settle(self, claim_id: str) -> None:
        """After the challenge window closes (and no open challenge), pay out."""
        if claim_id not in self.claims:
            raise gl.vm.UserError("Claim not found")
        c = self.claims[claim_id]
        if c.state == "CHALLENGED":
            raise gl.vm.UserError("Claim is under challenge; call retriage first")
        if c.state not in ["UPHELD", "REJECTED"]:
            raise gl.vm.UserError("Claim is not in a settleable state")
        if c.payout_done:
            raise gl.vm.UserError("Claim already settled")
        if int(c.challenge_deadline) != 0 and _now_epoch() < c.challenge_deadline:
            raise gl.vm.UserError("Challenge window is still open")
        self._settle(claim_id)

    def _settle(self, claim_id: str) -> None:
        c = self.claims[claim_id]
        p = self.programs[c.program_id]

        claimant = c.claimant
        provider = p.provider
        claim_bond = int(c.claim_bond)
        challenge_bond = int(c.challenge_bond)
        challenger = c.challenger

        if c.verdict == "UPHELD":
            # credit = provider bond * credit_bp / 10000, capped at the bond
            credit = (int(p.bond) * int(c.credit_bp)) // 10000
            if credit > int(p.bond):
                credit = int(p.bond)
            p.bond = bigint(int(p.bond) - credit)
            # claimant gets: credit + their own bond back
            payout_claimant = credit + claim_bond
            # if the provider challenged and lost, their challenge bond also goes to the claimant
            if challenger and challenger.lower() == provider.lower():
                payout_claimant += challenge_bond
            _pay(claimant, payout_claimant)
        else:  # REJECTED
            # claimant forfeits their bond to the provider (deters spurious claims)
            payout_provider = claim_bond
            # if the claimant challenged and lost, their challenge bond goes to the provider too
            if challenger and challenger.lower() == claimant.lower():
                payout_provider += challenge_bond
            _pay(provider, payout_provider)

        c.payout_done = True
        c.state = "SETTLED"

    # -------------------------------------------------------------------
    # Admin demo seeding (does not run the LLM; pre-baked verdicts)
    # -------------------------------------------------------------------
    @gl.public.write.payable
    def admin_seed_program(
        self,
        provider: str,
        service_name: str,
        sla_terms_url: str,
        uptime_target_bp: int,
        bond: int,
    ) -> str:
        if gl.message.sender_address != self.admin:
            raise gl.vm.UserError("Only admin can seed")
        pid = int(self.next_program_id)
        self.next_program_id = bigint(pid + 1)
        pid_str = str(pid)
        self.programs[pid_str] = Program(
            provider=provider,
            service_name=service_name,
            sla_terms_url=sla_terms_url,
            uptime_target_bp=u16(uptime_target_bp),
            bond=bigint(bond),
            active=True,
        )
        return pid_str

    @gl.public.write
    def admin_seed_claim(
        self,
        program_id: str,
        claimant: str,
        incident_window: str,
        description: str,
        evidence_urls: DynArray[str],
        claim_bond: int,
        state: str,
        verdict: str,
        severity: str,
        confidence: int,
        reason: str,
    ) -> str:
        if gl.message.sender_address != self.admin:
            raise gl.vm.UserError("Only admin can seed")
        cid = int(self.next_claim_id)
        self.next_claim_id = bigint(cid + 1)
        cid_str = str(cid)
        bp = SEVERITY_CREDIT_BPS.get(severity.upper(), 0) if verdict.upper() == "UPHELD" else 0
        self.claims[cid_str] = Claim(
            claimant=claimant,
            program_id=program_id,
            incident_window=incident_window,
            description=description,
            evidence_urls=evidence_urls,
            claim_bond=bigint(claim_bond),
            state=state,
            verdict=verdict.upper() if verdict else "",
            severity=severity.upper() if severity else "",
            credit_bp=u16(bp),
            confidence=u8(max(0, min(100, confidence))),
            reason=reason,
            challenge_deadline=bigint(0),
            challenger="",
            challenge_bond=bigint(0),
            rebuttal_url="",
            challenged_once=False,
            payout_done=(state == "SETTLED"),
        )
        return cid_str

    # -------------------------------------------------------------------
    # Views
    # -------------------------------------------------------------------
    @gl.public.view
    def get_program(self, program_id: str) -> str:
        if program_id not in self.programs:
            raise gl.vm.UserError("Program not found")
        p = self.programs[program_id]
        return json.dumps(
            {
                "program_id": program_id,
                "provider": p.provider,
                "service_name": p.service_name,
                "sla_terms_url": p.sla_terms_url,
                "uptime_target_bp": int(p.uptime_target_bp),
                "bond": str(p.bond),
                "active": p.active,
            }
        )

    @gl.public.view
    def get_claim(self, claim_id: str) -> str:
        if claim_id not in self.claims:
            raise gl.vm.UserError("Claim not found")
        c = self.claims[claim_id]
        return json.dumps(self._claim_json(claim_id, c))

    def _claim_json(self, claim_id: str, c: Claim) -> dict:
        return {
            "claim_id": claim_id,
            "claimant": c.claimant,
            "program_id": c.program_id,
            "incident_window": c.incident_window,
            "description": c.description,
            "evidence_urls": list(c.evidence_urls),
            "claim_bond": str(c.claim_bond),
            "state": c.state,
            "verdict": c.verdict,
            "severity": c.severity,
            "credit_bp": int(c.credit_bp),
            "confidence": int(c.confidence),
            "reason": c.reason,
            "challenge_deadline": int(c.challenge_deadline),
            "challenger": c.challenger,
            "challenge_bond": str(c.challenge_bond),
            "rebuttal_url": c.rebuttal_url,
            "challenged_once": c.challenged_once,
            "payout_done": c.payout_done,
        }

    @gl.public.view
    def get_program_count(self) -> u256:
        return u256(int(self.next_program_id) - 1)

    @gl.public.view
    def get_claim_count(self) -> u256:
        return u256(int(self.next_claim_id) - 1)

    @gl.public.view
    def list_programs(self, offset: int, limit: int) -> str:
        total = int(self.next_program_id) - 1
        out = []
        start = max(1, offset + 1)
        end = min(total + 1, start + limit)
        for i in range(start, end):
            k = str(i)
            if k in self.programs:
                p = self.programs[k]
                out.append(
                    {
                        "program_id": k,
                        "provider": p.provider,
                        "service_name": p.service_name,
                        "sla_terms_url": p.sla_terms_url,
                        "uptime_target_bp": int(p.uptime_target_bp),
                        "bond": str(p.bond),
                        "active": p.active,
                    }
                )
        return json.dumps(out)

    @gl.public.view
    def list_claims(self, state_filter: str, offset: int, limit: int) -> str:
        total = int(self.next_claim_id) - 1
        out = []
        f = state_filter.upper().strip()
        start = max(1, offset + 1)
        end = min(total + 1, start + limit)
        for i in range(start, end):
            k = str(i)
            if k in self.claims:
                c = self.claims[k]
                if not f or f == "ALL" or c.state == f:
                    out.append(self._claim_json(k, c))
        return json.dumps(out)


# ---------------------------------------------------------------------------
# Module-level helpers used only inside methods (kept out of the class so the
# nondet closure can call them without a `self` storage reference).
# ---------------------------------------------------------------------------
def _fetch(url: str, kind: str) -> dict:
    try:
        res = gl.nondet.web.get(url)
        body = res.body.decode("utf-8", errors="replace") if hasattr(res, "body") else str(res)
        return {"url": url, "kind": kind, "content": body[:3500]}
    except Exception:
        try:
            body = gl.nondet.web.render(url, mode="text")
            return {"url": url, "kind": kind, "content": body[:3500]}
        except Exception as e:
            return {"url": url, "kind": kind, "error": str(e)[:200]}


def _pay(recipient: str, amount: int) -> None:
    if amount <= 0 or not recipient:
        return
    try:
        gl.get_contract_at(Address(recipient)).emit_transfer(value=u256(int(amount)))
    except Exception:
        pass
