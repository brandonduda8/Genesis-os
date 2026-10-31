"""Legacy migration (P1 reader / P5 migration) and commit gates (module 4), incl. the Level C refusal test."""
import glob
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from ghost import gates, legacy, signing  # noqa: E402
from ghost.registry import Registry  # noqa: E402

QUEUE = os.path.join(os.path.dirname(HERE), "ghost", "queue")
MAPPING = os.path.join(HERE, "config", "legacy_requires.json")


def tree_hash(d):
    return {os.path.basename(p): hashlib.sha256(open(p, "rb").read()).hexdigest() for p in sorted(glob.glob(d + "/*"))}


@unittest.skipUnless(os.path.isdir(QUEUE), "needs the sibling genesis-os/ghost/queue (designed layout; Zane review D2)")
class Migration(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.reg = Registry(os.path.join(self.d, "g.db"))

    def test_migrates_every_legacy_job_read_only_and_idempotently(self):
        before = tree_hash(QUEUE)
        rep = legacy.migrate(self.reg, QUEUE, MAPPING, actor="os:test", repo_root=os.path.dirname(HERE))
        self.assertEqual(tree_hash(QUEUE), before, "legacy queue files must never be modified")
        n_files = len(glob.glob(QUEUE + "/*.json")) + len(glob.glob(QUEUE + "/Q-*.md"))
        self.assertEqual(len(rep["created"]), n_files)
        self.assertEqual(rep["level_c"], [])
        blocked = dict(b.split(":", 1) for b in rep["blocked"])
        self.assertEqual(blocked.get("GHOST-Q-008"), "human:brandon-relay")  # Brandon's hands, never dispatched
        again = legacy.migrate(self.reg, QUEUE, MAPPING, actor="os:test", repo_root=os.path.dirname(HERE))
        self.assertEqual((len(again["created"]), len(again["unchanged"])), (0, n_files))

    def test_lineage_source_pins_the_legacy_file_hash(self):
        legacy.migrate(self.reg, QUEUE, MAPPING, actor="os:test", repo_root=os.path.dirname(HERE))
        path = glob.glob(QUEUE + "/GHOST-Q-004-*.json")[0]
        sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
        src = self.reg.provenance("GHOST-Q-004")["lineage"][0]["source"]
        self.assertIn(f"@sha256:{sha}", src)
        self.assertTrue(src.startswith("ghost/queue/GHOST-Q-004-"))

    def test_changed_legacy_file_is_noted_not_overwritten(self):
        q = os.path.join(self.d, "queue")
        shutil.copytree(QUEUE, q)
        legacy.migrate(self.reg, q, MAPPING, actor="os:test")
        p = glob.glob(q + "/GHOST-Q-002-*.json")[0]
        d = json.load(open(p))
        d["title"] = "edited by hand"
        json.dump(d, open(p, "w"))
        rep = legacy.migrate(self.reg, q, MAPPING, actor="os:test")
        self.assertEqual(rep["changed"], ["GHOST-Q-002"])
        self.assertNotEqual(self.reg.get("GHOST-Q-002")["title"], "edited by hand")
        self.assertEqual(self.reg.provenance("GHOST-Q-002")["lineage"][-1]["transform"], "legacy_file_changed")

    def test_duplicate_ids_across_files_are_refused_not_merged(self):
        q = os.path.join(self.d, "dup")
        os.makedirs(q)
        for name, title in (("GHOST-Q-050-a.json", "first"), ("GHOST-Q-050-b.json", "second")):
            json.dump({"id": "GHOST-Q-050", "title": title, "requires_path": "x", "status": "QUEUED"},
                      open(os.path.join(q, name), "w"))
        rep = legacy.migrate(self.reg, q, MAPPING, actor="os:test")
        self.assertEqual(rep["created"], ["GHOST-Q-050"])
        self.assertEqual(len(rep["duplicate_ids"]), 1)
        self.assertEqual(self.reg.get("GHOST-Q-050")["title"], "first")

    def test_real_queue_has_one_file_per_id_and_no_level_c(self):
        rep = legacy.migrate(self.reg, QUEUE, MAPPING, actor="os:test", repo_root=os.path.dirname(HERE))
        self.assertEqual(rep["duplicate_ids"], [])
        self.assertEqual(rep["level_c"], [], "a legitimate queue job was classified Level C (Zane review D1)")

    def test_prose_statuses_are_normalised_and_unverified_states_stay_blocked(self):
        self.assertEqual(legacy.status_token("QUEUED — work order written 2026-10-31"), "QUEUED")
        self.assertEqual(legacy.status_token("DEAD-LETTER (attempts exhausted)"), "DEAD-LETTER")
        self.assertEqual(legacy.status_token("p0 decided"), "")
        q = os.path.join(self.d, "q3")
        os.makedirs(q)
        for n, st in ((60, "QUEUED — written today; delivered for relay"), (61, "DISCHARGED 2026-10-31 (receipt X)"),
                      (62, "P0 DECIDED (Shape A) + P1 BUILT-UNVERIFIED")):
            json.dump({"id": f"GHOST-Q-0{n}", "title": "t", "requires_path": "x", "status": st},
                      open(os.path.join(q, f"GHOST-Q-0{n}-x.json"), "w"))
        legacy.migrate(self.reg, q, MAPPING, actor="os:test")
        self.assertEqual(self.reg.get("GHOST-Q-060")["blocked_reason"], "requires-unmapped")  # QUEUED, then unmapped
        self.assertEqual(self.reg.get("GHOST-Q-061")["blocked_reason"], "legacy-status-discharged-unverified")
        self.assertEqual(self.reg.get("GHOST-Q-062")["blocked_reason"], "legacy-status-p0-unverified")
        self.assertIn("Shape A", self.reg.get("GHOST-Q-062")["spec"]["legacy_status"])  # full prose kept

    def test_unmapped_ids_are_blocked_not_guessed(self):
        q = os.path.join(self.d, "q2")
        os.makedirs(q)
        json.dump({"id": "GHOST-Q-099", "title": "new job", "requires_path": "free text", "status": "QUEUED"},
                  open(os.path.join(q, "GHOST-Q-099-x.json"), "w"))
        legacy.migrate(self.reg, q, MAPPING, actor="os:test")
        self.assertEqual(self.reg.get("GHOST-Q-099")["blocked_reason"], "requires-unmapped")


@unittest.skipUnless(signing.HAVE_CRYPTO, "cryptography not installed: Level B fails closed")
class Gates(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.reg = Registry(os.path.join(self.d, "g.db"))
        self.reg.add_job({"job_id": "GHOST-Q-001", "title": "t", "lane": "ops", "executor": "manual", "level": "A"},
                         actor="t", source="t", state="BLOCKED", blocked_reason="human:brandon-relay")
        keyfile = os.path.join(self.d, "owner.key")
        pub = signing.keygen(keyfile)
        self.key = signing.load_private(keyfile)
        self.esc = os.path.join(self.d, "esc")
        self.gate = gates.Gate(self.reg, verifier=signing.Verifier({"owner": {"owner:brandon": pub}}),
                               escalation_dir=self.esc, whoami=lambda: "zane")

    def grant(self, action="ghost_unblock", job="GHOST-Q-001", principal="os:zane", **kw):
        return signing.sign(self.key, issuer="owner:brandon", action=action, subject=job, principal=principal,
                            now=time.time(), **kw)

    def test_level_c_action_is_refused_logged_and_escalated(self):
        """Acceptance 3: a Level C-shaped action is refused in code, ledgered, and escalated to Brandon."""
        for kind, text in (("spend", ""), ("move_money", ""), ("release_envelope", "publish the Station app to the store"),
                           ("release_envelope", "make a payment of $40 to the vendor")):
            with self.assertRaises(gates.Refused) as cm:
                self.gate.commit(kind, job_id="GHOST-Q-001", text=text, now=time.time(), grant=self.grant())
            self.assertIsNotNone(cm.exception.escalation)
            esc_file = os.path.join(self.esc, f"ESC-{cm.exception.escalation:04d}.json")
            self.assertEqual(json.load(open(esc_file))["to"], "brandon")
        kinds = [json.loads(r["body"]) for r in self.reg.db.execute("SELECT body FROM ledger WHERE kind='gate_refused'")]
        self.assertEqual(len(kinds), 4)
        self.assertTrue(all(k["level"] == "C" for k in kinds))
        self.assertEqual(self.reg.get("GHOST-Q-001")["state"], "BLOCKED")  # nothing executed

    def test_level_c_capability_does_not_exist(self):
        self.assertFalse(any(gates.classify(k) == "C" for k in gates.EXECUTORS))
        for kind in ("spend", "publish", "move_money", "trade", "delete_irreversible", "wire_money_now"):
            with self.assertRaises(gates.Refused):
                gates.register_executor(kind, lambda *a, **k: None)
        with self.assertRaises(TypeError):
            gates.EXECUTORS["spend"] = lambda *a, **k: None  # read-only view

    def test_level_b_needs_valid_scoped_single_use_signature(self):
        with self.assertRaises(gates.Refused):
            self.gate.commit("ghost_unblock", job_id="GHOST-Q-001", now=time.time())
        with self.assertRaises(gates.Refused):  # bound to another job
            self.gate.commit("ghost_unblock", job_id="GHOST-Q-001", now=time.time(), grant=self.grant(job="GHOST-Q-002"))
        with self.assertRaises(gates.Refused):  # bound to another principal
            self.gate.commit("ghost_unblock", job_id="GHOST-Q-001", now=time.time(), grant=self.grant(principal="os:mallory"))
        g = self.grant()
        forged = {"payload": dict(g["payload"], action="ghost_cancel"), "signature": g["signature"]}
        with self.assertRaises(gates.Refused):
            self.gate.commit("ghost_cancel", job_id="GHOST-Q-001", now=time.time(), grant=forged)
        out = self.gate.commit("ghost_unblock", job_id="GHOST-Q-001", now=time.time(), grant=g)
        self.assertEqual(out["state"], "QUEUED")
        with self.assertRaises(gates.Refused):  # replay
            self.gate.commit("ghost_unblock", job_id="GHOST-Q-001", now=time.time(), grant=g)
        with self.assertRaises(gates.Refused):  # expired
            self.gate.commit("ghost_cancel", job_id="GHOST-Q-001", now=time.time() + 400, grant=self.grant("ghost_cancel"))

    def test_scope_is_required_even_with_a_signature(self):
        pol = os.path.join(self.d, "policy.json")
        json.dump({"operate": ["someone-else"]}, open(pol, "w"))
        gate = gates.Gate(self.reg, policy_path=pol, verifier=self.gate.verifier, whoami=lambda: "zane")
        with self.assertRaises(gates.Refused):
            gate.commit("ghost_unblock", job_id="GHOST-Q-001", now=time.time(), grant=self.grant())

    def test_paths_and_slugs_are_not_instructions_but_real_fence_prose_still_is(self):
        """Zane review D1: GHOST-Q-014's goal path 'college-enrollment-…' made the job Level C at import."""
        q014 = ("COLLEGE FUNDING COMPLETION — College of DuPage Spring 2027: machine owns investigation, follow-up "
                "workspace/goals/college-enrollment-college-of-dupage-spring-2027/files/COD_WAIVER_FOLLOWUP.md")
        self.assertEqual(gates.classify("release_envelope", q014), "A")
        for fence in ("enroll Brandon in the spring course", "publish the app", "make a payment to COD",
                      "sign up for a new account"):
            self.assertEqual(gates.classify("release_envelope", fence), "C", fence)

    def test_unknown_kinds_fail_closed_to_level_c(self):
        self.assertEqual(gates.classify("frobnicate"), "C")

    def test_grant_bytes_match_genesis_core_encoding(self):
        """One owner key for both systems: the payload encoding is identical to Genesis-core authority._encode."""
        g = self.grant()
        genesis_encode = lambda body: json.dumps(body, sort_keys=True, separators=(",", ":"),  # noqa: E731
                                                 ensure_ascii=True).encode("ascii")
        self.assertEqual(signing.encode(g["payload"]), genesis_encode(g["payload"]))
        self.assertEqual(set(g["payload"]), {"v", "issuer", "action", "mission_id", "principal", "nonce", "iat", "exp"})


if __name__ == "__main__":
    unittest.main()


class FailClosedWithoutCrypto(unittest.TestCase):
    def test_level_b_is_denied_when_signatures_cannot_be_checked(self):
        d = tempfile.mkdtemp()
        reg = Registry(os.path.join(d, "g.db"))
        reg.add_job({"job_id": "GHOST-Q-001", "title": "t", "lane": "ops", "executor": "manual", "level": "A"},
                    actor="t", source="t", state="BLOCKED", blocked_reason="human:x")
        saved = signing.HAVE_CRYPTO
        signing.HAVE_CRYPTO = False
        try:
            gate = gates.Gate(reg, verifier=signing.Verifier({"owner": {"owner:brandon": "AAAA"}}), whoami=lambda: "zane")
            fake = {"payload": {"v": 1, "issuer": "owner:brandon", "action": "ghost_unblock", "mission_id": "GHOST-Q-001",
                                "principal": "os:zane", "nonce": "a" * 48, "iat": int(time.time()),
                                "exp": int(time.time()) + 60}, "signature": "AAAA"}
            with self.assertRaises(gates.Refused) as cm:
                gate.commit("ghost_unblock", job_id="GHOST-Q-001", now=time.time(), grant=fake)
            self.assertIn("cryptography is not installed", str(cm.exception))
            self.assertEqual(reg.get("GHOST-Q-001")["state"], "BLOCKED")
        finally:
            signing.HAVE_CRYPTO = saved


@unittest.skipUnless(signing.HAVE_CRYPTO, "cryptography required for charters")
class PolicyClasses(unittest.TestCase):
    """POLICY-BASED-APPROVALS-2026-10-31: classes run tap-free, fences refuse, novel classes are asked once."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.reg = Registry(os.path.join(self.d, "g.db"))
        for n in (1, 2):
            self.reg.add_job({"job_id": f"GHOST-Q-00{n}", "title": "t", "lane": "ops", "executor": "manual",
                              "level": "A"}, actor="t", source="t", state="BLOCKED", blocked_reason="human:x")
        kf = os.path.join(self.d, "brandon.key")
        self.pub = signing.keygen(kf)
        self.key = signing.load_private(kf)
        self.ver = signing.Verifier({"owner": {"owner:brandon": self.pub}})

    def gate(self, charter, revoked=None):
        cp = os.path.join(self.d, "charter.json")
        json.dump(charter, open(cp, "w"))
        rp = None
        if revoked is not None:
            rp = os.path.join(self.d, "revoked.json")
            json.dump(revoked, open(rp, "w"))
        return gates.Gate(self.reg, verifier=self.ver, whoami=lambda: "zane", charter_path=cp, revoked_path=rp,
                          escalation_dir=os.path.join(self.d, "esc"))

    def charter(self, classes, **kw):
        return signing.sign_charter(self.key, issuer="owner:brandon", classes=classes, now=time.time(), **kw)

    def test_one_charter_signature_approves_every_item_in_the_class(self):
        g = self.gate(self.charter({"ghost_operations": "all"}))
        for jid in ("GHOST-Q-001", "GHOST-Q-002"):  # no per-item tap for either
            self.assertEqual(g.commit("ghost_unblock", job_id=jid, now=time.time())["state"], "QUEUED")
        rows = [json.loads(r[0]) for r in self.reg.db.execute("SELECT body FROM ledger WHERE kind='gate_allowed'")]
        self.assertTrue(all(r["policy_class"] == "ghost_operations" and r["charter_id"] for r in rows))

    def test_fences_stay_refused_even_if_a_charter_names_them(self):
        evil = self.charter({"ghost_operations": ["spend", "ghost_unblock"], "spend": "all", "publish": "all"})
        g = self.gate(evil)
        for kind in ("spend", "publish", "move_money"):
            with self.assertRaises(gates.Refused):
                g.commit(kind, job_id="GHOST-Q-001", now=time.time())
        with self.assertRaises(gates.Refused):  # Level C hidden in job text is still a fence
            g.commit("ghost_unblock", job_id="GHOST-Q-001", text="make a payment to the vendor", now=time.time())

    def test_a_charter_cannot_stretch_a_class_past_its_code_ceiling(self):
        g = self.gate(self.charter({"engineering": "all", "research": "all"}))  # no GHOST kinds in these ceilings
        with self.assertRaises(gates.Refused):
            g.commit("ghost_unblock", job_id="GHOST-Q-001", now=time.time())

    def test_revoked_expired_forged_or_missing_charters_fail_closed(self):
        c = self.charter({"ghost_operations": "all"})
        cases = [self.gate(c, revoked=[c["payload"]["charter_id"]]),
                 self.gate({"payload": dict(c["payload"], classes={"ghost_operations": "all", "x": 1}),
                            "signature": c["signature"]}),
                 gates.Gate(self.reg, verifier=self.ver, whoami=lambda: "zane")]
        for g in cases:
            with self.assertRaises(gates.Refused):
                g.commit("ghost_unblock", job_id="GHOST-Q-001", now=time.time())
        with self.assertRaises(gates.Refused):  # expired
            self.gate(self.charter({"ghost_operations": "all"}, days=1)).commit(
                "ghost_unblock", job_id="GHOST-Q-001", now=time.time() + 2 * 86400)
        with self.assertRaises(ValueError):
            self.charter({"ghost_operations": "all"}, days=365)  # max 180 days: approval is renewed, not forever

    def test_novel_class_is_asked_once_as_a_policy_question(self):
        g = self.gate(self.charter({"ghost_operations": "all"}))
        with self.assertRaises(gates.Refused) as cm:
            g.commit("rotate_dns", job_id="GHOST-Q-001", now=time.time())
        esc = json.load(open(os.path.join(self.d, "esc", f"ESC-{cm.exception.escalation:04d}.json")))
        self.assertEqual((esc["type"], esc["to"]), ("policy_question", "brandon"))
