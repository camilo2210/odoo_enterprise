from unittest.mock import MagicMock, patch

import requests

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged

TCMB_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<Tarih_Date Tarih="24.08.2026" Date="08/24/2026">
    <Currency CrossOrder="0" Kod="USD" CurrencyCode="USD">
        <ForexBuying>47.9924</ForexBuying>
        <ForexSelling>48.0788</ForexSelling>
    </Currency>
</Tarih_Date>"""

SELL_RATE = 1 / 48.0788
BUY_RATE = 1 / 47.9924


@tagged("post_install_l10n", "post_install", "-at_install")
class TestL10nTrCurrencyRateType(AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country("tr")
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.currency_provider = "tcmb"

        cls.foreign_currency = cls.setup_other_currency("USD", rates=[])
        cls.env["res.currency.rate"].create({
            "name": "2020-01-01",
            "currency_id": cls.foreign_currency.id,
            "company_id": cls.company.id,
            "rate": SELL_RATE,
            "l10n_tr_buy_rate": BUY_RATE,
        })

    def _create_move(self, move_type, partner=None):
        return self.env["account.move"].create({
            "move_type": move_type,
            "partner_id": (partner or self.partner_a).id,
            "currency_id": self.foreign_currency.id,
            "invoice_date": "2026-01-01",
            "date": "2026-01-01",
            "invoice_line_ids": [Command.create({"name": "line", "quantity": 1, "price_unit": 100, "tax_ids": []})],
        })

    def _create_payment(self, payment_type):
        return self.env["account.payment"].create({
            "payment_type": payment_type,
            "partner_type": "supplier" if payment_type == "outbound" else "customer",
            "partner_id": self.partner_a.id,
            "amount": 100.0,
            "currency_id": self.foreign_currency.id,
            "date": "2026-01-01",
        })

    def test_default_rate_type_follows_document_type(self):
        """Purchase documents default to the buying rate, sale documents to the selling rate."""
        for move_type, expected in [
            ("in_invoice", "buy"),
            ("in_refund", "buy"),
            ("out_invoice", "sell"),
            ("out_refund", "sell"),
        ]:
            with self.subTest(move_type=move_type):
                self.assertEqual(self._create_move(move_type).l10n_tr_currency_rate_type, expected)

    def test_partner_preference_overrides_the_default(self):
        """Each document type reads its own partner preference, not the other one."""
        self.partner_a.write({
            "l10n_tr_bill_currency_rate_type": "sell",       # opposite of the bill default
            "l10n_tr_invoice_currency_rate_type": "buy",     # opposite of the invoice default
        })
        self.assertEqual(self._create_move("in_invoice").l10n_tr_currency_rate_type, "sell")
        self.assertEqual(self._create_move("out_invoice").l10n_tr_currency_rate_type, "buy")

    def test_partner_preference_learned_on_first_post(self):
        """Posting fills an empty partner preference, and never overwrites one already set."""
        bill = self._create_move("in_invoice")
        bill.action_post()
        self.assertEqual(self.partner_a.l10n_tr_bill_currency_rate_type, "buy")
        self.assertFalse(self.partner_a.l10n_tr_invoice_currency_rate_type)

        other_bill = self._create_move("in_invoice")
        other_bill.l10n_tr_currency_rate_type = "sell"
        other_bill.action_post()
        self.assertEqual(self.partner_a.l10n_tr_bill_currency_rate_type, "buy")

    def test_partner_preference_not_learned_without_buy_sell(self):
        """A company that doesn't use buying rates must not write a preference on the partner."""
        self.company.currency_provider = "ecb"
        self._create_move("in_invoice").action_post()
        self.assertFalse(self.partner_a.l10n_tr_bill_currency_rate_type)

    def test_default_rate_type_on_payments(self):
        """Sending money defaults to the buying rate, receiving to the selling rate."""
        self.assertEqual(self._create_payment("outbound").l10n_tr_currency_rate_type, "buy")
        self.assertEqual(self._create_payment("inbound").l10n_tr_currency_rate_type, "sell")

    def test_toggle_rate_type(self):
        """The toggle flips the rate type while draft, and is inert once posted."""
        bill = self._create_move("in_invoice")
        bill.l10n_tr_action_toggle_currency_rate_type()
        self.assertEqual(bill.l10n_tr_currency_rate_type, "sell")

        bill.action_post()
        bill.l10n_tr_action_toggle_currency_rate_type()
        self.assertEqual(bill.l10n_tr_currency_rate_type, "sell")

    def test_get_currency_rate(self):
        """The date picker's rate lookup follows a single move's rate type, and tolerates having none."""
        args = (self.company.id, self.foreign_currency.id, "2026-01-01")
        self.assertAlmostEqual(self._create_move("in_invoice").get_currency_rate(*args), BUY_RATE)
        self.assertAlmostEqual(self._create_move("out_invoice").get_currency_rate(*args), SELL_RATE)
        # account also calls it as a plain helper, with no move to read a rate type from
        self.assertAlmostEqual(self.env["account.move"].get_currency_rate(*args), SELL_RATE)

    def test_show_buy_rate_only_for_buy_sell_companies(self):
        """The UI gate follows the company's rate provider."""
        self.assertTrue(self.foreign_currency.l10n_tr_show_buy_rate)
        self.company.currency_provider = "ecb"
        self.foreign_currency.invalidate_recordset(["l10n_tr_show_buy_rate"])
        self.assertFalse(self.foreign_currency.l10n_tr_show_buy_rate)

    def test_parse_tcmb_data_returns_both_rates(self):
        """The TCMB feed yields a buying rate alongside the selling one."""
        response = MagicMock()
        response.text = TCMB_SAMPLE
        with patch.object(requests.Session, "get", return_value=response):
            parsed = self.company._parse_tcmb_data(self.foreign_currency | self.company.currency_id)

        self.assertEqual(parsed["USD"][0], SELL_RATE)
        self.assertEqual(parsed["USD_buy"][0], BUY_RATE)
        self.assertEqual(parsed["USD"][1], "2026-08-24")
        self.assertGreater(parsed["USD_buy"][0], parsed["USD"][0], "buying a unit of foreign currency costs less")
        self.assertEqual(parsed["TRY"][0], 1.0)
        self.assertEqual(parsed["TRY_buy"][0], 1.0)
