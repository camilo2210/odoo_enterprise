# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged, new_test_user
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestL10nDePosCertAccountTax(AccountTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_chart_template('de_skr03')
    def setUpClass(cls):
        super().setUpClass()

    def test_get_vat_definition_export_id_pos_user_without_erp_manager(self):
        """A normal POS user can run get_vat_definition_export_id (no Access Rights, added Accounting Manager for test purposes)."""
        company = self.company_data['company']
        pos_accounting_manager_user = new_test_user(
            self.env,
            login='pos_test_fiskaly_vat_%s' % company.id,
            groups='base.group_user,point_of_sale.group_pos_user,account.group_account_manager',
        )
        company.sudo().write({
            'country_id': self.env.ref('base.de').id,
            'l10n_de_fiskaly_organization_id': 'test-org-123',
            'l10n_de_fiskaly_api_key': 'test-api-key',
            'l10n_de_fiskaly_api_secret': 'test-api-secret',
        })
        tax = self.percent_tax(0.0, company_id=company.id)
        self.assertFalse(pos_accounting_manager_user.has_group('base.group_erp_manager'))

        tax.with_user(pos_accounting_manager_user)._get_vat_definition_export_id()
        self.assertEqual(tax.l10n_de_vat_definition_export_identifier, 5)
