# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.hr_payroll.tests.common import TestPayrollBase


class TestPayrollCommon(TestPayrollBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write({
            'country_id': cls.env.ref('base.eg').id,
            'currency_id': cls.env.ref('base.EGP').id,
        })
        cls.company = cls.env.company
        cls._setup_common(
            country=cls.env.ref('base.eg'),
            structure=cls.env.ref('l10n_eg_hr_payroll.hr_payroll_structure_eg_employee_salary'),
            structure_type=cls.env.ref('l10n_eg_hr_payroll.structure_type_employee_eg'),
        )
