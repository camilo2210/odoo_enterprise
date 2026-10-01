# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo.addons.hr_payroll.tests.common import TestPayslipBase
from odoo.tests.common import users, warmup, tagged


@tagged('payslip_perf')
@tagged('at_install', '-post_install')  # LEGACY at_install
class TestPayrollPerformance(TestPayslipBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.jack = cls.env['hr.employee'].create({'name': 'Jack'})
        cls.employees = cls.richard_emp | cls.jack
        cls.user_admin = cls.env.ref('base.user_admin')
        cls.user_admin.company_ids |= cls.company_us

        cls.employees.write({
            'date_version': date(2018, 1, 1),
            'contract_date_start': date(2018, 1, 1),
            'contract_date_end': date(2018, 2, 1),
            'name': 'Test Contract',
            'wage': 5000.0,
            'structure_type_id': cls.structure_type.id,
        })

    @users('__system__', 'admin')
    @warmup
    def test_performance_work_entry_generation(self):
        """ Work entry generation """
        with self.assertQueryCount(__system__=22, admin=23):
            self.employees.generate_work_entries(date(2018, 1, 1), date(2018, 1, 2))

    @users('__system__', 'admin')
    @warmup
    def test_rule_parameter_cache(self):
        parameter = self.env['hr.rule.parameter'].create({
            'name': 'Test parameter',
            'code': 'test_parameter_cache',
        })
        self.env['hr.rule.parameter.value'].create({
            'rule_parameter_id': parameter.id,
            'date_from': date(2015, 10, 10),
            'parameter_value': 3
        })
        with self.assertQueryCount(__system__=1, admin=4):
            self.env['hr.rule.parameter']._get_parameter_from_code('test_parameter_cache')
        parameter.active = False
