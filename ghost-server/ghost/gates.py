"""Authorization-paired commit gates (module 4), using the Platinum Authority Engine's Levels A, B and C.

Every state-changing action goes through Gate.commit(kind, ...). The gate resolves three things:
  identity        - the OS user (getuid), or the verified signer for envelopes;
  scope           - config/policy.json {"operate": [users], "observe": [users]}; with no file, dev mode;
  signed receipt  - Level B only: an Ed25519 grant bound to (action, job, principal), with a single-use nonce.

Level C is a missing capability, not a policy note:
  * EXECUTORS has no Level C kind, and register_executor() raises if asked to add one.
  * classify() runs on the declared kind and on the job text; anything it calls C is refused,
    written to the ledger, and escalated to Brandon (DB row plus state/escalations/ESC-<n>.json).
"""
from __future__ import annotations

import json
import os
import pwd
import re
from types import MappingProxyType
from typing import Any, Callable, Dict, Optional

from .registry import Registry, canonical
from .signing import SignatureDenied, Verifier

LEVEL_A = frozenset(("probe", "board", "provenance", "migrate", "codeact_run", "release_envelope", "recover",
                     "import_envelope"))
LEVEL_B = frozenset(("ghost_unblock", "ghost_requeue", "ghost_cancel", "ghost_complete", "ghost_forward",
                     "ghost_install"))
LEVEL_C_KINDS = frozenset(("spend", "purchase", "payment", "publish", "create_account", "move_money", "trade",
                           "live_trading", "delete_irreversible", "sign_document"))
# Superset of master-runtime LEVEL_C_MARKERS. Applied to the title + command, never to fence notes ("$0, no spend").
LEVEL_C_TEXT = re.compile(
    r"\b(spend(?:ing)?|purchas\w*|buy|make (?:a )?payment|send (?:a )?payment|payments? to|pay (?:for|the|an?|invoice|bill)|pay out|payout|invoice|charge (?:the )?card|refund|wire (?:money|funds)|"
    r"transfer (?:money|funds)|move money|money movement|publish\w*|post publicly|create (?:an? )?account|sign[ -]?up|"
    r"enroll\w*|trad(?:e|es|ing)|place (?:an? )?order|sell|delete permanently|irreversibl\w*|drop database|"
    r"sign the)\b", re.I)


# Brandon's register (war-room/POLICY-BASED-APPROVALS-2026-10-31.md). CODE CEILING per class: a signed charter can
# approve a class, but it can never stretch a class beyond these kinds, and it can never reach a fence (Level C).
REGISTER_CLASSES = ("training", "engineering", "ghost_operations", "ace_pipeline", "operational_communications",
                    "research")
CLASS_CEILING = {
    "ghost_operations": frozenset(("ghost_unblock", "ghost_requeue", "ghost_cancel", "ghost_install",
                                   "ghost_forward", "ghost_complete")),
}


def is_known(kind: str) -> bool:
    return kind in LEVEL_A or kind in LEVEL_B or kind in LEVEL_C_KINDS


class Refused(PermissionError):
    """The gate said no. Level C refusals carry escalation=<id>."""

    def __init__(self, msg: str, escalation: Optional[int] = None):
        super().__init__(msg)
        self.escalation = escalation


_EXECUTORS: Dict[str, Callable[..., Any]] = {}
EXECUTORS = MappingProxyType(_EXECUTORS)  # read-only view; the only writer is register_executor


def classify(kind: str, text: str = "") -> str:
    if kind in LEVEL_C_KINDS or LEVEL_C_TEXT.search(text or ""):
        return "C"
    if kind in LEVEL_B:
        return "B"
    if kind in LEVEL_A:
        return "A"
    return "C"  # unknown kinds fail closed to the strictest level


def register_executor(kind: str, fn: Callable[..., Any]) -> None:
    if kind in LEVEL_C_KINDS or LEVEL_C_TEXT.search(kind.replace("_", " ")) or classify(kind) == "C":
        raise Refused(f"no executor may exist for Level C (or unknown) action {kind!r}")
    if kind in _EXECUTORS:
        raise Refused(f"executor for {kind!r} already registered")
    _EXECUTORS[kind] = fn


def current_user() -> str:
    return pwd.getpwuid(os.geteuid()).pw_name


