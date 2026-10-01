# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_hk = self.env['res.company'].create({
            'name': 'HK Co',
            'country_id': self.env.ref('base.hk').id,
        })
        self.employee_hk = self.env['hr.employee'].create({
            'name': 'HK Employee',
            'company_id': self.company_hk.id,
        })

    def test_hk_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_hk)

        template = Version.create({
            'name': 'HK Template',
            'l10n_hk_internet': 500.0,
        })

        contract = self.employee_hk.version_id

        self.employee_hk.contract_template_id = template
        self.employee_hk._onchange_contract_template_id()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
