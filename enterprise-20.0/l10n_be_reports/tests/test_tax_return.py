from freezegun import freeze_time
from unittest.mock import patch
from odoo.tests import tagged
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from odoo import Command


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestBEReportAccountReturn(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.be_vat_return_type = cls.env.ref('l10n_be_reports.be_vat_return_type')

        cls.startClassPatcher(freeze_time('2024-01-16'))

        with cls._patch_returns_generation():
            cls.env.company.account_opening_date = '2024-01-01'

    @classmethod
    def _patch_returns_generation(cls):
        def patched_generate_all_returns(account_return_type, country_code, main_company, tax_unit=None, return_types=None):
            cls.be_vat_return_type._try_create_returns_for_fiscal_year(main_company, tax_unit)

        return patch.object(cls.registry['account.return.type'], '_generate_all_returns', patched_generate_all_returns)

    def test_ec_sales_return_auto_generation(self):
        ec_return_type = self.env.ref('l10n_be_reports.be_ec_sales_list_return_type')
        self.env['account.return.type']._generate_all_returns('BE', self.env.company, None)
        returns = self.env['account.return'].search([
            ('type_id', '=', ec_return_type.id)
        ])
        self.assertFalse(returns)

        goods_tax_tag_id = self.env['l10n_be.ec.sales.report.handler']._get_ec_sales_tax_tags()['goods'][0]

        move = self.env['account.move'].create([{
            'move_type': 'entry',
            'date': '2023-12-31',
            'line_ids': [
                Command.create({
                    'debit': 0.0,
                    'credit': 100.0,
                    'account_id': self.company_data['default_account_expense'].id,
                }),
                Command.create({
                    'debit': 100.0,
                    'credit': 0.0,
                    'account_id': self.company_data['default_account_revenue'].id,
                    'tax_tag_ids': (goods_tax_tag_id,),
                }),
            ],
        }])
        move.action_post()

        self.env['account.return.type']._generate_all_returns('BE', self.env.company, None)
        returns = self.env['account.return'].search([
            ('type_id', '=', ec_return_type.id)
        ])
        self.assertTrue(returns)

    def test_be_vat_return_check_intervat_validation(self):
        """ Ensures the check 'Intervat Validation' is generated and fails if failed controls occurs on the tax report"""
        first_return = self.env['account.return'].search([
            ('date_from', '=', '2023-12-01'),
            ('date_to', '=', '2023-12-31'),
            ('type_id', '=', self.be_vat_return_type.id),
        ])

        first_return.refresh_checks()
        self.assertFalse(first_return.check_ids.filtered(lambda c: c.code == 'be_vat_compliance'))

        default_number_of_test = len(first_return.check_ids)
        be_vat_report = self.be_vat_return_type.report_id
        tax_tags = be_vat_report.line_ids.expression_ids._get_matching_tags()[0]

        # Setting the tax tag '00' in credit results in a negative amount on the tax report, leading to a failed check
        move = self.env['account.move'].create([{
            'move_type': 'entry',
            'date': '2023-12-31',
            'line_ids': [
                Command.create({
                    'debit': 0.0,
                    'credit': 100.0,
                    'account_id': self.company_data['default_account_expense'].id,
                }),
                Command.create({
                    'debit': 100.0,
                    'credit': 0.0,
                    'account_id': self.company_data['default_account_revenue'].id,
                    'tax_tag_ids': tax_tags.ids,
                }),
            ],
        }])
        move.action_post()

        first_return.refresh_checks()
        self.assertEqual(len(first_return.check_ids), default_number_of_test + 1)
        self.assertEqual(first_return.check_ids.filtered(lambda c: c.code == 'be_vat_compliance').result, 'anomaly')

    def test_be_vat_return_prorata_year_override(self):
        """ Test that manually modifying the prorata year in the lock wizard is correctly stored and retrieved in the generated xml. """

        vat_return = self.env['account.return'].create({
            'name': 'Test VAT Return Q1 2024',
            'date_from': '2024-01-01',
            'date_to': '2024-03-31',
            'type_id': self.be_vat_return_type.id,
            'company_id': self.env.company.id,
        })

        wizard = self.env['l10n_be_reports.vat.return.submission.wizard'].create({
            'return_id': vat_return.id,
            'is_prorata_necessary': True,
            'prorata': 50,
            'prorata_year': '2023',
        })
        self.assertEqual(wizard.prorata_year, '2023')

        options = wizard._get_submission_options_to_inject()
        self.assertEqual(options['prorata_deduction']['prorata_year'], '2023')