class Gate:
    def __init__(self, reg: Registry, *, policy_path: Optional[str] = None, verifier: Optional[Verifier] = None,
                 escalation_dir: Optional[str] = None, whoami: Callable[[], str] = current_user,
                 charter_path: Optional[str] = None, revoked_path: Optional[str] = None):
        self.reg, self.verifier, self.whoami = reg, verifier or Verifier(), whoami
        self.escalation_dir = escalation_dir
        self.charter = json.load(open(charter_path)) if charter_path and os.path.exists(charter_path) else None
        self.revoked = frozenset(json.load(open(revoked_path))) if revoked_path and os.path.exists(revoked_path) \
            else frozenset()
        self.policy = json.load(open(policy_path)) if policy_path and os.path.exists(policy_path) else None

    def scopes(self, user: str) -> frozenset:
        if self.policy is None:
            return frozenset(("operate", "observe"))  # dev mode: single operator, recorded as such
        return frozenset(s for s in ("operate", "observe") if user in self.policy.get(s, []))

    def policy_class_for(self, kind: str, now: float) -> Optional[Dict[str, Any]]:
        """The approved class covering `kind` under a valid, unrevoked charter, or None. Never covers a fence."""
        if self.charter is None or classify(kind) == "C":
            return None
        try:
            body = self.verifier.verify_charter(self.charter, now=now)
        except SignatureDenied:
            return None
        if body["charter_id"] in self.revoked:
            return None
        for cls, kinds in body["classes"].items():
            if cls in REGISTER_CLASSES and kind in CLASS_CEILING.get(cls, frozenset()) and \
                    (kinds == "all" or kind in kinds):
                return {"class": cls, "charter_id": body["charter_id"], "issuer": body["issuer"]}
        return None

    def _escalate(self, kind: str, job_id: str, reason: str, actor: str, *, policy_question: bool = False) -> int:
        esc = self.reg.escalate(job_id=job_id, action=kind, reason=reason, actor=actor)
        if self.escalation_dir:
            os.makedirs(self.escalation_dir, mode=0o700, exist_ok=True)
            path = os.path.join(self.escalation_dir, f"ESC-{esc:04d}.json")
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
                note = ("Novel class: asked ONCE as policy (register novel-class rule). Brandon's ruling enters the "
                        "register; then it is policy, not a recurring tap.") if policy_question else \
                    "GHOST cannot execute Level C actions; this is a one-touch decision packet for Brandon's tap."
                f.write(canonical({"esc_id": esc, "job_id": job_id, "action": kind, "reason": reason,
                                   "to": "brandon", "state": "AWAITING-BRANDON",
                                   "type": "policy_question" if policy_question else "fence", "note": note}))
        return esc

    def commit(self, kind: str, *, job_id: str = "", text: str = "", grant: Any = None, now: float,
               principal: Optional[str] = None, **args: Any) -> Any:
        user = principal or self.whoami()
        actor = f"os:{user}"
        level = classify(kind, text)
        if not is_known(kind) and not LEVEL_C_TEXT.search(text or "") and not LEVEL_C_TEXT.search(kind.replace("_", " ")):
            reason = f"novel action class {kind!r}: no register class covers it; raised once as a policy question"
            esc = self._escalate(kind, job_id, reason, actor, policy_question=True)
            self.reg.ledger("gate_refused", actor, {"kind": kind, "level": "novel", "escalation": esc}, job_id)
            raise Refused(reason, escalation=esc)
        if level == "C":
            reason = f"Level C action {kind!r} is structurally unavailable to GHOST; escalated to Brandon"
            esc = self._escalate(kind, job_id, reason, actor)
            self.reg.ledger("gate_refused", actor, {"kind": kind, "level": "C", "escalation": esc}, job_id)
            raise Refused(reason, escalation=esc)
        if "operate" not in self.scopes(user):
            self.reg.ledger("gate_refused", actor, {"kind": kind, "level": level, "why": "no operate scope"}, job_id)
            raise Refused(f"{actor} lacks the operate scope")
        policy = None
        if level == "B" and grant is None:
            policy = self.policy_class_for(kind, now)
            if policy is None:
                why = "no per-item receipt and no valid policy charter covers this class"
                self.reg.ledger("gate_refused", actor, {"kind": kind, "level": "B", "why": why}, job_id)
                raise Refused(f"Level B {kind!r}: {why}")
        elif level == "B":
            try:
                body = self.verifier.verify_grant(grant, action=kind, subject=job_id, principal=actor, now=now)
            except SignatureDenied as exc:
                self.reg.ledger("gate_refused", actor, {"kind": kind, "level": "B", "why": str(exc)}, job_id)
                raise Refused(f"Level B {kind!r} needs a valid signed receipt: {exc}") from exc
            if not self.reg.consume_nonce(body["nonce"]):
                self.reg.ledger("gate_refused", actor, {"kind": kind, "level": "B", "why": "replayed nonce"}, job_id)
                raise Refused("signed receipt already used (replay)")
        fn = EXECUTORS.get(kind)
        if fn is None:  # defence in depth: an unregistered kind has no code path at all
            self.reg.ledger("gate_refused", actor, {"kind": kind, "level": level, "why": "no executor"}, job_id)
            raise Refused(f"no executor for {kind!r}")
        self.reg.ledger("gate_allowed", actor, {"kind": kind, "level": level,
                                                "signed_by": (grant or {}).get("payload", {}).get("issuer", "")
                                                if level == "B" and grant else "",
                                                "policy_class": policy["class"] if policy else "",
                                                "charter_id": policy["charter_id"] if policy else ""}, job_id)
        return fn(self.reg, job_id=job_id, actor=actor, now=now, **args)


# ---- Level B executors: thin, auditable, all go through Registry's single-ID write path ----------------------------
def _unblock(reg: Registry, *, job_id: str, actor: str, now: float, **_: Any):
    return reg.operator_transition(job_id, "QUEUED", actor=actor, transform="unblock_signed")


def _requeue(reg: Registry, *, job_id: str, actor: str, now: float, **_: Any):
    return reg.operator_transition(job_id, "QUEUED", actor=actor, transform="requeue_signed")


def _cancel(reg: Registry, *, job_id: str, actor: str, now: float, **_: Any):
    return reg.operator_transition(job_id, "BLOCKED", actor=actor, transform="cancel_signed")


for _k, _f in (("ghost_unblock", _unblock), ("ghost_requeue", _requeue), ("ghost_cancel", _cancel)):
    register_executor(_k, _f)
