"""Genesis Vault v1 deterministic tests (stdlib unittest). Run from pay/: python3 -m unittest discover -s genesis_vault/tests"""
import ast
import contextlib
import hashlib
import io
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from genesis_vault import board, rules
from genesis_vault.cli import main, seed_known
from genesis_vault.ledger import Vault, VaultError, fmt_cents, parse_cents

TODAY = date(2026, 10, 30)
PKG = Path(__file__).resolve().parents[1]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "vault.db"
        self.v = Vault(self.path)

    def tearDown(self):
        self.v.close()
        self.tmp.cleanup()

    def state(self):
        """Every row of every table, for before/after comparisons."""
        db = self.v.db
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {t: [tuple(r) for r in db.execute(f"SELECT * FROM {t} ORDER BY rowid")] for t in tables}


class Money(unittest.TestCase):
    def test_parse_cents_exact(self):
        self.assertEqual(parse_cents("292.00"), 29200)
        self.assertEqual(parse_cents("$1,234.5"), 123450)
        self.assertEqual(parse_cents("-5"), -500)
        self.assertEqual(parse_cents("0.01"), 1)
        self.assertEqual(parse_cents(750), 750)

    def test_parse_cents_refuses_floats_and_sub_cent(self):
        for bad in (12.5, "1.005", "abc", "NaN", "inf", "", True):
            with self.assertRaises(VaultError):
                parse_cents(bad)

    def test_fmt(self):
        self.assertEqual(fmt_cents(-123456), "-$1,234.56")
        self.assertEqual(fmt_cents(5), "$0.05")


