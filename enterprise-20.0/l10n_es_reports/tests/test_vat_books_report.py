from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

from odoo import fields
from odoo.tests import tagged


@tagged("post_install_l10n", "post_install", "-at_install")
class TestL10nEsAccountReportVatBooks(TestAccountReportsCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country("es")
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref("l10n_es_reports.l10n_es_vat_books_report")

    def test_withholding_tax_is_excluded_from_total_vat(self):
        tax_21 = self.env['account.chart.template'].ref("account_tax_template_s_iva21b")
        tax_9_whi = self.env['account.chart.template'].ref("account_tax_template_s_irpf9")
        self._create_invoice_one_line(
            product_id=self.product,
            quantity=4,
            tax_ids=tax_21 + tax_9_whi,
            partner_id=self.partner_a,
            invoice_date=fields.Date.from_string("2026-04-17"),
            post=True
        )
        options = self._generate_options(self.report, "2026-04-01", "2026-04-30")

        self.assertLinesValues(
            self.report._get_lines(options),
                     #                      Invoice Date         Partner     Invoice Total  Vat total]
            [        0,                            1,                2,             3,             4],
            [
                ("Income",                         "",              "",            "",            ""),
                ("INV/2026/00001",           "04/17/2026",    "partner_a",       80.0,          16.8),
            ],
            options,
        )
