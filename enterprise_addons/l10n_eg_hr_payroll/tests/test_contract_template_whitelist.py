# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestWhitelistFromTemplate(TestPayrollCommon):

    def test_eg_contract_template_loading(self):
        Version = self.env['hr.version']

        template = Version.create({
            'name': 'EG Template',
            'l10n_eg_social_insurance_reference': 4000.0,
        })

        contract = self.employee.version_id

        self.assertEqual(contract.l10n_eg_social_insurance_reference, 0.0)

        self.employee.contract_template_id = template
        self.employee._onchange_contract_template_id()

        for field in Version._get_whitelist_fields_from_template():
            self.assertEqual(contract[field], template[field])
