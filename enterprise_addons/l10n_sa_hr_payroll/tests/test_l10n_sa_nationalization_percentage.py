# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from odoo.tests.common import tagged
from .common import TestSACommon


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestL10nSaNationalizationPercentage(TestSACommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.country_sa = cls.env.ref('base.sa')
        cls.country_eg = cls.env.ref('base.eg')

        cls.sa_company_1 = cls.env['res.company'].create({
            'name': 'Saudi Arabia Company 1',
            'country_id': cls.country_sa.id,
        })

        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.sa_company_1.ids))

        cls.dept_acc = cls.env['hr.department'].create({
            'name': 'Acc',
            'l10n_sa_saudization_minimum_wage': 4000,
            'company_id': cls.sa_company_1.id
        })
        cls.dept_eng = cls.env['hr.department'].create({
            'name': 'Eng',
            'l10n_sa_saudization_minimum_wage': 6000,
            'company_id': cls.sa_company_1.id
        })

        cls.employees = cls.env['hr.employee'].create([
            {
                'name': 'emp_sa_1',
                'country_id': cls.country_sa.id,
                'department_id': cls.dept_acc.id,
                'wage': 4500,
                'contract_date_start': date(2025, 1, 1),
                'company_id': cls.sa_company_1.id,
            },
            {
                'name': 'emp_sa_2',
                'country_id': cls.country_sa.id,
                'department_id': cls.dept_acc.id,
                'wage': 6000,
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': date(2025, 12, 31),
                'company_id': cls.sa_company_1.id,
            },
            {
                'name': 'emp_sa_3',
                'country_id': cls.country_sa.id,
                'department_id': cls.dept_acc.id,
                'wage': 6000,
                'contract_date_start': date(2024, 1, 1),
                'contract_date_end': date(2024, 12, 31),
                'company_id': cls.sa_company_1.id,
            },
            {
                'name': 'emp_sa_4',
                'country_id': cls.country_sa.id,
                'department_id': cls.dept_acc.id,
                'wage': 6000,
                'contract_date_start': date(2025, 8, 1),
                'company_id': cls.sa_company_1.id,
            },
            {
                'name': 'emp_sa_5',
                'country_id': cls.country_sa.id,
                'department_id': cls.dept_eng.id,
                'wage': 4500,
                'contract_date_start': date(2025, 1, 1),
                'company_id': cls.sa_company_1.id,
            },
            {
                'name': 'emp_sa_6',
                'country_id': cls.country_sa.id,
                'department_id': cls.dept_eng.id,
                'wage': 5000,
                'contract_date_start': date(2025, 1, 1),
                'company_id': cls.sa_company_1.id,
            },
            {
                'name': 'emp_eg_1',
                'country_id': cls.country_eg.id,
                'department_id': cls.dept_acc.id,
                'wage': 5000,
                'contract_date_start': date(2025, 1, 1),
                'company_id': cls.sa_company_1.id,
            },
            {
                'name': 'emp_eg_2',
                'country_id': cls.country_eg.id,
                'department_id': cls.dept_eng.id,
                'wage': 3500,
                'contract_date_start': date(2025, 1, 1),
                'company_id': cls.sa_company_1.id,
            },
        ])

    def test_compute_rate_single_department(self):
        report = self.env['l10n.sa.nationalization.percentage'].create({
            'date': date(2025, 6, 1),
            'company_id': self.sa_company_1.id,
            'department_ids': [(6, 0, self.dept_acc.ids)],
        })
        report.action_compute_rate()
        self.assertAlmostEqual(report.saudization_rate, 2 / 3)

    def test_compute_rate_multiple_departments(self):
        report = self.env['l10n.sa.nationalization.percentage'].create({
            'date': date(2025, 6, 1),
            'company_id': self.sa_company_1.id,
            'department_ids': [(6, 0, [self.dept_acc.id, self.dept_eng.id])],
        })
        report.action_compute_rate()
        self.assertAlmostEqual(report.saudization_rate, 2 / 6)

    def test_compute_rate_company_wide(self):
        report = self.env['l10n.sa.nationalization.percentage'].create({
            'date': date(2025, 6, 1),
            'company_id': self.sa_company_1.id,
        })
        report.action_compute_rate()
        self.assertAlmostEqual(report.saudization_rate, 2 / 6)

    def test_excluded_employee_is_ignored_in_rate(self):
        report = self.env['l10n.sa.nationalization.percentage'].create({
            'date': date(2025, 6, 1),
            'company_id': self.sa_company_1.id,
            'excluded_employee_domain': "[('name', '=', 'emp_sa_1')]"
        })
        report.action_compute_rate()
        self.assertAlmostEqual(report.saudization_rate, 1 / 6)

    def test_employee_version_change_affects_rate(self):
        report_2025 = self.env['l10n.sa.nationalization.percentage'].create({
            'date': date(2025, 12, 15),
            'company_id': self.sa_company_1.id,
        })
        report_2025.action_compute_rate()
        self.assertAlmostEqual(report_2025.saudization_rate, 3 / 7)

        emp_sa_2 = self.employees[1]
        self.env['hr.version'].create({
            'employee_id': emp_sa_2.id,
            'department_id': self.dept_acc.id,
            'country_id': self.country_sa.id,
            'wage': 7000,
            'contract_date_start': date(2026, 1, 1),
            'company_id': self.sa_company_1.id
        })

        report_2026 = self.env['l10n.sa.nationalization.percentage'].create({
            'date': date(2026, 1, 15),
            'company_id': self.sa_company_1.id,
        })
        report_2026.action_compute_rate()
        self.assertAlmostEqual(report_2026.saudization_rate, 3 / 7)

    def test_compute_rate_no_employees(self):
        report = self.env['l10n.sa.nationalization.percentage'].create({
            'date': date(2020, 1, 1),
            'company_id': self.sa_company_1.id,
        })
        report.action_compute_rate()
        self.assertEqual(report.saudization_rate, 0.0)
