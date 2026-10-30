"""Genesis Vault Phase 2 tests: dated-debit watch, ranked sweep cards with math
and fee warnings, verified-rates parking comparison, daily digest.

Run from pay/: python3 -m unittest discover -s genesis_vault/tests
Same fences as v1: computing/rendering writes nothing, no rate is ever shown
without an official source + check date, and nothing executes a transfer.
"""
import contextlib
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path

from genesis_vault import board, parking, rules
from genesis_vault.cli import main
from genesis_vault.ledger import Vault, VaultError

TODAY = date(2026, 10, 30)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "vault.db"
        self.v = Vault(self.path)
        self.v.add_account("cash_app", "Cash App", "cash_app")
        self.v.add_account("chime", "Chime", "chime")
        self.v.add_account("robinhood", "Robinhood", "robinhood")

    def tearDown(self):
        self.v.close()
        self.tmp.cleanup()

    def state(self):
        db = self.v.db
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {t: [tuple(r) for r in db.execute(f"SELECT * FROM {t} ORDER BY rowid")] for t in tables}


class Watch(Base):
    def test_scheduled_debit_requires_date_and_account(self):
        with self.assertRaises(VaultError):
            self.v.add_scheduled_debit("d1", "Merchant", "10.00", due_date="", account="cash_app")
        with self.assertRaises(VaultError):
            self.v.add_scheduled_debit("d1", "Merchant", "10.00", due_date="2026-11-02", account="")
        oid = self.v.add_scheduled_debit("d1", "Merchant", "10.00", due_date="2026-11-02", account="cash_app")
        [o] = self.v.obligations()
        self.assertEqual((o["id"], o["kind"], o["due_date"], o["account"]),
                         (oid, "scheduled_debit", "2026-11-02", "cash_app"))

    def test_watch_window_includes_overdue_and_7d_excludes_8d_and_undated(self):
        self.v.set_balance("cash_app", "292.00", "2026-10-30")
        self.v.add_scheduled_debit("a", "Soon", "50.00", due_date="2026-11-02", account="cash_app")
        self.v.add_scheduled_debit("b", "Late", "10.00", due_date="2026-10-28", account="cash_app")
        self.v.add_scheduled_debit("c", "Far", "10.00", due_date="2026-11-07", account="cash_app")
        self.v.add_obligation("u", "Undated debit", "10.00", account="cash_app", kind="scheduled_debit")
        rows = rules.debit_watch(self.v.snapshot(), TODAY)
        self.assertEqual([r["payee"] for r in rows], ["Late", "Soon"])
        self.assertEqual(rows[0]["when"], "OVERDUE 2d")

    def test_watch_cumulative_coverage_runs_out_in_due_order(self):
        self.v.set_balance("cash_app", "100.00", "2026-10-30")
        self.v.add_scheduled_debit("a", "First", "60.00", due_date="2026-11-01", account="cash_app")
        self.v.add_scheduled_debit("b", "Second", "60.00", due_date="2026-11-03", account="cash_app")
        rows = rules.debit_watch(self.v.snapshot(), TODAY)
        self.assertEqual([(r["payee"], r["covered"], r["shortfall_cents"]) for r in rows],
                         [("First", True, 0), ("Second", False, 2000)])

    def test_watch_unknown_balance_is_none_not_a_guess(self):
        self.v.add_scheduled_debit("a", "Mystery", "10.00", due_date="2026-11-01", account="chime")
        [row] = rules.debit_watch(self.v.snapshot(), TODAY)
        self.assertIsNone(row["covered"])
        self.assertIsNone(row["shortfall_cents"])

    def test_deficit_guard_extended_to_dated_debits(self):
        # The $292 case shape: a dated debit larger than the balance flags DEFICIT,
        # and the same debit lands in the board's 7-day watch.
        self.v.set_balance("cash_app", "292.00", "2026-10-30")
        self.v.add_scheduled_debit("live", "Unknown merchant debit", "310.00",
                                   due_date="2026-11-04", account="cash_app")
        flags = rules.deficit_guard(self.v.snapshot(), TODAY)
        self.assertEqual([(f["level"], f["account"], f["shortfall_cents"]) for f in flags],
                         [("DEFICIT", "cash_app", 1800)])
        b = rules.board(self.v.snapshot(), TODAY)
        self.assertEqual([r["payee"] for r in b["debit_watch"]], ["Unknown merchant debit"])
        self.assertFalse(b["debit_watch"][0]["covered"])

    def test_due_window_lists_bills_and_debits_within_7d(self):
        self.v.add_obligation("bill", "Electric", "40.00", due_date="2026-11-05", account="chime")
        self.v.add_obligation("far", "Far bill", "40.00", due_date="2026-12-01", account="chime")
        rows = rules.due_window(self.v.snapshot(), TODAY)
        self.assertEqual([r["payee"] for r in rows], ["Electric"])


