from datetime import date
from odoo.tests import tagged
from freezegun import freeze_time
from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestPayrollEcoVouchers(TestPayrollCommon):

    def _validate_impulsion_payslip_lines(self, payslips, expected_amounts):
        impulsion_codes = ['IMPULSION25', 'IMPULSION12']
        payslips_by_employee_month = {
            (payslip.employee_id, payslip.date_from.month): payslip
            for payslip in payslips
        }
        for employee, expected_by_month in expected_amounts.items():
            for month, expected_values in expected_by_month.items():
                payslip = payslips_by_employee_month.get((employee, month))
                if not payslip:
                    self.assertFalse(
                        any(expected_values.values()),
                        '%s has no payslip for month %s, but expected impulsion values: %s' % (employee.name, month, expected_values),
                    )
                    continue
                line_values = payslip._get_line_values(impulsion_codes, compute_sum=True)
                for code in impulsion_codes:
                    self.assertAlmostEqual(
                        line_values[code]['sum']['total'], expected_values.get(code, 0.0), places=2,
                        msg='%s: unexpected %s amount for month %s' % (employee.name, code, month),
                    )

    @freeze_time("2026-04-10 10:00:00")
    def test_impulsion_deductions(self):
        employees = self.env['hr.employee'].create([{
            'name': name,
            'birthday': birthday,
            'country_id': self.env.ref('base.be').id,
            'company_id': self.belgian_company.id,
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'contract_date_start': date(2025, 1, 1),
            'date_version': date(2025, 1, 1),
            'wage': 3000.0,
            'l10n_be_impulsion_plan': impulsion_plan,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
        } for i, (name, impulsion_plan, birthday) in enumerate([
            ('Employee without Impulsion Plan', False, date(1995, 1, 1)),
            ('Employee with Impulsion 25yo', '25yo', date(2002, 1, 1)),
            ('Employee with Impulsion 12mo', '12mo', date(1995, 1, 1)),
        ])])

        # unpaid leave - should affect the impulsion amount in March
        self.env['hr.leave'].create([{
            'employee_id': employee.id,
            'request_date_from': date(2026, 3, 17),
            'request_date_to': date(2026, 3, 21),
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave').id,
        } for employee in employees])

        payslips = self.env['hr.payslip'].create([{
            'name': f'Payslip {month:02d}/2026 {employee.name}',
            'version_id': employee.version_id.id,
            'date_from': date(2026, month, 1),
            'date_to': date(2026, month, 31 if month in (1, 3) else 28),
            'employee_id': employee.id,
            'company_id': self.belgian_company.id,
        }
            for month in (1, 2, 3) for employee in employees
        ])

        for payslip in payslips:
            payslip.compute_sheet()
            payslip.action_payslip_done()

        expected_amounts = {
            employees[0]: {  # without Impulsion Plan
                1: {},
                2: {},
                3: {},
            },
            employees[1]: {  # Impulsion 25yo
                1: {'IMPULSION25': -500.0},
                2: {'IMPULSION25': -500.0},
                3: {'IMPULSION25': -409.09},
            },
            employees[2]: {  # Impulsion 12mo
                1: {'IMPULSION12': -250.0},
                2: {'IMPULSION12': -250.0},
                3: {'IMPULSION12': -204.55},
            },
        }
        self._validate_impulsion_payslip_lines(payslips, expected_amounts)
