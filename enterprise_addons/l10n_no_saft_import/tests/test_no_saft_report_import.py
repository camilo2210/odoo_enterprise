from odoo.tests import tagged
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestNoSaftImport(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('no')
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data['company'].write({
            'city': 'OSLO',
            'zip': 'N-0104',
            'phone': '+47 11 11 11 11',
            'l10n_no_bronnoysund_number': '987654325',
        })

    def test_saft_import_values(self):
        saft_filedata = self.file_read('l10n_no_saft_import/tests/data/audit_file_no_saft.xml')

        draft_moves_count = self.env['account.move'].search([
            *self.env['account.move']._check_company_domain(self.env.companies),
            ('state', '=', 'draft'),
        ], limit=1)
        # No draft move for the moment
        self.assertFalse(draft_moves_count)
        account = self.env['account.account'].search([
            *self.env['account.account']._check_company_domain(self.env.company),
            ('code', '=', '9999'),
        ])
        self.assertFalse(account)
        self.env['account.saft.import.wizard'].create({
            'attachment_id': saft_filedata,
            'import_opening_balance': True,
        }).action_import()

        # After the import we should have draft moves
        draft_moves_count = self.env['account.move'].search_count([
            *self.env['account.move']._check_company_domain(self.env.companies),
            ('state', '=', 'draft'),
        ])
        self.assertEqual(16, draft_moves_count)
        account = self.env['account.account'].search([
            *self.env['account.account']._check_company_domain(self.env.company),
            ('code', '=', '9999'),
        ])
        self.assertTrue(account)