class SweepCards(Base):
    def test_cash_app_source_card_carries_fee_warning_and_math(self):
        self.v.set_balance("robinhood", "0", "2026-10-30")
        self.v.set_balance("cash_app", "100.00", "2026-10-30")
        self.v.add_scheduled_debit("rh", "Robinhood debit", "5.00", due_date="2026-11-01", account="robinhood")
        [card] = rules.sweep_suggestions(self.v.snapshot(), TODAY)
        self.assertEqual(card["status"], rules.PREPARED)
        self.assertEqual(card["rank"], 1)
        self.assertEqual(card["due_by"], "2026-11-01")
        self.assertIn("$5.00 short", card["math"])
        self.assertIn("$100.00 balance", card["math"])
        self.assertIn("fee preview in the Cash App app", card["fee_warning"])
        self.assertNotIn("%", card["fee_warning"])  # the fee itself is never stated or guessed

    def test_non_cash_app_source_has_no_cash_app_warning(self):
        self.v.set_balance("robinhood", "0", "2026-10-30")
        self.v.set_balance("chime", "100.00", "2026-10-30")
        self.v.add_scheduled_debit("rh", "Robinhood debit", "5.00", due_date="2026-11-01", account="robinhood")
        [card] = rules.sweep_suggestions(self.v.snapshot(), TODAY)
        self.assertEqual(card["from"], "chime")
        self.assertNotIn("fee_warning", card)

    def test_cards_ranked_by_earliest_due_then_shortfall(self):
        self.v.set_balance("cash_app", "500.00", "2026-10-30")
        self.v.set_balance("chime", "0", "2026-10-30")
        self.v.set_balance("robinhood", "0", "2026-10-30")
        self.v.add_scheduled_debit("late", "Late big", "50.00", due_date="2026-11-10", account="robinhood")
        self.v.add_scheduled_debit("early", "Early small", "5.00", due_date="2026-11-01", account="chime")
        cards = rules.sweep_suggestions(self.v.snapshot(), TODAY)
        self.assertEqual([(c["rank"], c["to"]) for c in cards], [(1, "chime"), (2, "robinhood")])

    def test_phase2_computation_writes_nothing(self):
        self.v.set_balance("cash_app", "292.00", "2026-10-30")
        self.v.set_balance("robinhood", "0", "2026-10-30")
        self.v.add_scheduled_debit("rh", "Robinhood debit", "5.00", due_date="2026-11-01", account="robinhood")
        self.v.add_obligation("t", "Talkiatry", "100.00", notice="final notice")
        before = self.state()
        snap = self.v.snapshot()
        b = rules.board(snap, TODAY)
        d = rules.daily_digest(snap, TODAY)
        comp = parking.parking_comparison(snap, parking.load_options(None), TODAY)
        board.render_text(b)
        board.render_html(b)
        board.render_digest({**d, "parking": comp})
        with contextlib.redirect_stdout(io.StringIO()):
            main(["--db", str(self.path), "digest", "--today", "2026-10-30"])
            main(["--db", str(self.path), "parking", "--today", "2026-10-30"])
        self.assertEqual(self.state(), before)  # no entry, no audit record, no transfer
        self.assertTrue(self.v.verify_audit()["ok"])


class ParkingOptions(unittest.TestCase):
    def test_defaults_are_held_first_and_all_unverified(self):
        opts = parking.load_options(None)
        self.assertTrue(all(o["held"] for o in opts))
        self.assertTrue(all(o["apy_percent"] is None for o in opts))
        self.assertEqual(opts[0]["account_slug"], "cash_app")

    def test_unverified_rate_shows_no_figure_and_no_projection(self):
        v = Vault(":memory:")
        try:
            v.add_account("cash_app", "Cash App", "cash_app")
            v.set_balance("cash_app", "1000.00", "2026-10-30")
            comp = parking.parking_comparison(v.snapshot(), parking.load_options(None), TODAY)
            self.assertIsNone(comp["best_verified"])
            row = next(r for r in comp["rows"] if r["account_slug"] == "cash_app")
            self.assertEqual(row["rate_status"], "UNVERIFIED")
            self.assertIsNone(row["apy_percent"])
            self.assertIsNone(row["projected_annual_cents"])
        finally:
            v.close()

    def test_record_verified_rate_requires_official_source_and_real_date(self):
        opts = parking.load_options(None)
        for bad in ({"source": "http://example.com/rates"}, {"source": "a blog post"},
                    {"checked": "2026-11-01"}, {"checked": "not-a-date"}):
            kw = {"name": "Cash App Savings", "apy_percent": "4.00",
                  "source": "https://cash.app/help", "checked": "2026-10-30"}
            kw.update(bad)
            with self.assertRaises(VaultError, msg=str(bad)):
                parking.record_verified_rate(opts, kw.pop("name"), kw.pop("apy_percent"),
                                             kw.pop("source"), kw.pop("checked"), TODAY)
        out = parking.record_verified_rate(opts, "Cash App Savings", "4.00",
                                           "https://cash.app/help", "2026-10-29", TODAY)
        self.assertIsNone(opts[0]["apy_percent"])  # input not mutated
        self.assertEqual(out[0]["rate_checked"], "2026-10-29")

    def test_verified_rate_projects_on_idle_only_and_goes_stale(self):
        v = Vault(":memory:")
        try:
            v.add_account("cash_app", "Cash App", "cash_app")
            v.set_balance("cash_app", "1000.00", "2026-10-30")
            v.add_scheduled_debit("d", "Due soon", "200.00", due_date="2026-11-05", account="cash_app")
            opts = parking.record_verified_rate(parking.load_options(None), "Cash App Savings",
                                                "5.00", "https://cash.app/help", "2026-10-30", TODAY)
            comp = parking.parking_comparison(v.snapshot(), opts, TODAY)
            row = comp["rows"][0]
            self.assertEqual(comp["best_verified"], "Cash App Savings")
            self.assertEqual(row["idle_cents"], 80000)  # $1000 - $200 due, $0 buffer
            self.assertEqual(row["projected_annual_cents"], 4000)  # $800 x 5% = $40.00
            stale = parking.parking_comparison(v.snapshot(), opts, date(2026, 12, 15))
            self.assertEqual(stale["rows"][0]["rate_status"], "STALE")
            self.assertIsNone(stale["rows"][0]["projected_annual_cents"])
            self.assertIsNone(stale["best_verified"])
        finally:
            v.close()


