"""Tests for the S0 payments layer (paylinks) — no-API-key rails.

The QR encoder is verified properly, not by eyeballing: tests extract
the data modules back out of the rendered matrix (undoing the mask),
de-interleave, check Reed-Solomon syndromes are zero for every block,
and round-trip the payload.
"""
import json
import os
import sys
import unittest

PAY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PAY_DIR)

from genesis_pay import GenesisPay, build_rails, load_config, render_pay_page
from genesis_pay import paylinks
from genesis_pay.paylinks import (
    _QR_M_BLOCKS, _data_codewords, _format_bits, _interleave, _qr_matrix,
    _rs_encode,
)

INV = {"invoice_number": "INV-2026-0100", "total_cents": 29700,
       "currency": "USD", "status": "sent"}


def cfg(**over):
    base = json.loads(json.dumps(load_config()))
    base.update(over)
    return base


class TestRails(unittest.TestCase):
    def setUp(self):
        self.rails = {r["rail"]: r for r in build_rails(INV, load_config())}

    def test_all_four_rails_present(self):
        self.assertEqual(set(self.rails),
                         {"cash_app", "paypal", "current", "onepay"})

    def test_cash_app_verified_profile_link(self):
        r = self.rails["cash_app"]
        self.assertEqual(r["kind"], "link")
        self.assertEqual(r["url"], "https://cash.app/$zanehart369")
        self.assertEqual(r["status"], "VERIFIED")
        self.assertIn("$297.00", r["instruction"])
        self.assertIn("INV-2026-0100", r["instruction"])
        self.assertTrue(r["qr_svg"].startswith("<svg"))

    def test_paypal_handle_missing_is_honest(self):
        # The live config carries Brandon's handle since 2026-10-17;
        # exercise the missing-handle path on an explicit empty copy.
        c = cfg()
        c["paypal"] = dict(c["paypal"], paypal_me_handle=None)
        r = {x["rail"]: x for x in build_rails(INV, c)}["paypal"]
        self.assertEqual(r["status"], "HANDLE_NEEDED")
        self.assertIsNone(r["url"])           # never a guessed link
        self.assertIn("dawnmorrissette@gmail.com", " ".join(r["steps"]))
        self.assertIn("BRANDON", r["config_needed"])

    def test_paypal_with_handle_builds_verified_link(self):
        c = cfg()
        c["paypal"] = dict(c["paypal"], paypal_me_handle="ApexForge")
        rails = {r["rail"]: r for r in build_rails(INV, c)}
        self.assertEqual(rails["paypal"]["url"],
                         "https://www.paypal.me/ApexForge/297")
        rails2 = {r["rail"]: r for r in build_rails(
            {**INV, "total_cents": 7550}, c)}
        self.assertEqual(rails2["paypal"]["url"],
                         "https://www.paypal.me/ApexForge/75.50")

    def test_instruction_rails_carry_payee_amount_note(self):
        for key in ("current", "onepay"):
            r = self.rails[key]
            self.assertEqual(r["kind"], "instruction")
            steps = " ".join(r["steps"])
            self.assertIn("Brandon Duda", steps)
            self.assertIn("630-210-5724", steps)
            self.assertIn("$297.00", steps)
            self.assertIn("INV-2026-0100", steps)
            self.assertEqual(r["status"], "INSTRUCTION")


class TestPayPage(unittest.TestCase):
    def test_one_page_all_rails(self):
        page = render_pay_page(INV, load_config())
        for label in ("Cash App", "PayPal", "Current", "OnePay"):
            self.assertIn(label, page)
        self.assertIn("$297.00", page)
        self.assertIn("INV-2026-0100", page)
        self.assertIn("https://cash.app/$zanehart369", page)
        # Handle supplied 2026-10-17: the PayPal rail now renders the
        # one-tap amount-prefilled PayPal.Me link (+ QR), like Cash App.
        self.assertIn("https://www.paypal.me/DawnMorrissette/297", page)

    def test_invoice_number_is_escaped(self):
        evil = {**INV, "invoice_number": "X<script>alert(1)</script>"}
        page = render_pay_page(evil, load_config())
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)


