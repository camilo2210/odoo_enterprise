# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import HttpCase, tagged, new_test_user


@tagged('-at_install', 'post_install', 'post_install_l10n', 'is_tour')
class TestEmployeeUi(HttpCase):

    def test_create_employee_with_hr_rights(self):
        belgian_company = self.env['res.company'].create({
            'name': 'My BE Company',
            'country_id': self.env.ref('base.be').id,
        })
        new_test_user(self.env, login='hr_user', groups='hr.group_hr_user', company_id=belgian_company.id)
        self.start_tour('/odoo', 'hr_officer_create_employee_tour', login='hr_user')

        emp = self.env['hr.employee'].search([('name', 'ilike', 'My Employee')])
        self.assertTrue(emp)
