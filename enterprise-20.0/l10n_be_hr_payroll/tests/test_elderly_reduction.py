# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo.tests import tagged
from odoo.addons.l10n_be_hr_payroll.models.hr_dmfa import (
    DMFAWorker,
    DMFAOccupationTargetGroup,
)

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'elderly_reduction')
class TestElderlyReduction(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Payslip = cls.env['hr.payslip']

        cls.partner_brussels = cls.env['res.partner'].create({'name': 'BRU Work Address'})
        cls.partner_wallonia = cls.env['res.partner'].create({'name': 'WA Work Address'})
        cls.env['hr.work.location'].create([{
            'company_id': cls.belgian_company.id,
            'bce_code': '8888888888',
            'location_type': 'dmfa_unit',
            'address_id': cls.partner_brussels.id,
            'competence': 'br',
        }, {
            'company_id': cls.belgian_company.id,
            'bce_code': '8888888881',
            'location_type': 'dmfa_unit',
            'address_id': cls.partner_wallonia.id,
            'competence': 'wa',
        }])

    def _make_employee(self, birthday, partner, calendar=None, wage=2500.0, hire_date=None):
        calendar = calendar or self.resource_calendar
        hire_date = hire_date or date(2018, 1, 1)
        emp = self.create_employee({
            'name': f'Elderly {birthday} hired {hire_date}',
            'birthday': birthday,
            'date_version': hire_date,
            'contract_date_start': hire_date,
            'contract_date_end': False,
            'resource_calendar_id': calendar.id,
            'wage': wage,
            'l10n_be_worker_code_id': self.worker_code_id.id,
            'l10n_be_dimona_category': 'oth',
            'address_id': partner.id,
        })
        return emp

    def _compute_elderly_amount(self, employee, date_from, date_to):
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'version_id': employee.version_id.id,
            'date_from': date_from,
            'date_to': date_to,
            'company_id': self.belgian_company.id,
        })
        payslip.compute_sheet()
        line = payslip.line_ids.filtered(lambda l: l.salary_rule_id.code == 'ONSSELDERLY')
        return line.total if line else 0.0

    def _build_dmfa_worker(self, employee, quarter_start):
        quarter_end = quarter_start + relativedelta(months=3, days=-1)
        payslips = self.env['hr.payslip']
        cursor = quarter_start
        while cursor <= quarter_end:
            month_end = cursor + relativedelta(months=1, days=-1)
            ps = self.env['hr.payslip'].create({
                'employee_id': employee.id,
                'version_id': employee.version_id.id,
                'date_from': cursor,
                'date_to': month_end,
                'company_id': self.belgian_company.id,
            })
            ps.compute_sheet()
            payslips |= ps
            cursor = month_end + relativedelta(days=1)
        return DMFAWorker(payslips, quarter_start, quarter_end, '1')

    def _elderly_deductions(self, worker):
        elderly_codes = self.env['hr.payslip']._l10n_be_elderly_reduction_codes()
        return [
            d
            for occ in worker.occupations
            for d in (occ.occupation_deductions or [])
            if isinstance(d, DMFAOccupationTargetGroup) and d.deduction_code in elderly_codes
        ]

    # Frozen to Q1 2026: the Brussels elderly reduction is removed for periods
    # from Q3 2026 onwards.
    @freeze_time('2026-01-01')
    def test_payslip_elderly_reduction(self):
        # Brussels pre-2024 (old 57-65 band), age 60 → eligible.
        emp = self._make_employee(date(1964, 1, 1), self.partner_brussels)
        amount = self._compute_elderly_amount(emp, date(2024, 1, 1), date(2024, 1, 31))
        self.assertEqual(amount, 333.33)

        # Brussels pre-2024, age out of band (age 66 on 2024-03-31).
        emp = self._make_employee(date(1958, 1, 1), self.partner_brussels)
        amount = self._compute_elderly_amount(emp, date(2024, 1, 1), date(2024, 1, 31))
        self.assertEqual(amount, 0)

        # Brussels post-2024 (new 61-66 band), age 58 → not eligible.
        emp = self._make_employee(date(1966, 1, 1), self.partner_brussels)
        amount = self._compute_elderly_amount(emp, date(2025, 1, 1), date(2025, 1, 31))
        self.assertEqual(amount, 0)

        # Brussels post-2024, age 62 → eligible.
        emp = self._make_employee(date(1963, 1, 1), self.partner_brussels)
        amount = self._compute_elderly_amount(emp, date(2025, 1, 1), date(2025, 1, 31))
        self.assertEqual(amount, 333.33)

        # Wallonia pre-2023 (8320 band), age 56 → G=400 bracket.
        emp = self._make_employee(date(1966, 1, 1), self.partner_wallonia)
        amount = self._compute_elderly_amount(emp, date(2022, 10, 1), date(2022, 10, 31))
        self.assertEqual(amount, 133.33)

        # Wallonia post-2023 (8321 band), age 61 → G=1000.
        emp = self._make_employee(date(1964, 1, 1), self.partner_wallonia)
        amount = self._compute_elderly_amount(emp, date(2025, 1, 1), date(2025, 1, 31))
        self.assertEqual(amount, 333.33)

        # Wallonia age too young → not eligible.
        emp = self._make_employee(date(1975, 1, 1), self.partner_wallonia)
        amount = self._compute_elderly_amount(emp, date(2025, 1, 1), date(2025, 1, 31))
        self.assertEqual(amount, 0)

        # Wage above the cap → amount forced to 0.
        emp = self._make_employee(date(1963, 1, 1), self.partner_brussels, wage=20000.0)
        amount = self._compute_elderly_amount(emp, date(2025, 1, 1), date(2025, 1, 31))
        self.assertEqual(amount, 0)

        # Partial time (mid-time) is eligible but strictly lower than full-time.
        emp_full = self._make_employee(date(1963, 1, 1), self.partner_brussels)
        emp_part = self._make_employee(
            date(1963, 1, 2), self.partner_brussels,
            calendar=self.resource_calendar_mid_time, wage=1250.0,
        )
        amount_full = self._compute_elderly_amount(emp_full, date(2025, 1, 1), date(2025, 1, 31))
        amount_part = self._compute_elderly_amount(emp_part, date(2025, 1, 1), date(2025, 1, 31))
        self.assertEqual(amount_full, 333.33)
        self.assertEqual(amount_part, 163.33)

        # Wallonia grandfather: hired pre-2023-07 and eligible under the old
        # 8320 table stays in that table after 2023-07.
        emp = self._make_employee(date(1961, 1, 1), self.partner_wallonia)
        amount = self._compute_elderly_amount(emp, date(2025, 1, 1), date(2025, 1, 31))
        self.assertEqual(amount, 500.0)  # G=1500 (62-65 band) / 3

        # Wallonia late hire (>= 2026-04-01): 8321 G=400 sub-bracket min age
        # becomes 57, so age 55 → no monthly estimation.
        emp = self._make_employee(
            date(1971, 1, 1), self.partner_wallonia,
            hire_date=date(2026, 4, 1),
        )
        amount = self._compute_elderly_amount(emp, date(2026, 4, 1), date(2026, 4, 30))
        self.assertEqual(amount, 0)

        # Wallonia late hire, age 57 still eligible for the 400€ bracket.
        emp = self._make_employee(
            date(1969, 1, 1), self.partner_wallonia,
            hire_date=date(2026, 4, 1),
        )
        amount = self._compute_elderly_amount(emp, date(2026, 4, 1), date(2026, 4, 30))
        self.assertEqual(amount, 133.33)

    # Frozen to Q1 2026: the Brussels elderly reduction is removed for periods
    # from Q3 2026 onwards.
    @freeze_time('2026-01-01')
    def test_dmfa_elderly_reduction(self):
        # Brussels post-2024, age 62 in Q1 2025 → code 7320, amount ~1000.
        emp = self._make_employee(date(1963, 1, 1), self.partner_brussels)
        deductions = self._elderly_deductions(self._build_dmfa_worker(emp, date(2025, 1, 1)))
        self.assertEqual(len(deductions), 1)
        self.assertEqual(deductions[0].deduction_code, 7320)
        self.assertEqual(int(deductions[0].deduction_amount) / 100, 1000.0)

        # Wallonia pre-2023, age 56 in Q4 2022 → bracket (8320, 55, 57, 400).
        emp = self._make_employee(date(1966, 1, 1), self.partner_wallonia)
        deductions = self._elderly_deductions(self._build_dmfa_worker(emp, date(2022, 10, 1)))
        self.assertEqual(len(deductions), 1)
        self.assertEqual(deductions[0].deduction_code, 8320)
        self.assertEqual(int(deductions[0].deduction_amount) / 100, 400.0)

        # Wallonia post-2023, age 59 in Q1 2025 → (8320, 58, 61, 1000).
        emp = self._make_employee(date(1966, 1, 1), self.partner_wallonia)
        deductions = self._elderly_deductions(self._build_dmfa_worker(emp, date(2025, 1, 1)))
        self.assertEqual(len(deductions), 1)
        self.assertEqual(deductions[0].deduction_code, 8320)
        self.assertEqual(int(deductions[0].deduction_amount) / 100, 1000.0)

        # Wallonia post-2023, age 63 @freeze_time('2026-01-01') in Q1 2026 and hired in 1/3/2026  → (8322, 60, 63, 1000).
        emp = self._make_employee(date(1963, 1, 1), self.partner_wallonia, hire_date=date(2026, 3, 1))
        deductions = self._elderly_deductions(self._build_dmfa_worker(emp, date(2026, 3, 1)))
        self.assertEqual(len(deductions), 1)
        self.assertEqual(deductions[0].deduction_code, 8322)
        self.assertEqual(int(deductions[0].deduction_amount) / 100, 1000.0)

        # Age 50 → no matching bracket → no elderly deduction.
        emp = self._make_employee(date(1975, 1, 1), self.partner_wallonia)
        self.assertEqual(self._elderly_deductions(self._build_dmfa_worker(emp, date(2025, 1, 1))), [])

        # Wage above the cap → no elderly deduction.
        emp = self._make_employee(date(1963, 1, 1), self.partner_brussels, wage=20000.0)
        self.assertEqual(self._elderly_deductions(self._build_dmfa_worker(emp, date(2025, 1, 1))), [])

        # Partial time (mid-time) → amount strictly lower than full time.
        emp_full = self._make_employee(date(1963, 1, 1), self.partner_brussels)
        emp_part = self._make_employee(
            date(1963, 1, 2), self.partner_brussels,
            calendar=self.resource_calendar_mid_time, wage=1250.0,
        )
        full_amount = int(self._elderly_deductions(
            self._build_dmfa_worker(emp_full, date(2025, 1, 1))
        )[0].deduction_amount) / 100
        part_amount = int(self._elderly_deductions(
            self._build_dmfa_worker(emp_part, date(2025, 1, 1))
        )[0].deduction_amount) / 100
        self.assertEqual(full_amount, 1000.0)
        self.assertEqual(part_amount, 480.0)

        # 4/5 Brussels employee (age 62 in Q1 2025): both the payslip estimation
        # and the DMFA elderly deduction scale proportionally to mu ~= 0.8.
        emp = self._make_employee(
            date(1963, 1, 1), self.partner_brussels,
            calendar=self.resource_calendar_4_5, wage=2500.0 * 4 / 5,
        )

        deductions = self._elderly_deductions(self._build_dmfa_worker(emp, date(2025, 1, 1)))
        self.assertEqual(len(deductions), 1)
        self.assertEqual(deductions[0].deduction_code, 7320)
        amount = int(deductions[0].deduction_amount) / 100
        self.assertEqual(amount, 959.4)

        # Wallonia grandfather: hired pre-2023-07, stays on the 8320 table in
        # Q1 2025 with G=1500 (age 64 in the 62-65 old band).
        emp = self._make_employee(date(1961, 1, 1), self.partner_wallonia)
        deductions = self._elderly_deductions(self._build_dmfa_worker(emp, date(2025, 1, 1)))
        self.assertEqual(len(deductions), 1)
        self.assertEqual(deductions[0].deduction_code, 8320)
        self.assertEqual(int(deductions[0].deduction_amount) / 100, 1500.0)

        # Wallonia late hire (2026-04-01), age 55: bumped 400€ sub-bracket
        # starts at 57, so age 55 is out → no elderly deduction.
        emp = self._make_employee(
            date(1971, 1, 1), self.partner_wallonia,
            hire_date=date(2026, 4, 1),
        )
        self.assertEqual(self._elderly_deductions(self._build_dmfa_worker(emp, date(2026, 4, 1))), [])

        # Wallonia late hire, age 57: 8321 with G=400.
        emp = self._make_employee(
            date(1969, 1, 1), self.partner_wallonia,
            hire_date=date(2026, 4, 1),
        )
        deductions = self._elderly_deductions(self._build_dmfa_worker(emp, date(2026, 4, 1)))
        self.assertEqual(len(deductions), 1)
        self.assertEqual(deductions[0].deduction_code, 8321)
        self.assertEqual(int(deductions[0].deduction_amount) / 100, 400.0)

    @freeze_time('2026-07-01')
    def test_brussels_elderly_reduction_removed_q3_2026(self):
        # Brussels elderly reduction is removed for periods from Q3 2026 on:
        # an otherwise eligible worker (age 63) gets neither a payslip
        # estimation nor a DMFA target-group deduction in Q3 2026.
        emp = self._make_employee(date(1963, 1, 1), self.partner_brussels)
        amount = self._compute_elderly_amount(emp, date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(amount, 0)
        self.assertEqual(
            self._elderly_deductions(self._build_dmfa_worker(emp, date(2026, 7, 1))),
            [],
        )
