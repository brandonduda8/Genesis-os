"""Modules 1, 2, 9: registry law, bounded retries, lineage, append-only hash-chained ledger, recovery."""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ghost.registry import (BLOCKED, DEAD, DONE, QUEUED, RUNNING, Registry, RegistryError,  # noqa: E402
                            backoff_s, display_state)


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def job(n=1, **kw):
    return {"job_id": f"GHOST-Q-{n:03d}", "title": f"job {n}", "lane": "ops", "executor": "manual",
            "level": "A", **kw}


class RegistryLaw(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.clock = Clock()
        self.reg = Registry(os.path.join(self.d, "g.db"), clock=self.clock)

    def test_db_file_is_private(self):
        self.assertEqual(os.stat(self.reg.path).st_mode & 0o777, 0o600)

    def test_ids_must_be_deterministic_and_never_reused(self):
        with self.assertRaises(RegistryError):
            self.reg.add_job({**job(), "job_id": "fix-the-thing"}, actor="t", source="t")
        self.reg.add_job(job(), actor="t", source="t")
        with self.assertRaises(RegistryError):
            self.reg.add_job(job(), actor="t", source="t")

    def test_find_never_writes(self):
        self.reg.add_job(job(1, title="install aider"), actor="t", source="t")
        before = self.reg.db.total_changes
        self.assertEqual(self.reg.find("aider"), ["GHOST-Q-001"])
        self.assertEqual(self.reg.db.total_changes, before)

    def test_transition_requires_expected_state_and_version(self):
        j = self.reg.add_job(job(), actor="t", source="t")
        with self.assertRaises(RegistryError):
            self.reg.transition(j["job_id"], RUNNING, actor="t", transform="x", expect_state=QUEUED,
                                expect_version=j["version"] + 1)
        with self.assertRaises(RegistryError):  # illegal edge
            self.reg.transition(j["job_id"], DONE, actor="t", transform="x", expect_state=QUEUED)
        with self.assertRaises(RegistryError):  # free-form patch fields are refused
            self.reg.transition(j["job_id"], BLOCKED, actor="t", transform="x", expect_state=QUEUED,
                                patch={"title": "renamed"})

    def test_bounded_retries_with_backoff_then_dead_letter(self):
        self.reg.add_job(job(max_attempts=3), actor="t", source="t")
        jid = "GHOST-Q-001"
        for n in (1, 2):
            self.reg.start_attempt(jid, actor="t", lease_s=60)
            out = self.reg.finish_attempt(jid, actor="t", verified=False, outcome="fail", error_class="timeout")
            self.assertEqual(out["state"], QUEUED)
            self.assertEqual(out["next_eligible_at"], self.clock.t + backoff_s(n))
        self.reg.start_attempt(jid, actor="t", lease_s=60)
        out = self.reg.finish_attempt(jid, actor="t", verified=False, outcome="fail", error_class="timeout")
        self.assertEqual(out["state"], DEAD)
        self.assertEqual([backoff_s(n) for n in (1, 2, 3, 7, 20)], [60, 120, 240, 3600, 3600])

    def test_done_verified_is_frozen_by_trigger(self):
        self.reg.add_job(job(), actor="t", source="t")
        self.reg.start_attempt("GHOST-Q-001", actor="t", lease_s=60)
        self.reg.finish_attempt("GHOST-Q-001", actor="t", verified=True, outcome="verified")
        with self.assertRaises(sqlite3.DatabaseError):
            self.reg.db.execute("UPDATE jobs SET state='QUEUED' WHERE job_id='GHOST-Q-001'")
        with self.assertRaises(sqlite3.DatabaseError):
            self.reg.db.execute("DELETE FROM jobs")

    def test_ledger_and_lineage_are_append_only_and_tamper_evident(self):
        self.reg.add_job(job(), actor="t", source="t")
        for sql in ("UPDATE ledger SET actor='x'", "DELETE FROM ledger", "UPDATE lineage SET actor='x'",
                    "DELETE FROM lineage"):
            with self.assertRaises(sqlite3.DatabaseError):
                self.reg.db.execute(sql)
        self.assertTrue(self.reg.verify_ledger()["ok"])
        # an attacker with raw file access who drops the trigger is still caught by the hash chain
        self.reg.db.execute("DROP TRIGGER ledger_no_update")
        self.reg.db.execute("UPDATE ledger SET body='{}' WHERE seq=1")
        self.assertEqual(self.reg.verify_ledger(), {"ok": False, "records": 0, "broken_at_seq": 1})

    def test_recovery_requeues_expired_leases_as_counted_attempts(self):
        self.reg.add_job(job(), actor="t", source="t")
        self.reg.start_attempt("GHOST-Q-001", actor="t", lease_s=60)
        self.assertEqual(self.reg.recover(), [])  # lease still live
        self.clock.t += 61
        self.assertEqual(self.reg.recover(), ["GHOST-Q-001"])
        j = self.reg.get("GHOST-Q-001")
        self.assertEqual((j["state"], j["attempts"]), (QUEUED, 1))
        self.assertEqual(self.reg.provenance("GHOST-Q-001")["attempts"][0]["outcome"], "interrupted")

    def test_provenance_returns_complete_history_in_one_call(self):
        self.reg.add_job(job(), actor="os:a", source="ghost/queue/x.json@sha256:abc")
        self.reg.start_attempt("GHOST-Q-001", actor="os:b", lease_s=60)
        p = os.path.join(self.d, "art.txt")
        open(p, "w").write("evidence")
        self.reg.add_artifact("GHOST-Q-001", p, produced_by="os:b")
        self.reg.finish_attempt("GHOST-Q-001", actor="os:b", verified=True, outcome="verified")
        prov = self.reg.provenance("GHOST-Q-001")
        self.assertEqual([l["transform"] for l in prov["lineage"]], ["create", "attempt_start", "artifact", "verified"])
        self.assertEqual(prov["lineage"][0]["source"], "ghost/queue/x.json@sha256:abc")
        for a, b in zip(prov["lineage"], prov["lineage"][1:]):  # each step's input is the previous output
            self.assertEqual(b["input_sha256"], a["output_sha256"])
        self.assertEqual(len(prov["artifacts"]), 1)
        self.assertEqual(display_state(prov["job"]), "DONE-VERIFIED")
        self.assertTrue(any(r["kind"] == "transition" for r in prov["ledger"]))

    def test_state_survives_reopen(self):
        self.reg.add_job(job(), actor="t", source="t")
        self.reg.start_attempt("GHOST-Q-001", actor="t", lease_s=60)
        self.reg.close()
        again = Registry(os.path.join(self.d, "g.db"), clock=self.clock)
        self.assertEqual(again.get("GHOST-Q-001")["state"], RUNNING)
        self.assertTrue(again.verify_ledger()["ok"])


if __name__ == "__main__":
    unittest.main()
