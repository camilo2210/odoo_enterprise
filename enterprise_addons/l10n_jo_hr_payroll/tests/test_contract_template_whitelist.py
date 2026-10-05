# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_jo = self.env['res.company'].create({
            'name': 'JO Co',
            'country_id': self.env.ref('base.jo').id,
        })
        self.employee_jo = self.env['hr.employee'].create({
            'name': 'JO Employee',
            'company_id': self.company_jo.id,
        })

    def test_jo_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_jo)

        template = Version.create({
            'name': 'JO Template',
            'l10n_jo_housing_allowance': 2000.0,
            'l10n_jo_transportation_allowance': 500.0,
            'l10n_jo_other_allowances': 800.0,
        })

        contract = self.employee_jo.version_id

        self.assertEqual(contract.l10n_jo_housing_allowance, 0.0)
        self.assertEqual(contract.l10n_jo_transportation_allowance, 0.0)
        self.assertEqual(contract.l10n_jo_other_allowances, 0.0)

        self.employee_jo.contract_template_id = template
        self.employee_jo._onchange_contract_template_id()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
