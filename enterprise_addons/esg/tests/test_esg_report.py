from odoo import Command

from odoo.addons.esg.tests.esg_common import TestEsgCommon
from odoo.exceptions import ValidationError


class TestEsgReport(TestEsgCommon):

    _test_user_groups = None  # FIXME list needed groups

    def test_knowledge_report_data(self):
        esg_report = self.env['esg.report'].create({
            'title': 'VSME Report',
            'report_type': 'vsme_basic',
            'start_date': '1125-01-01',
            'end_date': '1125-12-31',
            'base_year': 1110,
            'company_id': self.env.company.id,
        })
        self.partner_a.country_id = self.env['res.country'].search([('code', '=', 'KR')])
        moves = bill_1, _invoice_1, _invoice_2 = self.env['account.move'].create([
            {
                'partner_id': self.partner_a.id,
                'move_type': 'in_invoice',
                'invoice_date': '1125-01-01',
                'invoice_line_ids': [
                    Command.create({
                        'quantity': 1,
                        'price_unit': 1000,
                    }),
                    Command.create({
                        'quantity': 50,
                        'price_unit': 250,
                        'account_id': self.expense_account.id,
                        'esg_emission_factor_id': self.emission_factor_computers_production.id,
                        'product_uom_id': self.env.ref('uom.product_uom_unit').id,
                    }),
                ],
            },
            {
                'partner_id': self.partner_a.id,
                'move_type': 'out_invoice',
                'invoice_date': '1125-01-01',
                'invoice_line_ids': [Command.create({
                    'quantity': 1,
                    'price_unit': 500,
                    'account_id': self.env.ref(f'account.{self.env.company.id}_income').id,
                })],
            },
            {
                'partner_id': self.partner_a.id,
                'move_type': 'out_invoice',
                'invoice_date': '1125-01-01',
                'invoice_line_ids': [Command.create({
                    'quantity': 1,
                    'price_unit': 100,
                })]
            },
        ])
        moves.action_post()
        bill_line = bill_1.line_ids.filtered(lambda line: line.account_id.account_type in {'asset_receivable', 'liability_payable'})
        self.env['account.payment.register'].with_context(
            active_ids=bill_line.move_id.ids,
            active_model='account.move',
        ).create({
            'amount': 800,
            'journal_id': self.company_data['default_journal_bank'].id,
            'payment_date': '1125-01-16',
        })._create_payments()
        bill_1.invoice_date_due = '1125-01-31'
        self.env.cr.flush()  # Used to force 'invoice_date_due' stored in DB
        data = esg_report._get_knowledge_report_data()

        self.assertEqual(data['report_name'], 'VSME Report')
        self.assertEqual(data['company_name'], self.env.company.name)
        self.assertEqual(data['avg_days_payment_reporting'], '15.0')
        self.assertEqual(data['pct_payment_on_terms_reporting'], '100.0')
        self.assertEqual(data['avg_days_payment_base'], '0')
        self.assertEqual(data['pct_payment_on_terms_base'], '0')
        self.assertEqual(data['reporting_type'], 'VSME - Basic Module')
        self.assertEqual(data['legal_form'], self.env.company.partner_id._get_preferred_legal_entity_identifier_vals().get('value') or '[Not Mentioned]')
        self.assertEqual(data['nace_code'], '[Not Mentioned]')
        self.assertEqual(data['country_of_main_operations'], self.env.company.country_id.name)
        self.assertEqual(data['balance_sheet_total'], '-200.0')  # -800 + 500 + 100
        self.assertEqual(data['net_turnover'], '-600.0')  # -500 - 100
        self.assertEqual(data['ghg_total'], '4.648')  # 50 (aml quantity) * 92.96 (factor value) * 1.0 (unit->unit conversion) = 4648 kgCO2e
        self.assertEqual(data['ghg_intensity'], '-0.00775')  # 4.648 / (-600.0)
        self.assertEqual(data['main_market_regions'], self.partner_a.country_id.name)

    def test_esg_report_base_year_validation(self):
        """Test that the base year validation works correctly."""
        EsgReport = self.env['esg.report']
        # Test with a valid base year
        report = EsgReport.create({
            'title': 'Test Report',
            'report_type': 'vsme_basic',
            'start_date': '2026-01-01',
            'end_date': '2026-12-31',
            'base_year': 2024,
        })
        self.assertEqual(report.base_year, 2024)

        # Test with an invalid base year
        with self.assertRaises(ValidationError):
            EsgReport.create({
                'title': 'Invalid Report',
                'report_type': 'vsme_basic',
                'start_date': '2026-01-01',
                'end_date': '2026-12-31',
                'base_year': 10,
            })