class Ledger(Base):
    def test_pragmas(self):
        self.assertEqual(self.v.db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(self.v.db.execute("PRAGMA synchronous").fetchone()[0], 2)  # FULL
        self.assertEqual(self.v.db.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_unbalanced_entry_rejected_via_api(self):
        self.v.add_account("cash_app", "Cash App", "cash_app")
        self.v.add_account("chime", "Chime", "chime")
        before = self.state()
        with self.assertRaisesRegex(VaultError, "unbalanced"):
            self.v.post_entry("k1", "2026-10-30", "bad", [("cash_app", 500), ("chime", -499)])
        self.assertEqual(self.state(), before)

    def test_unbalanced_entry_rejected_by_trigger_raw_sql(self):
        a = self.v.add_account("cash_app", "Cash App", "cash_app")
        db = self.v.db
        db.execute("INSERT INTO entries (idempotency_key, effective_date, memo, source, created_at) "
                   "VALUES ('raw', '2026-10-30', 'raw', 'manual', 'now')")
        eid = db.execute("SELECT id FROM entries WHERE idempotency_key='raw'").fetchone()[0]
        db.execute("INSERT INTO postings (entry_id, account_id, amount_cents) VALUES (?, ?, 100)", (eid, a))
        with self.assertRaisesRegex(sqlite3.IntegrityError, "unbalanced"):
            db.execute("UPDATE entries SET posted = 1 WHERE id = ?", (eid,))
        self.assertEqual(self.v.balance("cash_app"), 0)  # unposted entries never count

    def test_single_posting_and_non_integer_rejected(self):
        self.v.add_account("cash_app", "Cash App", "cash_app")
        with self.assertRaises(VaultError):
            self.v.post_entry("k", "2026-10-30", "one leg", [("cash_app", 0)])
        with self.assertRaises(VaultError):
            self.v.post_entry("k2", "2026-10-30", "float", [("cash_app", 1.5), ("reconciliation", -1.5)])
        a = self.v._account_id("cash_app")
        self.v.db.execute("INSERT INTO entries (idempotency_key, effective_date, memo, source, created_at) "
                          "VALUES ('t', '2026-10-30', 't', 'manual', 'now')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.v.db.execute("INSERT INTO postings (entry_id, account_id, amount_cents) "
                              "VALUES ((SELECT id FROM entries WHERE idempotency_key='t'), ?, '5.00')", (a,))

    def test_postings_and_posted_entries_append_only(self):
        self.v.add_account("cash_app", "Cash App", "cash_app")
        eid = self.v.set_balance("cash_app", "40.00", "2026-10-30")
        db = self.v.db
        for sql in ("UPDATE postings SET amount_cents = 1", "DELETE FROM postings",
                    "UPDATE entries SET memo = 'x'", "DELETE FROM entries",
                    "UPDATE audit_log SET event = 'x'", "DELETE FROM audit_log"):
            with self.assertRaises(sqlite3.IntegrityError, msg=sql):
                db.execute(sql)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "posted"):
            db.execute("INSERT INTO postings (entry_id, account_id, amount_cents) VALUES (?, 1, 5)", (eid,))
        self.assertEqual(self.v.balance("cash_app"), 4000)

    def test_idempotent_entries(self):
        self.v.add_account("cash_app", "Cash App", "cash_app")
        self.v.add_account("chime", "Chime", "chime")
        e1 = self.v.post_entry("same", "2026-10-30", "m", [("cash_app", 100), ("chime", -100)])
        e2 = self.v.post_entry("same", "2026-10-30", "m", [("cash_app", 100), ("chime", -100)])
        self.assertEqual(e1, e2)
        self.assertEqual(self.v.balance("cash_app"), 100)

    def test_set_balance_zero_sum_and_restatement(self):
        self.v.add_account("cash_app", "Cash App", "cash_app")
        self.v.set_balance("cash_app", "43.12", "2026-10-29")
        self.v.set_balance("cash_app", "10.00", "2026-10-30")
        self.assertEqual(self.v.balance("cash_app"), 1000)
        self.assertEqual(self.v.ledger_total(), 0)
        self.assertIsNone(self.v.set_balance("cash_app", "10.00", "2026-10-30"))  # idempotent

    def test_zero_balance_statement_counts_as_known(self):
        self.v.add_account("robinhood", "Robinhood", "robinhood")
        self.assertFalse(self.v.balance_known("robinhood"))
        self.v.set_balance("robinhood", "0", "2026-10-30")
        self.assertTrue(self.v.balance_known("robinhood"))
        self.assertEqual(self.v.last_balance_date("robinhood"), "2026-10-30")

    def test_record_completed_transfer(self):
        self.v.add_account("cash_app", "Cash App", "cash_app")
        self.v.add_account("robinhood", "Robinhood", "robinhood")
        self.v.set_balance("cash_app", "50.00", "2026-10-30")
        self.v.record_completed_transfer("t1", "cash_app", "robinhood", "5.00", "2026-10-30")
        self.assertEqual((self.v.balance("cash_app"), self.v.balance("robinhood")), (4500, 500))
        with self.assertRaises(VaultError):
            self.v.record_completed_transfer("t2", "cash_app", "cash_app", "5.00", "2026-10-30")

    def test_csv_import_atomic_and_idempotent(self):
        for s, i in (("cash_app", "cash_app"), ("chime", "chime")):
            self.v.add_account(s, s, i)
        good = "account,balance,as_of\ncash_app,12.00,2026-10-30\nchime,3.50,2026-10-30\n"
        self.assertEqual(self.v.import_balances_csv(good), 2)
        self.assertEqual(self.v.import_balances_csv(good), 0)
        before = self.state()
        for bad in ("account,balance,as_of\ncash_app,1.00,2026-10-30\nnope,2.00,2026-10-30\n",
                    "account,balance,as_of\ncash_app,1.001,2026-10-30\n",
                    "acct,bal\ncash_app,1\n"):
            with self.assertRaises(VaultError):
                self.v.import_balances_csv(bad)
            self.assertEqual(self.state(), before)

    def test_audit_chain_verifies_and_detects_tamper(self):
        self.v.add_account("cash_app", "Cash App", "cash_app")
        self.v.set_balance("cash_app", "1.00", "2026-10-30")
        res = self.v.verify_audit()
        self.assertTrue(res["ok"])
        self.assertGreaterEqual(res["records"], 3)
        self.v.db.execute("DROP TRIGGER audit_no_update")  # simulate someone bypassing the guard
        self.v.db.execute("UPDATE audit_log SET payload = '{}' WHERE seq = 2")
        self.assertFalse(self.v.verify_audit()["ok"])


class Obligations(Base):
    def test_talkiatry_open_until_outcome_recorded_once(self):
        seed_known(self.v)
        [item] = self.v.obligations()
        self.assertEqual((item["payee"], item["amount_cents"], item["status"]), ("Talkiatry", 10000, "open"))
        bills = rules.bill_calendar(self.v.snapshot(), TODAY)
        self.assertTrue(bills[0]["final_notice"])
        self.assertEqual(bills[0]["when"], "DATE UNKNOWN")
        with self.assertRaises(VaultError):
            self.v.mark_outcome(item["id"], "executed")  # not a valid outcome
        self.v.mark_outcome(item["id"], "arranged", "payment plan by phone")
        self.assertEqual(rules.bill_calendar(self.v.snapshot(), TODAY), [])
        with self.assertRaises(VaultError):
            self.v.mark_outcome(item["id"], "paid")  # outcome recorded once
        with self.assertRaises(sqlite3.IntegrityError):
            self.v.db.execute("DELETE FROM obligations")

    def test_seed_is_idempotent_and_has_no_balances(self):
        seed_known(self.v)
        seed_known(self.v)
        self.assertEqual(len(self.v.obligations()), 1)
        self.assertEqual(len(self.v.accounts()), 7)
        self.assertTrue(all(a["balance_cents"] is None for a in self.v.snapshot()["accounts"]))

    def test_calendar_order(self):
        self.v.add_account("chime", "Chime", "chime")
        self.v.add_obligation("a", "Later", "1", due_date="2026-11-20", account="chime")
        self.v.add_obligation("b", "Overdue", "1", due_date="2026-10-25", account="chime")
        self.v.add_obligation("c", "Undated", "1")
        self.v.add_obligation("d", "Final", "1", due_date="2026-11-25", notice="FINAL notice")
        order = [r["payee"] for r in rules.bill_calendar(self.v.snapshot(), TODAY)]
        self.assertEqual(order, ["Final", "Overdue", "Undated", "Later"])


class Rules(Base):
    def setUp(self):
        super().setUp()
        self.v.add_account("cash_app", "Cash App", "cash_app", buffer="10.00")
        self.v.add_account("robinhood", "Robinhood", "robinhood")
        self.v.add_account("chime", "Chime", "chime")

    def test_robinhood_five_dollar_bounce_flagged(self):
        self.v.set_balance("robinhood", "0", "2026-10-30")
        self.v.add_obligation("rh", "Robinhood debit", "5.00", due_date="2026-11-01", account="robinhood",
                              kind="scheduled_debit")
        [flag] = rules.deficit_guard(self.v.snapshot(), TODAY)
        self.assertEqual((flag["level"], flag["account"], flag["shortfall_cents"]), ("DEFICIT", "robinhood", 500))

    def test_covered_and_far_future_not_flagged(self):
        self.v.set_balance("robinhood", "5.00", "2026-10-30")
        self.v.add_obligation("rh", "Robinhood debit", "5.00", due_date="2026-11-01", account="robinhood")
        self.v.add_obligation("far", "Far bill", "500", due_date="2027-01-30", account="robinhood")
        self.assertEqual(rules.deficit_guard(self.v.snapshot(), TODAY), [])

    def test_unknown_balance_and_unassigned_are_not_deficits(self):
        self.v.add_obligation("x", "Something", "20", due_date="2026-11-01", account="chime")
        self.v.add_obligation("y", "Talkiatry", "100")
        levels = sorted(f["level"] for f in rules.deficit_guard(self.v.snapshot(), TODAY))
        self.assertEqual(levels, ["UNASSIGNED", "UNKNOWN_BALANCE"])
        self.assertEqual(rules.sweep_suggestions(self.v.snapshot(), TODAY), [])

    def test_sweep_prepared_respects_buffer_and_other_bills(self):
        self.v.set_balance("robinhood", "0", "2026-10-30")
        self.v.set_balance("cash_app", "30.00", "2026-10-30")
        self.v.add_obligation("rh", "Robinhood debit", "5.00", due_date="2026-11-01", account="robinhood")
        self.v.add_obligation("ca", "Phone", "12.00", due_date="2026-11-02", account="cash_app")
        [card] = rules.sweep_suggestions(self.v.snapshot(), TODAY)
        self.assertEqual((card["status"], card["from"], card["to"], card["amount_cents"]),
                         (rules.PREPARED, "cash_app", "robinhood", 500))
        self.assertIn("does not move money", card["how"])

    def test_sweep_no_source_when_surplus_insufficient(self):
        self.v.set_balance("robinhood", "0", "2026-10-30")
        self.v.set_balance("cash_app", "12.00", "2026-10-30")  # $2 free after $10 buffer
        self.v.add_obligation("rh", "Robinhood debit", "5.00", due_date="2026-11-01", account="robinhood")
        cards = rules.sweep_suggestions(self.v.snapshot(), TODAY)
        self.assertEqual([(c["status"], c["amount_cents"]) for c in cards],
                         [(rules.PREPARED, 200), ("NO_SOURCE", 300)])

    def test_suggestion_never_auto_executes(self):
        self.v.set_balance("robinhood", "0", "2026-10-30")
        self.v.set_balance("cash_app", "100.00", "2026-10-30")
        self.v.add_obligation("rh", "Robinhood debit", "5.00", due_date="2026-11-01", account="robinhood")
        before = self.state()
        b = rules.board(self.v.snapshot(), TODAY)
        board.render_text(b)
        board.render_html(b)
        with contextlib.redirect_stdout(io.StringIO()):
            main(["--db", str(self.path), "board", "--today", "2026-10-30"])
        self.assertEqual(self.state(), before)  # nothing written: no entry, no audit record, no transfer
        self.assertEqual((self.v.balance("cash_app"), self.v.balance("robinhood")), (10000, 0))
        self.assertTrue(all(c["status"] in (rules.PREPARED, "NO_SOURCE") for c in b["sweeps"]))
        for mod in (rules, board):
            self.assertFalse([n for n in dir(mod) if any(w in n.lower() for w in ("execute", "send", "transfer", "pay"))])

    def test_package_has_no_network_or_process_code(self):
        banned = {"socket", "ssl", "http", "urllib", "requests", "subprocess", "smtplib", "ftplib", "asyncio"}
        for f in PKG.rglob("*.py"):
            tree = ast.parse(f.read_text())
            for node in ast.walk(tree):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                self.assertFalse({n.split(".")[0] for n in names} & banned, f"{f.name} imports {names}")

    def test_board_deterministic_and_html_escaped(self):
        self.v.add_obligation("evil", "<script>alert(1)</script>", "1", due_date="2026-11-01", account="chime")
        b1 = rules.board(self.v.snapshot(), TODAY)
        b2 = rules.board(self.v.snapshot(), TODAY)
        self.assertEqual(b1, b2)
        h = board.render_html(b1)
        self.assertNotIn("<script>", h)
        self.assertIn("&lt;script&gt;", h)
        self.assertEqual(hashlib.sha256(board.render_text(b1).encode()).hexdigest(),
                         hashlib.sha256(board.render_text(b2).encode()).hexdigest())

    def test_stale_balance_noted(self):
        self.v.set_balance("chime", "1.00", "2026-10-20")
        self.assertEqual(rules.board(self.v.snapshot(), TODAY)["stale_balances"], ["chime"])


class Cli(Base):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--db", str(self.path), *args])
        return code, out.getvalue(), err.getvalue()

    def test_end_to_end(self):
        self.assertEqual(self.run_cli("seed-known")[0], 0)
        self.assertEqual(self.run_cli("set-balance", "robinhood", "0", "--as-of", "2026-10-30")[0], 0)
        self.assertEqual(self.run_cli("set-balance", "cash_app", "25.00", "--as-of", "2026-10-30")[0], 0)
        self.assertEqual(self.run_cli("add-bill", "rh1", "Robinhood debit", "5.00", "--due", "2026-11-01",
                                      "--account", "robinhood", "--kind", "scheduled_debit")[0], 0)
        html_path = Path(self.tmp.name) / "board.html"
        code, out, _ = self.run_cli("board", "--today", "2026-10-30", "--html", str(html_path))
        self.assertEqual(code, 0)
        self.assertIn("!! Robinhood: $5.00 scheduled vs $0.00 balance, short $5.00", out)
        self.assertIn("[PREPARED_ONLY] Move $5.00 from Cash App to Robinhood", out)
        self.assertIn("FINAL NOTICE Talkiatry  $100.00  DATE UNKNOWN", out)
        self.assertIn("PREPARED_ONLY", html_path.read_text())
        self.assertEqual(self.run_cli("audit-verify")[0], 0)

    def test_bad_input_exit_2(self):
        code, _, err = self.run_cli("set-balance", "nope", "1", "--as-of", "2026-10-30")
        self.assertEqual(code, 2)
        self.assertIn("unknown account", err)


if __name__ == "__main__":
    unittest.main()