class Digest(Base):
    def test_digest_covers_balances_window_uncovered_and_waiting_cards(self):
        self.v.set_balance("cash_app", "292.00", "2026-10-30")
        self.v.set_balance("robinhood", "0", "2026-10-30")
        self.v.add_scheduled_debit("rh", "Robinhood debit", "5.00", due_date="2026-11-01", account="robinhood")
        self.v.add_obligation("t", "Talkiatry", "100.00", notice="final notice")
        d = rules.daily_digest(self.v.snapshot(), TODAY)
        self.assertEqual(d["sweep_cards_waiting"], 1)
        self.assertEqual([r["payee"] for r in d["debits_due_7d"]], ["Robinhood debit"])
        uncovered = {u["payee"]: u["why"] for u in d["uncovered"]}
        self.assertEqual(uncovered["Talkiatry"], "no paying account set")
        self.assertEqual(uncovered["Robinhood debit"], "account balance does not cover it")
        text = board.render_digest(d)
        self.assertIn("DEBITS DUE IN 7 DAYS", text)
        self.assertIn("SWEEP CARDS AWAITING YOUR TAP: 1", text)
        self.assertIn("Talkiatry", text)


class CliPhase2(Base):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--db", str(self.path), *args])
        return code, out.getvalue(), err.getvalue()

    def test_add_debit_and_digest_end_to_end(self):
        self.assertEqual(self.run_cli("seed-known")[0], 0)
        self.assertEqual(self.run_cli("set-balance", "cash_app", "292.00", "--as-of", "2026-10-30")[0], 0)
        code, _, err = self.run_cli("add-debit", "live-292", "Unknown merchant", "310.00",
                                    "--due", "2026-11-04", "--account", "cash_app")
        self.assertEqual(code, 0, err)
        code, out, _ = self.run_cli("digest", "--today", "2026-10-30")
        self.assertEqual(code, 0)
        self.assertIn("Unknown merchant  $310.00  due 2026-11-04 (in 5d)  [Cash App]  NOT COVERED, short $18.00", out)
        self.assertIn("UNCOVERED BILLS", out)
        self.assertIn("PARK FOR GROWTH", out)
        self.assertIn("rate not verified", out)
        # add-debit refuses a missing due date at the CLI layer too
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                main(["--db", str(self.path), "add-debit", "x", "M", "1.00", "--account", "cash_app"])
        self.assertEqual(cm.exception.code, 2)  # argparse: --due is required
        self.assertEqual(self.run_cli("audit-verify")[0], 0)

    def test_parking_set_rate_roundtrip(self):
        pfile = Path(self.tmp.name) / "parking.json"
        code, _, err = self.run_cli("parking-set-rate", "Cash App Savings", "4.25",
                                    "--source", "https://cash.app/help", "--checked", "2026-10-30",
                                    "--file", str(pfile))
        self.assertEqual(code, 0, err)
        opts = parking.load_options(pfile)
        self.assertEqual(opts[0]["apy_percent"], "4.25")
        code, _, err = self.run_cli("parking-set-rate", "Cash App Savings", "4.25",
                                    "--source", "http://not-official.example", "--checked", "2026-10-30",
                                    "--file", str(pfile))
        self.assertEqual(code, 2)
        self.assertIn("official source", err)


if __name__ == "__main__":
    unittest.main()
