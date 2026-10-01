# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon


class TestPayslipBase(TestBelgiumCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.country_id = cls.env.ref('base.be')
        cls.employee = cls.env['hr.employee'].create({
            'name': 'employee',
            'date_version': '2019-01-01',
            'contract_date_start': '2019-01-01',
        })
        cls.version = cls.employee.version_id

    def check_payslip(self, name, payslip, values):
        for code, value in values.items():
            self.assertAlmostEqual(payslip.line_ids.filtered(lambda line: line.code == code).total, value)

    def update_version(self, date_start, date_end=False, wage=2500):
        self.version.write({
            'wage': wage,
            'employee_id': self.employee.id,
            'contract_date_start': date_start,
            'contract_date_end': date_end,
            'date_version': date_start,
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'internet': False,
            'mobile': False,
        })
        return self.version

    def create_version(self, date_start, date_end=False, wage=2500):
        return self.employee.create_version({
            'wage': wage,
            'contract_date_start': date_start,
            'contract_date_end': date_end,
            'date_version': date_start,
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'internet': False,
            'mobile': False,
        })

    @classmethod
    def create_payslip(cls, structure, date_start, date_end=False):
        return cls.env['hr.payslip'].create({
            'name': '%s for %s' % (structure, cls.employee),
            'employee_id': cls.employee.id,
            'date_from': date_start,
            'date_to': date_end,
            'struct_id': structure.id,
            'version_id': cls.version.id,
        })

    def test_payslip_with_concurrent_versions(self):
        """ Ensure that only one version appears of the concurrent versions for a payslip. """
        self.employee.country_id = self.env.ref('base.be')
        self.version.contract_date_end = '2023-01-31'

        version_1 = self.create_version(date_start='2023-03-01', date_end='2023-03-15')
        version_2 = version_1.copy({
            'date_version': '2023-03-02',
            'contract_date_start': '2023-03-16',
            'contract_date_end': '2023-03-31',
        })

        payslip_vals = {
            'name': f'Payslip for {self.employee.name}',
            'employee_id': self.employee.id,
            'date_from': '2023-03-01',
            'date_to': '2023-03-31',
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
        }

        payslip_1 = self.env['hr.payslip'].create(payslip_vals)
        working_days = payslip_1.worked_days_line_ids.filtered(lambda line: line.code == '002.00')
        self.assertEqual(working_days.mapped('version_id'), version_1 | version_2)
        self.assertEqual(payslip_1.version_id, version_1)
        self.assertEqual(payslip_1.allowed_version_ids, version_1)

        version_2.l10n_be_dimona_category = 'stu'

        payslip_2 = self.env['hr.payslip'].create(payslip_vals)
        working_days = payslip_2.worked_days_line_ids.filtered(lambda line: line.code == '002.00')
        self.assertEqual(len(working_days.mapped('version_id')), 1)
        self.assertEqual(payslip_2.allowed_version_ids, version_1 | version_2)
