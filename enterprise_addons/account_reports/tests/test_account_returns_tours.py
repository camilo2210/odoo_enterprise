from freezegun import freeze_time
from unittest.mock import patch

from odoo import Command
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingHttpCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestAccountReturnTours(AccountTestInvoicingHttpCommon):

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

        # Init tax closing journal so that it is set on the dashboard
        # By default the journal only appears when `accountant` is installed.
        journal = cls.env.company._get_tax_closing_journal()
        journal.show_on_dashboard = True

    def test_account_return_basic_tax_return(self):
        # states_workflow is by default generic_state_tax_report when this is a return linked to a tax report
        self.dummy_tax_return_type = self.env['account.return.type'].create([{
            'name': "DUMMY_TAX",
            'report_id': self.env.ref('account.generic_tax_report').id,
        }])
        self.dummy_tax_return_type._try_create_returns_for_fiscal_year(self.env.company, False)
        with patch.object(self.env.registry['ir.actions.report'], '_run_pdf_engine_without_processing', return_value=b"0"):
            self.start_tour("/odoo/accounting", 'account_return_flow_tax_return', login=self.account_return_user.login)
