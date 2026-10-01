from odoo.tests.common import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('-at_install', 'post_install', 'post_install_l10n')
class TestL10nBeAccountJournal(AccountTestInvoicingCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()
        cls.company_data_2 = cls.setup_other_company()

    def test_cash_reco_model_creation(self):
        cash_journal = self.env['account.journal'].search([('type', '=', 'cash'), ('company_id', '=', self.company_data_2['company'].id)])
        client_reco_model = self.env.ref(f'l10n_be_reports.client_reco_model_{self.company_data_2['company'].id}', raise_if_not_found=False)
        self.assertTrue(client_reco_model)
        self.assertEqual(client_reco_model.match_journal_ids.ids, cash_journal.ids)
        cash_journal_2 = self.env['account.journal'].sudo().create({
            'name': 'test2',
            'code': 'TCSH2',
            'type': 'cash',
            'company_id': self.company_data_2['company'].id,
        })
        self.assertEqual(client_reco_model.match_journal_ids.ids, (cash_journal + cash_journal_2).ids)
