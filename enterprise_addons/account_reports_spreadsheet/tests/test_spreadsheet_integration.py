from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingHttpCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestAccountReportsSpreadsheetIntegration(AccountTestInvoicingHttpCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.startClassPatcher(freeze_time('2024-12-31'))

        default_group_ids = cls.env.user.group_ids.ids
        required_group_ids = [
            *default_group_ids,

            # Required to see the views
            cls.env.ref('account.group_account_user').id
        ]

        cls.account_return_user = cls.env['res.users'].create({
            'name': 'Account Return Test User',
            'login': 'account_return_test_user',
            'group_ids': [
                Command.link(id)
                for id in required_group_ids
            ],
        })

        # Prepare tax accounts
        cls.tax_account_1 = cls.env['account.account'].create({
            'name': 'Tax Account',
            'code': '250000',
            'account_type': 'liability_current',
        })

        cls.tax_account_2 = cls.env['account.account'].create({
            'name': 'Tax Account',
            'code': '250001',
            'account_type': 'liability_current',
        })

        cls.sale_tax_percentage_incl_1 = cls.env['account.tax'].create({
            'name': 'sale_tax_percentage_incl_1',
            'amount': 20.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'price_include_override': 'tax_included',
        })

        cls.sale_tax_percentage_excl = cls.env['account.tax'].create({
            'name': 'sale_tax_percentage_excl',
            'amount': 10.0,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
        })

        cls.sale_tax_group = cls.env['account.tax'].create({
            'name': 'sale_tax_group',
            'amount_type': 'group',
            'type_tax_use': 'sale',
            'children_tax_ids': [Command.set((cls.sale_tax_percentage_incl_1 + cls.sale_tax_percentage_excl).ids)],
        })

        cls.move_sale = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': '2016-01-01',
            'journal_id': cls.company_data['default_journal_sale'].id,
            'line_ids': [
                Command.create({
                    'debit': 1320.0,
                    'credit': 0.0,
                    'account_id': cls.company_data['default_account_receivable'].id,
                }),
                Command.create({
                    'debit': 0.0,
                    'credit': 120.0,
                    'account_id': cls.tax_account_1.id,
                    'tax_repartition_line_id': cls.sale_tax_percentage_excl.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax').id,
                }),
                Command.create({
                    'debit': 0.0,
                    'credit': 200.0,
                    'account_id': cls.tax_account_1.id,
                    'tax_repartition_line_id': cls.sale_tax_percentage_incl_1.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == 'tax').id,
                    'tax_ids': [Command.set(cls.sale_tax_percentage_excl.ids)]
                }),
                Command.create({
                    'debit': 0.0,
                    'credit': 1000.0,
                    'account_id': cls.company_data['default_account_revenue'].id,
                    'tax_ids': [Command.set(cls.sale_tax_group.ids)]
                }),
            ],
        })
        cls.move_sale.action_post()

    def test_account_reports_spreadsheet_integration(self):
        self.start_tour("/odoo/accounting", 'account_report_spreadsheet_integration', login=self.account_return_user.login)
