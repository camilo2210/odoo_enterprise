# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company_id = self.env['res.company'].create({
            'name': 'ZA Co',
            'country_id': self.env.ref('base.za').id,
        })
        self.employee_id = self.env['hr.employee'].create({
            'name': 'ZA Employee',
            'company_id': self.company_id.id,
        })

    def test_za_contract_template_loading(self):
        Version = self.env['hr.version'].with_company(self.company_id)

        template = Version.create({
            'name': 'ZA Template',
            'l10n_za_employee_medical_scheme_contribution': 100.0,
            'l10n_za_employee_dependant_count': 2,
            'l10n_za_dependant_medical_scheme_contribution': 50.0,
        })

        contract = self.employee_id.version_id

        self.employee_id.contract_template_id = template
        self.employee_id._onchange_contract_template_id()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
