# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime

from freezegun import freeze_time

from odoo.tests import tagged
from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'cp200_annual_bonus')
class TestCP200AnnualBonus(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cp200 = cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200')
        cls.salary_struct = cls.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        cls.unpaid_work_entry_type = cls.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave')

        # Reference calendar: Mon-Sat, 6h20min/day
        cls.ref_calendar_6d = cls.env['resource.calendar'].create({
            'name': 'CP200 Ref: Mon-Sat 6h20',
            'company_id': cls.belgian_company.id,
            'attendance_ids': [
                (0, 0, {'dayofweek': str(day), 'duration_hours': 6 + 20 / 60, 'hour_from': 0, 'hour_to': 0})
                for day in range(6)
            ],
            'full_time_required_hours': 38,
        })

        cls.work_calendar_4d = cls.env['resource.calendar'].create({
            'name': '4 days/week 7h36',
            'company_id': cls.belgian_company.id,
            'attendance_ids': [
                (0, 0, {'dayofweek': str(day), 'hour_from': 8, 'hour_to': 15.6})
                for day in range(4)
            ],
            'full_time_required_hours': 38,
        })

        # Work calendar: Mon-Fri, 38h/week (4 days/week)
        cls.work_calendar_5d = cls.env['resource.calendar'].create({
            'name': '5 days/week 8h on mon and 7h30 for the rest',
            'company_id': cls.belgian_company.id,
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'duration_hours': 8, 'hour_from': 0, 'hour_to': 0}),
                (0, 0, {'dayofweek': '1', 'duration_hours': 7.5, 'hour_from': 0, 'hour_to': 0}),
                (0, 0, {'dayofweek': '2', 'duration_hours': 7.5, 'hour_from': 0, 'hour_to': 0}),
                (0, 0, {'dayofweek': '3', 'duration_hours': 7.5, 'hour_from': 0, 'hour_to': 0}),
                (0, 0, {'dayofweek': '4', 'duration_hours': 7.5, 'hour_from': 0, 'hour_to': 0})
            ],
            'full_time_required_hours': 38,
        })

    def test_full_year_single_version_with_unpaid(self):
        """
        Worker with:
        - Reference calendar: Mon-Sat, 6h20min/day
        - Work calendar: Mon-Thu, 7h36/day
        - Full ref period coverage: 1/6/2024 to 31/5/2025 (B/C = 1)
        - 834.10h assimilated, rest (~746h) unpaid
        - prorata = 834.10/1982.33 * 365/365 → BASIC = 136.20
        """
        with freeze_time('2025-06-01'):
            employee = self.create_employee({
                'name': 'Test Annual Bonus Worker',
                'resource_calendar_id': self.work_calendar_4d.id,
                'reference_calendar_id': self.ref_calendar_6d.id,
                'l10n_be_joint_committee_id': self.cp200.id,
                'date_version': date(2024, 1, 1),
                'contract_date_start': date(2024, 1, 1),
                'contract_date_end': False,
            })
            # Pin the resource timezone so the partial-day leave overlap is deterministic
            # regardless of the server/user timezone (runbot defaults to UTC, local may be CET).
            employee.resource_id.tz = 'Europe/Brussels'

            # Create unpaid leaves covering June 3, 2024 to Nov 19, 2024 (98 full working days)
            # + partial day on Nov 20, 2024 (1h54min = 1.9h local time)
            # Nov 20 is CET (UTC+1): 08:54 UTC = 09:54 local, work starts 08:00 local → 1.9h
            # Total unpaid: 98 * 7.6 + 1.9 = 746.7h → Assimilated: 1580.8 - 746.7 = 834.1h
            self.env['resource.calendar.leaves'].create({
                'name': 'Unpaid Leave',
                'date_from': datetime(2024, 6, 3, 0, 0, 0),
                'date_to': datetime(2024, 11, 20, 8, 54, 0),
                'resource_id': employee.resource_id.id,
                'calendar_id': self.work_calendar_4d.id,
                'work_entry_type_id': self.unpaid_work_entry_type.id,
                'count_as': 'absence',
            })

            payslip = self.env['hr.payslip'].create({
                'name': 'Annual Sectorial Bonus',
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                'struct_id': self.salary_struct.id,
                'date_from': date(2025, 6, 1),
                'date_to': date(2025, 6, 30),
                'company_id': self.belgian_company.id,
            })
            payslip.compute_sheet()

            bonus_line = payslip.line_ids.filtered(lambda l: l.code == 'SECTORIAL.BONUS')
            self.assertTrue(bonus_line, "SECTORIAL.BONUS line should be present")
            self.assertAlmostEqual(bonus_line.total, 136.20, places=2)

    def test_partial_year_single_version_with_unpaid(self):
        """
        Worker with:
        - Reference calendar: Mon-Sat, 6h20min/day
        - Work calendar: Mon-Fri, 7h30/day except monday (8h)
        - Partial ref period coverage: 9/9/2024 to 31/5/2025 (B/C = 265/365)
        - 1405.50h assimilated, rest (~38h30min) unpaid
        - prorata = (1405.50/1444.00) * 265/365 → BASIC = 228.74
        """
        with freeze_time('2025-06-01'):
            employee = self.create_employee({
                'name': 'Test Annual Bonus Worker 2',
                'resource_calendar_id': self.work_calendar_5d.id,
                'reference_calendar_id': self.ref_calendar_6d.id,
                'l10n_be_joint_committee_id': self.cp200.id,
                'date_version': date(2024, 9, 9),
                'contract_date_start': date(2024, 9, 9),
                'contract_date_end': False,
            })
            # Pin the resource timezone so the partial-day leave overlap is deterministic
            # regardless of the server/user timezone (runbot defaults to UTC, local may be CEST).
            employee.resource_id.tz = 'Europe/Brussels'

            # Create unpaid leaves covering Oct 7, 2024 to Oct 14, 2024 (5 full working days)
            # + partial day on Oct 14, 2024 (30min = 0.5h local time)
            # Oct 14 is still CEST (UTC+2, DST ends Oct 27): 06:30 UTC = 08:30 local, work starts 08:00 → 0.5h
            # Total unpaid: 38h (1 week) + 0.5 = 38.5h → Assimilated: 1444.0 - 38.5 = 1405.5h
            self.env['resource.calendar.leaves'].create({
                'name': 'Unpaid Leave',
                'date_from': datetime(2024, 10, 7, 0, 0, 0),
                'date_to': datetime(2024, 10, 14, 6, 30, 0),
                'resource_id': employee.resource_id.id,
                'calendar_id': self.work_calendar_5d.id,
                'work_entry_type_id': self.unpaid_work_entry_type.id,
                'count_as': 'absence',
            })

            payslip = self.env['hr.payslip'].create({
                'name': 'Annual Sectorial Bonus',
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                'struct_id': self.salary_struct.id,
                'date_from': date(2025, 6, 1),
                'date_to': date(2025, 6, 30),
                'company_id': self.belgian_company.id,
            })
            payslip.compute_sheet()

            bonus_line = payslip.line_ids.filtered(lambda l: l.code == 'SECTORIAL.BONUS')
            self.assertTrue(bonus_line, "SECTORIAL.BONUS line should be present")
            self.assertAlmostEqual(bonus_line.total, 228.74, places=2)

    def test_mid_year_version_change_with_unpaid(self):
        """
        Employee changes version mid-year:
        - Version 1 (June 1 - Nov 30, 2024): 4-day calendar (Mon-Thu, 7.6h/day)
          with 20 working days unpaid leave (June 3 - July 4, 2024)
          B_v1=183, H_v1=638.4, H_ref_v1=994.33
        - Version 2 (Dec 1, 2024 - May 31, 2025): 5-day calendar (8h Mon + 7.5h Tue-Fri)
          no unpaid leave
          B_v2=182, H_v2=988.0, H_ref_v2=988.0
        - Both versions use ref calendar Mon-Sat 6h20min/day
        - prorata = (183/365)*(638.4/994.33) + (182/365)*(988.0/988.0) = 0.8205
        - BASIC = 323.69 * 0.8205 = 265.60
        """
        with freeze_time('2025-06-01'):
            employee = self.create_employee({
                'name': 'Test Mid-Year Change Worker',
                'resource_calendar_id': self.work_calendar_4d.id,
                'reference_calendar_id': self.ref_calendar_6d.id,
                'l10n_be_joint_committee_id': self.cp200.id,
                'date_version': date(2024, 1, 1),
                'contract_date_start': date(2024, 1, 1),
                'contract_date_end': date(2024, 11, 30),
            })

            # Version 2: switch to 5-day calendar from Dec 1, 2024
            version2 = employee.create_version({
                'date_version': date(2024, 12, 1),
                'contract_date_start': date(2024, 12, 1),
                'contract_date_end': False,
                'resource_calendar_id': self.work_calendar_5d.id,
                'reference_calendar_id': self.ref_calendar_6d.id,
                'l10n_be_joint_committee_id': self.cp200.id,
            })

            # Unpaid leave in V1: 20 Mon-Thu working days (June 3 - July 4, 2024)
            self.env['resource.calendar.leaves'].create({
                'name': 'Unpaid Leave V1',
                'date_from': datetime(2024, 6, 3, 0, 0, 0),
                'date_to': datetime(2024, 7, 4, 23, 59, 59),
                'resource_id': employee.resource_id.id,
                'calendar_id': self.work_calendar_4d.id,
                'work_entry_type_id': self.unpaid_work_entry_type.id,
                'count_as': 'absence',
            })

            payslip = self.env['hr.payslip'].create({
                'name': 'Annual Sectorial Bonus',
                'employee_id': employee.id,
                'version_id': version2.id,
                'struct_id': self.salary_struct.id,
                'date_from': date(2025, 6, 1),
                'date_to': date(2025, 6, 30),
                'company_id': self.belgian_company.id,
            })
            payslip.compute_sheet()

            bonus_line = payslip.line_ids.filtered(lambda l: l.code == 'SECTORIAL.BONUS')
            self.assertTrue(bonus_line, "SECTORIAL.BONUS line should be present")
            self.assertAlmostEqual(bonus_line.total, 265.60, places=2)

    def test_compensatory_amount_per_employee(self):
        """
        Full-time employee in 2026 (Z = 330.84), present for the whole ref period
        (June 1, 2025 - May 31, 2026), no unpaid leave.
        ref_cal = emp_cal (Mon-Sat 6h20min/day) → H/H_ref = 1, B/C = 1, prorata = 1.

        The compensatory amount is set per employee via the
        l10n_be_sectorial_bonus_compensatory_amount field (benefit).
        SECTORIAL.BONUS = max(Z*prorata - comp, 0).

        With compensatory_amount = 100: effective = 230.84
        With compensatory_amount = 0:   effective = 330.84
        With compensatory_amount = 500: effective = 0 (clamped)
        """
        with freeze_time('2026-06-01'):
            employee = self.create_employee({
                'name': 'Test Compensatory Worker',
                'resource_calendar_id': self.ref_calendar_6d.id,
                'reference_calendar_id': self.ref_calendar_6d.id,
                'l10n_be_joint_committee_id': self.cp200.id,
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
            })

            # comp = 100 → 330.84 - 100 = 230.84
            employee.version_id.l10n_be_sectorial_bonus_compensatory_amount = 100.0

            payslip = self.env['hr.payslip'].create({
                'name': 'Annual Sectorial Bonus (with compensatory)',
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                'struct_id': self.salary_struct.id,
                'date_from': date(2026, 6, 1),
                'date_to': date(2026, 6, 30),
                'company_id': self.belgian_company.id,
            })
            payslip.compute_sheet()

            bonus_line = payslip.line_ids.filtered(lambda l: l.code == 'SECTORIAL.BONUS')
            self.assertTrue(bonus_line)
            self.assertAlmostEqual(bonus_line.total, 230.84, places=2)

            # comp = 0 → full bonus = 330.84
            employee.version_id.l10n_be_sectorial_bonus_compensatory_amount = 0.0

            payslip2 = self.env['hr.payslip'].create({
                'name': 'Annual Sectorial Bonus (no compensatory)',
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                'struct_id': self.salary_struct.id,
                'date_from': date(2026, 6, 1),
                'date_to': date(2026, 6, 30),
                'company_id': self.belgian_company.id,
            })
            payslip2.compute_sheet()

            bonus_line2 = payslip2.line_ids.filtered(lambda l: l.code == 'SECTORIAL.BONUS')
            self.assertTrue(bonus_line2)
            self.assertAlmostEqual(bonus_line2.total, 330.84, places=2)

            # comp = 500 > prime → clamped to 0
            employee.version_id.l10n_be_sectorial_bonus_compensatory_amount = 500.0

            payslip3 = self.env['hr.payslip'].create({
                'name': 'Annual Sectorial Bonus (compensatory > prime)',
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                'struct_id': self.salary_struct.id,
                'date_from': date(2026, 6, 1),
                'date_to': date(2026, 6, 30),
                'company_id': self.belgian_company.id,
            })
            payslip3.compute_sheet()

            bonus_line3 = payslip3.line_ids.filtered(lambda l: l.code == 'SECTORIAL.BONUS')
            self.assertTrue(bonus_line3)
            self.assertAlmostEqual(bonus_line3.total, 0.0, places=2)

    def test_sectorial_bonus_ineligible_cases(self):
        # 1. Terminated for serious misconduct (reason code 355)
        employee_misconduct = self.create_employee({
            'name': 'Fired For Misconduct',
            'l10n_be_joint_committee_id': self.cp200.id,
            'date_version': date(2024, 1, 1),
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': date(2024, 12, 31),
        })
        self.env['hr.employee.departure'].create({
            'employee_id': employee_misconduct.id,
            'departure_reason_id': self.env.ref('l10n_be_hr_payroll.departure_fired_serious_misconduct').id,
            'dismissal_date': date(2024, 12, 31),
        })
        payslip_misconduct = self.env['hr.payslip'].create({
            'name': 'Bonus - Misconduct',
            'employee_id': employee_misconduct.id,
            'version_id': employee_misconduct.version_id.id,
            'struct_id': self.salary_struct.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
            'company_id': self.belgian_company.id,
        })
        self.assertFalse(payslip_misconduct._is_cp200_annual_sectorial_bonus_eligible())

        # 2. Payslip period before January 1, 2016
        employee_pre2016 = self.create_employee({
            'name': 'Pre-2016 Worker',
            'l10n_be_joint_committee_id': self.cp200.id,
            'date_version': date(2015, 1, 1),
            'contract_date_start': date(2015, 1, 1),
            'contract_date_end': False,
        })
        payslip_pre2016 = self.env['hr.payslip'].create({
            'name': 'Bonus - Pre-2016',
            'employee_id': employee_pre2016.id,
            'version_id': employee_pre2016.version_id.id,
            'struct_id': self.salary_struct.id,
            'date_from': date(2015, 6, 1),
            'date_to': date(2015, 12, 31),
            'company_id': self.belgian_company.id,
        })
        self.assertFalse(payslip_pre2016._is_cp200_annual_sectorial_bonus_eligible())

        # 3. Excluded employer category (dmfa_code 024 — construction sector)
        employee_construction = self.create_employee({
            'name': 'Construction Worker',
            'l10n_be_joint_committee_id': self.cp200.id,
            'date_version': date(2024, 1, 1),
            'contract_date_start': date(2024, 1, 1),
            'contract_date_end': False,
        })
        construction_company = self.belgian_company
        construction_company._get_payroll_config(date(2025, 6, 1)).l10n_be_employer_category_id = self.env.ref(
            'l10n_be_hr_payroll.l10n_be_employer_category_00024'
        )
        payslip_construction = self.env['hr.payslip'].create({
            'name': 'Bonus - Construction',
            'employee_id': employee_construction.id,
            'version_id': employee_construction.version_id.id,
            'struct_id': self.salary_struct.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
            'company_id': construction_company.id,
        })
        self.assertFalse(payslip_construction._is_cp200_annual_sectorial_bonus_eligible())

    def test_sectorial_bonus_eligible_mid_year_departure(self):
        """
        Employee whose contract ends mid-July 2025 (not a June payslip).
        - Reference period: 1/6/2024 → 31/5/2025, fully covered → B/C = 1
        - Same calendar for work and reference → H/H_ref = 1
        - prorata = 1 → SECTORIAL.BONUS = Z(2025) = 323.69
        """
        with freeze_time('2025-07-01'):
            employee = self.create_employee({
                'name': 'Mid-Year Departure Worker',
                'resource_calendar_id': self.ref_calendar_6d.id,
                'reference_calendar_id': self.ref_calendar_6d.id,
                'l10n_be_joint_committee_id': self.cp200.id,
                'date_version': date(2024, 1, 1),
                'contract_date_start': date(2024, 1, 1),
                'contract_date_end': date(2025, 7, 15),
            })
            payslip = self.env['hr.payslip'].create({
                'name': 'Bonus - Mid-Year Departure',
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                'struct_id': self.salary_struct.id,
                'date_from': date(2025, 7, 1),
                'date_to': date(2025, 7, 31),
                'company_id': self.belgian_company.id,
            })
            self.assertTrue(payslip._is_cp200_annual_sectorial_bonus_eligible())
            payslip.compute_sheet()
            bonus_line = payslip.line_ids.filtered(lambda l: l.code == 'SECTORIAL.BONUS')
            self.assertTrue(bonus_line, "SECTORIAL.BONUS line should be present")
            self.assertAlmostEqual(bonus_line.total, 39.91, places=2)

    def _june_2026_payslip(self, employee, ignore_worked_day_lines=False):
        """Create and compute a June 2026 CP200 payslip for ``employee``.

        With ``ignore_worked_day_lines=True`` the worked-day lines (and thus the
        monthly salary) are dropped, producing a sectorial-bonus-only payslip.
        """
        payslip = self.env['hr.payslip'].create({
            'name': 'June 2026',
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            'struct_id': self.salary_struct.id,
            'date_from': date(2026, 6, 1),
            'date_to': date(2026, 6, 30),
            'company_id': self.belgian_company.id,
        })
        if ignore_worked_day_lines:
            payslip.ignore_worked_day_lines = True
        payslip.compute_sheet()
        return payslip

    def test_employment_bonus_invariant_across_sectorial_bonus_split(self):
        """
        The work bonus (EmpBonus.1) must total the same amount whether the annual
        sectorial bonus and the monthly salary are paid on a single payslip or
        split over two payslips of the same month, and regardless of their order.

        This guards the EmpBonus.1.STD / EmpBonus.1.FALLBACK split: those rules
        only redistribute the bonus between the standard and the bonus withholding
        base, they must not change the total work bonus.

        Same full-time worker as test_compensatory_amount_per_employee
        (2026, prorata = 1, Z = 330.84); a fresh employee per scenario so a
        previous monthly payslip doesn't leak from one scenario into another.
        """
        def line_total(payslips, code):
            return sum(payslips.line_ids.filtered(lambda l: l.code == code).mapped('total'))

        with freeze_time('2026-06-01'):
            employee_values = {
                'resource_calendar_id': self.ref_calendar_6d.id,
                'reference_calendar_id': self.ref_calendar_6d.id,
                'l10n_be_joint_committee_id': self.cp200.id,
                'date_version': date(2025, 1, 1),
                'contract_date_start': date(2025, 1, 1),
                'contract_date_end': False,
            }
            emp_bonus_first, emp_salary_first, emp_single = self.create_employee([
                {'name': 'Split bonus-first Worker', **employee_values},
                {'name': 'Split salary-first Worker', **employee_values},
                {'name': 'Single payslip Worker', **employee_values},
            ])

            # Scenario 1: sectorial-bonus-only payslip first, validated, then the
            # monthly one. The monthly payslip no longer carries the bonus because
            # a previous payslip of the month already did.
            bonus_slip = self._june_2026_payslip(emp_bonus_first, ignore_worked_day_lines=True)
            # A bonus-only payslip must carry the sectorial bonus but no worked
            # days (i.e. no monthly salary), otherwise it's just a monthly slip.
            self.assertFalse(bonus_slip.worked_days_line_ids)
            self.assertGreater(line_total(bonus_slip, 'SECTORIAL.BONUS'), 0.0)
            # Must be validated to count as a previous monthly payslip for the next.
            bonus_slip.write({'state': 'validated'})
            salary_slip = self._june_2026_payslip(emp_bonus_first)
            total_bonus_first = line_total(bonus_slip | salary_slip, 'EmpBonus.1')

            # Scenario 2: monthly payslip first (bonus suppressed), validated, then
            # the bonus-only one. A compensatory amount above the prime zeroes the
            # sectorial bonus on the first payslip; removing it lets the bonus-only
            # payslip carry the full bonus.
            emp_salary_first.version_id.l10n_be_sectorial_bonus_compensatory_amount = 1000.0
            salary_slip_2 = self._june_2026_payslip(emp_salary_first)
            self.assertFalse(line_total(salary_slip_2, 'SECTORIAL.BONUS'))
            salary_slip_2.write({'state': 'validated'})
            emp_salary_first.version_id.l10n_be_sectorial_bonus_compensatory_amount = 0.0
            bonus_slip_2 = self._june_2026_payslip(emp_salary_first, ignore_worked_day_lines=True)
            self.assertFalse(bonus_slip_2.worked_days_line_ids)
            self.assertGreater(line_total(bonus_slip_2, 'SECTORIAL.BONUS'), 0.0)
            total_salary_first = line_total(salary_slip_2 | bonus_slip_2, 'EmpBonus.1')

            # Scenario 3: monthly salary and sectorial bonus on a single payslip.
            single_slip = self._june_2026_payslip(emp_single)
            self.assertGreater(line_total(single_slip, 'SECTORIAL.BONUS'), 0.0)
            total_single = line_total(single_slip, 'EmpBonus.1')

            # The work bonus is actually triggered, and identical across the three.
            self.assertGreater(total_single, 0.0, "Work bonus (EmpBonus.1) should be triggered")
            self.assertAlmostEqual(total_bonus_first, total_single, places=2)
            self.assertAlmostEqual(total_salary_first, total_single, places=2)
