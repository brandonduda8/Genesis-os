import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_pay_page import checks

GOOD = """<h1>Invoice $292.00</h1><a href="https://cash.app/$zanehart369/292">Cash App</a>
<a href="https://paypal.me/DawnMorrissette/292">PayPal</a><p>Current</p><p>OnePay</p>"""


class VerifyPayPage(unittest.TestCase):
    def test_good_page_passes(self):
        self.assertTrue(all(ok for _, ok, _ in checks(GOOD, Decimal("292.00"))))

    def test_wrong_paypal_amount_fails_and_reports_url(self):
        res = {n: (ok, d) for n, ok, d in checks(GOOD.replace("DawnMorrissette/292", "DawnMorrissette/29"), Decimal("292.00"))}
        ok, detail = res["PayPal.Me link paypal.me/DawnMorrissette/292"]
        self.assertFalse(ok)
        self.assertIn("paypal.me/DawnMorrissette/29", detail)

    def test_missing_rails_fail(self):
        res = dict((n, ok) for n, ok, _ in checks("<p>$292.00</p>", Decimal("292.00")))
        self.assertEqual(sum(res.values()), 1)

    def test_cents_amount(self):
        page = GOOD.replace("$292.00", "$292.50").replace("DawnMorrissette/292", "DawnMorrissette/292.50")
        self.assertTrue(all(ok for _, ok, _ in checks(page, Decimal("292.50"))))


if __name__ == "__main__":
    unittest.main()
