from freezegun import freeze_time
from odoo.tests import tagged
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestITReportAccountReturn(TestAccountReportsCommon):

    @classmethod
    @TestAccountReportsCommon.setup_country('it')
    def setUpClass(cls):
        super().setUpClass()
        cls.it_vat_return_type = cls.env.ref('l10n_it_reports.it_tax_return_type')
        cls.it_withh_return_type = cls.env.ref('l10n_it_reports.it_withh_tax_return_type')

        cls.startClassPatcher(freeze_time('2026-06-10'))
        cls.env.company.account_opening_date = '2026-06-01'

    def test_it_return_types_closing(self):
        """ Ensures the closing entries and amounts to pay are properly computed for Italian VAT and Withholding returns """
        vat_may_return = self.env['account.return'].search([
            ('company_id', '=', self.company.id),
            ('date_from', '=', '2026-05-01'),
            ('date_to', '=', '2026-05-31'),
            ('type_id', '=', self.it_vat_return_type.id),
        ], limit=1)

        withh_may_return = self.env['account.return'].search([
            ('company_id', '=', self.company.id),
            ('date_from', '=', '2026-05-01'),
            ('date_to', '=', '2026-05-31'),
            ('type_id', '=', self.it_withh_return_type.id),
        ], limit=1)

        vat_sale = self.env['account.chart.template'].ref('22v')
        vat_purchase = self.env['account.chart.template'].ref('22am')
        withh_sale = self.env['account.chart.template'].ref('20vwi')
        withh_purchase = self.env['account.chart.template'].ref('20awi')

        # Sales: 100 Base -> +22.00 VAT, -20.00 Withholding
        inv = self.init_invoice(
            'out_invoice', partner=self.partner_a, invoice_date='2026-05-01',
            amounts=[100.0], taxes=vat_sale + withh_sale, post=True
        )

        # Purchases: 400 Base -> +88.00 VAT, -80.00 Withholding
        bill = self.init_invoice(
            'in_invoice', partner=self.partner_a, invoice_date='2026-05-05',
            amounts=[400.0], taxes=vat_purchase + withh_purchase, post=True
        )

        # Register payments to trigger the cash-basis withholding tax lines
        self.env['account.payment.register'].with_context(active_model='account.move', active_ids=inv.ids).create({
            'payment_date': '2026-05-10',
        })._create_payments()

        self.env['account.payment.register'].with_context(active_model='account.move', active_ids=bill.ids).create({
            'payment_date': '2026-05-15',
        })._create_payments()

        with self.allow_pdf_render():
            vat_may_return.action_validate()
            withh_may_return.action_validate()

        self.assertEqual(
            vat_may_return.closing_move_ids.line_ids.mapped(lambda aml: [aml.name, aml.account_name, aml.balance]),
            [
                ['22%',                     'VAT debt',      22.0],
                ['22% G',                   'VAT credit',   -88.0],
                ['Receivable tax amount',   'Treasury VAT Receivable',  66.0]
            ]
        )

        # Withholding should only include the 80.00 liability from the vendor bill. The 20.00 from sales must be ignored.
        self.assertEqual(
            withh_may_return.closing_move_ids.line_ids.mapped(lambda aml: [aml.name, aml.account_name, aml.balance]),
            [
                ['20% RIT PF',           'Payables for withholding taxes to be paid',  80.0],
                ['Payable tax amount',   'Debts for withholding taxes to be paid',    -80.0]
            ]
        )

        self.assertEqual(vat_may_return.total_amount_to_pay, -66.0, msg="VAT amount to pay should correctly net sales and purchases.")
        self.assertEqual(withh_may_return.total_amount_to_pay, 80.0, msg="Withholding amount to pay must strictly exclude sales withholding assets.")
