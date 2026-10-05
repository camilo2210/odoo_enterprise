# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from freezegun import freeze_time

from odoo.tests import common, tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestHrEmployee(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_worked_years(self):
        employee_1 = self.env['hr.employee'].create({
            'name': 'Test Employee 1',
            'contract_date_start': date(2023, 2, 15),
            'date_version': date(2023, 2, 15),
            'wage': 15_000.0,
        })

        with freeze_time('2025-2-15'):
            departure_notice_1 = self.env['hr.employee.departure'].create({
                'employee_id':  employee_1.id,
                'dismissal_date': date(2025, 2, 14),
                'departure_description': 'foo',
            })
            departure_notice_1.action_register()

        self.assertAlmostEqual(employee_1._l10n_ae_get_worked_years(), 2, 2, "This employee has worked for 2 years")
