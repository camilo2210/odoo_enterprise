# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase
from odoo.tests import tagged, HttpCase
from odoo.fields import Date

from datetime import datetime
from dateutil.relativedelta import relativedelta


@tagged('post_install', '-at_install')
class TestPayrunSearch(TestPayslipContractBase, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Test Structure Type',
            'country_id': cls.env.ref('base.us').id
        })
        structure = cls.env['hr.payroll.structure'].create({
            'name': 'Test Regular Pay',
            'type_id': structure_type.id,
        })
        cls.faruk_emp = cls.env['hr.employee'].create({
            'name': 'Faruk',
            'sex': 'male',
            'birthday': '2000-05-01',
            'country_id': cls.env.ref('base.us').id,
            'contract_date_start': Date.to_date('2018-01-01'),
            'wage': 4000,
            'contract_date_end': Date.today() + relativedelta(years=2),
            'department_id': cls.dep_rd.id,
            'structure_type_id': structure.type_id.id,
        })

        # Contract for Faruk
        cls.faruk_emp.version_id.sudo().write({
            'contract_date_start': datetime.strptime('2015-01-01', '%Y-%m-%d'),
            'contract_date_end': False,
            'date_version': datetime.strptime('2015-01-01', '%Y-%m-%d'),
            'name': 'Contract for Faruk',
            'resource_calendar_id': cls.calendar_40h.id,
            'wage': 4000,
            'employee_id': cls.faruk_emp.id,
            'structure_type_id': structure.type_id.id,
        })
        cls.contract_faruk = cls.faruk_emp.version_id

    def test_payrun_search(self):
        self.user_admin = self.env.ref('base.user_admin')
        self.user_admin.company_ids |= self.company_us
        self.user_admin.write({
            'company_id': self.env.company.id,
            'email': 'mitchell.admin@example.com',
        })
        self.skipTest("TODO RAAME: Reintroduce this test, freeze skipping")
        self.start_tour("/odoo", 'payroll_payrun_search_tour', login="admin")
