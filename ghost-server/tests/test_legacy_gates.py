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
