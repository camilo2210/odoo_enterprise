# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'post_install_l10n')
class TestIntervatSettings(TransactionCase):

    def test_show_intervat_settings_with_foreign_vat(self):
        """
        Ensure companies with BE fiscal position having a foreign VAT can access the settings
        """
        company_us = self.env['res.company'].create({
            'name': 'Test US Main',
            'country_id': self.env.ref('base.us').id,
        })

        self.env['account.fiscal.position'].create({
            'name': 'Test Fiscal Position BE',
            'company_id': company_us.id,
            'auto_apply': True,
            'foreign_vat': 'BE0980737405',
            'country_id': self.env.ref('base.be').id,
        })

        self.assertIn(self.env.ref('base.be'), company_us.account_enabled_tax_country_ids)
        self.assertRecordValues(company_us, [
            {'name': 'Test US Main', 'l10n_be_intervat_show_settings': True},
        ])