def _extract_codewords(matrix, fn, size, mask):
    bits = []
    upward = True
    x = size - 1
    while x > 0:
        if x == 6:
            x -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for y in rows:
            for xx in (x, x - 1):
                if not fn[y][xx]:
                    dark = matrix[y][xx]
                    if ((mask == 0 and (y + xx) % 2 == 0) or
                        (mask == 1 and y % 2 == 0) or
                        (mask == 2 and xx % 3 == 0) or
                        (mask == 3 and (y + xx) % 3 == 0) or
                        (mask == 4 and (y // 2 + xx // 3) % 2 == 0) or
                        (mask == 5 and (y * xx) % 2 + (y * xx) % 3 == 0) or
                        (mask == 6 and ((y * xx) % 2 + (y * xx) % 3) % 2 == 0) or
                        (mask == 7 and ((y + xx) % 2 + (y * xx) % 3) % 2 == 0)):
                        dark = not dark
                    bits.append(1 if dark else 0)
        upward = not upward
        x -= 2
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for bit in bits[i:i + 8]:
            byte = (byte << 1) | bit
        out.append(byte)
    return bytes(out)


def _deinterleave(stream, version):
    ec_len, groups = _QR_M_BLOCKS[version]
    blocks_meta = []
    for count, dcw in groups:
        blocks_meta += [dcw] * count
    blocks = [bytearray() for _ in blocks_meta]
    pos = 0
    for i in range(max(blocks_meta)):
        for bi, dcw in enumerate(blocks_meta):
            if i < dcw:
                blocks[bi].append(stream[pos])
                pos += 1
    ecs = [bytearray() for _ in blocks_meta]
    for i in range(ec_len):
        for bi in range(len(blocks_meta)):
            ecs[bi].append(stream[pos])
            pos += 1
    return [bytes(b) for b in blocks], [bytes(e) for e in ecs]


class TestQrEncoder(unittest.TestCase):
    PAYLOADS = ["https://cash.app/$zanehart369",
                "https://www.paypal.me/ApexForge/297",
                "A", "x" * 100]

    def test_matrix_structure_and_format_bits(self):
        for payload in self.PAYLOADS:
            with self.subTest(payload=payload[:24]):
                version, size, matrix, mask, _fn = _qr_matrix(
                    payload, _return_fn=True)
                self.assertEqual(size, 4 * version + 17)
                # finder pattern corners
                self.assertTrue(matrix[0][0] and matrix[0][6]
                                and matrix[6][0] and not matrix[1][1])
                self.assertTrue(matrix[size - 8][8])  # dark module
                # read format bits back (first copy) and compare
                fb = 0
                pos = {}
                for i in range(6):
                    pos[i] = matrix[i][8]
                pos[6] = matrix[7][8]
                pos[7] = matrix[8][8]
                pos[8] = matrix[8][7]
                for i in range(9, 15):
                    pos[i] = matrix[8][14 - i]
                for i in range(15):
                    if pos[i]:
                        fb |= (1 << i)
                self.assertEqual(fb, _format_bits(mask))

    def test_decode_back_round_trip_and_zero_syndromes(self):
        for payload in self.PAYLOADS:
            with self.subTest(payload=payload[:24]):
                version, size, matrix, mask, fn = _qr_matrix(
                    payload, _return_fn=True)
                stream = _extract_codewords(matrix, fn, size, mask)
                expected = _interleave(
                    _data_codewords(payload.encode(), version), version)
                self.assertEqual(stream[:len(expected)], expected)
                blocks, ecs = _deinterleave(stream, version)
                ec_len, _g = _QR_M_BLOCKS[version]
                for block, ecc in zip(blocks, ecs):
                    self.assertEqual(_rs_encode(block + ecc, ec_len),
                                     bytes(ec_len),
                                     "RS syndrome must be zero")
                data = b"".join(blocks)
                bits = "".join(format(b, "08b") for b in data)
                self.assertEqual(bits[:4], "0100")  # byte mode
                ln = int(bits[4:12], 2)
                got = bytes(int(bits[12 + 8 * i:20 + 8 * i], 2)
                            for i in range(ln))
                self.assertEqual(got.decode(), payload)


class TestLedgerRecordsRailAndReference(unittest.TestCase):
    def test_confirm_records_instruction_rail(self):
        p = GenesisPay(":memory:")
        try:
            p.ingest_invoice_issued(INV, "pl-i")
            # Payer used the Current instruction rail and put the invoice
            # number in the note; Brandon confirms with rail + reference.
            r = p.record_confirmed_payment(
                {"id": 5, "status": "confirmed", "amount_cents": 29700,
                 "rail": "current", "reference": "INV-2026-0100"},
                INV["invoice_number"], "pl-p")
            intent = p.get_intent(r["intent_id"])
            self.assertEqual(intent["rail"], "current")
            self.assertEqual(intent["external_ref"], "INV-2026-0100")
            self.assertEqual(p.account_balance("1200_clearing:current"), 29700)
        finally:
            p.close()


if __name__ == "__main__":
    unittest.main()
