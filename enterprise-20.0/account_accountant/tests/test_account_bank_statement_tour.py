from requests import Session, PreparedRequest, Response

from .common import TestBankRecWidgetCommon
from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestAccountBankStatementTour(TestBankRecWidgetCommon, HttpCase):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def _request_handler(cls, s: Session, r: PreparedRequest, /, **kw):
        # mock odoofin requests
        if 'proxy/v2/get_dashboard_institutions' in r.url:
            r = Response()
            r.status_code = 200
            r.json = list
            return r
        return super()._request_handler(s, r, **kw)

    def test_tour_bank_rec_widget(self):
        self.partner_a.name = "AAAA"  # To have this partner as the first one in the list
        self._create_invoice_one_line_reco(partner_id=self.partner_a.id, price_unit=100.0)
        self._create_invoice_one_line_reco(partner_id=self.partner_a.id, price_unit=150.0)
        self.env['account.bank.statement'].create({
            'name': 'Test Statement',
            'journal_id': self.company_data['default_journal_bank'].id,
            'date': '2019-01-01',
        })
        self.start_tour('/odoo', 'account_accountant_bank_rec_widget', login=self.env.user.login)

    def test_tour_bank_reconciliation_widget_reload_activities_when_add_a_new_one(self):
        self._create_st_line(amount=100.0)

        self.start_tour('/odoo', 'account_accountant_bank_reconciliation_widget_reload_activies_when_add_a_new_one', login=self.env.user.login)

    def test_tour_set_partner_with_child_contact(self):
        """ Test that a contact that has a parent contact can't be selected via the 'Set Partner' button """
        partner = self.env['res.partner'].create({'name': 'test child contact', 'parent_id': self.partner_a.id})
        self._create_invoice_one_line_reco(partner_id=partner.id, price_unit=100.0)
        self.start_tour('/odoo', 'account_accountant_set_partner_with_child_contact', login=self.env.user.login)

    def test_tour_bank_rec_set_partner_branch_company(self):
        """
        Test that the partner lookup in bank reconciliation uses the 'parent_of' domain,
        making contacts of ancestor companies visible when reconciling from a branch company.
        """
        # Create a branch company whose parent is the main test company
        branch_company = self.env['res.company'].create({
            'name': 'Test Branch',
            'parent_id': self.company_data['company'].id,
        })
        # Partner linked to the parent company — must appear in the branch's partner lookup
        self.env['res.partner'].create({
            'name': 'AAAA Parent Partner',
            'company_id': self.company_data['company'].id,
        })
        branch_journal = self.env['account.journal'].with_company(branch_company).create({
            'name': 'Branch Bank',
            'type': 'bank',
            'code': 'BBNK',
            'suspense_account_id': self.company_data['default_journal_bank'].suspense_account_id.id,
        })
        self.env['account.bank.statement.line'].with_company(branch_company).create({
            'amount': 100.0,
            'date': '2019-01-01',
            'payment_ref': 'branch line',
            'journal_id': branch_journal.id,
        })
        # Switch the user to the branch company so the dashboard shows the branch journal
        self.env.user.write({
            'company_ids': [(4, branch_company.id)],
            'company_id': branch_company.id,
        })
        self.start_tour(
            '/odoo',
            'account_accountant_bank_rec_set_partner_branch_company',
            login=self.env.user.login,
        )
