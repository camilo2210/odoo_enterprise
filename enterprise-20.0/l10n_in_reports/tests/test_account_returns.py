from odoo import fields
from odoo.exceptions import RedirectWarning
from odoo.tests import tagged

from odoo.addons.l10n_in_reports.tests.common import L10nInTestAccountReportsCommon


@tagged('post_install', 'post_install_l10n', '-at_install')
class L10nInTestAccountReturn(L10nInTestAccountReportsCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gstr_return_types = cls.env.ref('l10n_in_reports.in_gstr1_return_type') + cls.env.ref('l10n_in_reports.in_gstr2b_return_type')

    def test_access_to_tax_return_view_is_not_restricted(self):
        """
        Test that any specific return filing feature disabled should not restrict access to the tax return view.
        """
        # If a fiscal year is set up without enabling the GST e-Filing feature,
        # access to the tax return view should not be restricted, and GSTR returns should not be created automatically.
        company = self.company_data['company']
        company.l10n_in_gst_efiling_feature = False

        self.env['account.return.type']._generate_or_refresh_all_returns(company)

        gstr_returns = self.env['account.return'].search([('company_id', '=', company.id), ('type_id', 'in', self.gstr_return_types.ids)])
        self.assertFalse(gstr_returns)

        # Attempting to manually create a GSTR return without the gst e-Filing feature enabled should raise a RedirectWarning.
        return_creation_wizard = self.env['account.return.creation.wizard'].create({
            'date_from': fields.Date.to_date('2026-01-01'),
            'date_to': fields.Date.to_date('2026-01-31'),
            'return_type_id': self.gstr_return_types[0].id,
        })
        with self.assertRaises(RedirectWarning):
            return_creation_wizard.action_create_manual_account_returns()
