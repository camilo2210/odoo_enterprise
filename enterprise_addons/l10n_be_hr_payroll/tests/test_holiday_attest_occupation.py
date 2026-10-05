# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime
from odoo.tools import float_compare


from odoo.tests import tagged
from .common import TestPayrollCommon


@tagged("post_install_l10n", "post_install", "-at_install")
class TestPayrollHolidayAttestOccupation(TestPayrollCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        contract_start_date = date(2024, 1, 1)
        contract_end_date = date(2024, 12, 31)
        cls.employee_isaac = cls.create_employee(
            {
                "name": "Isaac Morris",
                "date_version": date(2024, 1, 1),
                "contract_date_start": contract_start_date,
                "contract_date_end": contract_end_date,
                "resource_calendar_id": cls.belgian_company.resource_calendar_id.id,
            }
        )
        calendar_4_days, calendar_3_days = cls.env["resource.calendar"].create(
            [
                {
                    "attendance_ids": [
                        (
                            0,
                            0,
                            {
                                "dayofweek": weekday,
                                "hour_from": hour_from,
                                "hour_to": hour_to,
                            },
                        )
                        for weekday in ["0", "1", "2", "3"]
                        for hour_from, hour_to in [(8, 12), (13, 16.6)]
                    ],
                    "name": "Standard 4d/week",
                },
                {
                    "attendance_ids": [
                        (
                            0,
                            0,
                            {
                                "dayofweek": weekday,
                                "hour_from": hour_from,
                                "hour_to": hour_to,
                            },
                        )
                        for weekday in ["0", "2", "4"]
                        for hour_from, hour_to in [(8, 12), (13, 16.6)]
                    ],
                    "name": "Standard 3d/week",
                },
            ]
        )
        cls.employee_isaac_version_may = cls.employee_isaac.create_version(
            {
                "date_version": date(2024, 5, 1),
                "contract_date_start": contract_start_date,
                "contract_date_end": contract_end_date,
                "resource_calendar_id": calendar_3_days.id,
            }
        )
        cls.employee_isaac_version_sep = cls.employee_isaac.create_version(
            {
                "date_version": date(2024, 9, 1),
                "contract_date_start": contract_start_date,
                "contract_date_end": contract_end_date,
                "resource_calendar_id": calendar_4_days.id,
            }
        )

    def _validate_holiday_attest(self, result, expected):
        errors = []

        for idx, expected_dict in enumerate(expected):
            if idx >= len(result):
                errors.append(f"{'MISSING ENTRY':>20} │ Index {idx} not found in result")
                continue

            result_dict = result[idx]

            # Check values
            for key, expected_val in expected_dict.items():
                if key not in result_dict:
                    errors.append(
                        f"{'MISSING KEY':>20} │ {key:<30} │ {expected_val!s:>15} │ {'/':>15} │"
                    )
                    continue

                real_val = result_dict[key]

                # Float-safe comparison
                if isinstance(expected_val, float):
                    if float_compare(real_val, expected_val, 2):
                        diff = round(real_val - expected_val, 2)
                        errors.append(
                            f"{'WRONG VALUE':>20} │ {key:<30} │ {expected_val:>15} │ {real_val:>15} │ {diff:>15} │"
                        )
                else:
                    if real_val != expected_val:
                        errors.append(
                            f"{'WRONG VALUE':>20} │ {key:<30} │ {expected_val!s:>15} │ {real_val!s:>15} │"
                        )

            # Check unexpected keys
            for key in result_dict:
                if key not in expected_dict:
                    errors.append(
                        f"{'UNEXPECTED KEY':>20} │ {key:<30} │ {'/':>15} │ {result_dict[key]!s:>15} │"
                    )

        # Check extra entries
        if len(result) > len(expected):
            for idx in range(len(expected), len(result)):
                errors.append(f"{'EXTRA ENTRY':>20} │ Index {idx} present in result but not expected")

        # Pretty header
        if errors:
            errors.insert(
                0,
                f"{'ERROR':>20} │ {'FIELD':<30} │ {'EXPECTED':>15} │ {'REALITY':>15} │ {'DIFF':>15} │\n"
                f"{'':>20} │ {'':<30} │ {'':>15} │ {'':>15} │ {'':>15} │"
            )
            errors.extend([
                "",
                "Full result:",
                str(result)
            ])

        self.assertEqual(len(errors), 0, "\n\n" + "\n".join(errors))

    def test_holiday_attest_occupation(self):
        be_work_entry_type_unpaid_leave = self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave')
        be_work_entry_type_unjustified_reason_leave = self.env.ref('hr_work_entry.l10n_be_work_entry_type_unjustified_reason')
        be_work_entry_type_unpredictable_leave = self.env.ref('hr_work_entry.l10n_be_work_entry_type_unpredictable')
        be_work_entry_type_credit_time_leave = self.env.ref('hr_work_entry.l10n_be_work_entry_type_credit_time')
        be_work_entry_type_youth_leave = self.env.ref('hr_work_entry.l10n_be_work_entry_type_youth_time_off')
        be_work_entry_type_european_leave = self.env.ref('hr_work_entry.l10n_be_work_entry_type_european')
        be_work_entry_type_paid_leave = self.env.ref('hr_work_entry.be_work_entry_type_legal_leave')

        self.env["hr.leave.allocation"].create([
            {
                "employee_id": self.employee_isaac.id,
                "work_entry_type_id": work_entry_type.id,
                "number_of_days": 30,
                "date_from": date(2024, 1, 1),
            }
            for work_entry_type in (
                be_work_entry_type_unjustified_reason_leave,
                be_work_entry_type_youth_leave,
                be_work_entry_type_european_leave,
                be_work_entry_type_paid_leave,
                be_work_entry_type_unpredictable_leave,
            )
        ]).action_approve()

        leave_data = [
            ('unpaid leave', be_work_entry_type_unpaid_leave, datetime(2024, 1, 16), datetime(2024, 1, 27)),
            ('unjustified leave', be_work_entry_type_unjustified_reason_leave, datetime(2024, 6, 3, 6, 0, 0), datetime(2024, 6, 14, 14, 36, 0)),
            ('unpredictable leave', be_work_entry_type_unpredictable_leave, datetime(2024, 9, 27), datetime(2024, 10, 7)),
            ('credit time leave', be_work_entry_type_credit_time_leave, datetime(2024, 11, 20), datetime(2024, 11, 28)),
            ('youth leave 1', be_work_entry_type_youth_leave, datetime(2024, 2, 11), datetime(2024, 2, 19)),
            ('youth leave 2', be_work_entry_type_youth_leave, datetime(2024, 5, 11), datetime(2024, 5, 21)),
            ('youth leave 3', be_work_entry_type_youth_leave, datetime(2024, 12, 17), datetime(2024, 12, 26)),
            ('european leave 1', be_work_entry_type_european_leave, datetime(2024, 1, 1), datetime(2024, 1, 5)),
            ('european leave 2', be_work_entry_type_european_leave, datetime(2024, 7, 1), datetime(2024, 7, 6)),
            ('european leave 3', be_work_entry_type_european_leave, datetime(2024, 10, 9), datetime(2024, 10, 13)),
            ('paid leave 1', be_work_entry_type_paid_leave, datetime(2024, 1, 7), datetime(2024, 1, 12)),
            ('paid leave 2', be_work_entry_type_paid_leave, datetime(2024, 8, 5), datetime(2024, 8, 11)),
            ('paid leave 3', be_work_entry_type_paid_leave, datetime(2024, 10, 21), datetime(2024, 10, 25)),
        ]
        self.env["hr.leave"].create(
            [
                {
                    "name": name,
                    "employee_id": self.employee_isaac.id,
                    "work_entry_type_id": work_entry_type.id,
                    "request_date_from": date_from,
                    "request_date_to": date_to,
                }
                for name, work_entry_type, date_from, date_to in leave_data
            ]
        )._action_validate()
        payslip_periods = [
            (date(2024, 1, 1), date(2024, 1, 31)),
            (date(2024, 2, 1), date(2024, 2, 29)),
            (date(2024, 3, 1), date(2024, 3, 31)),
            (date(2024, 4, 1), date(2024, 4, 30)),
            (date(2024, 5, 1), date(2024, 5, 31)),
            (date(2024, 6, 1), date(2024, 6, 30)),
            (date(2024, 7, 1), date(2024, 7, 31)),
            (date(2024, 8, 1), date(2024, 8, 31)),
            (date(2024, 9, 1), date(2024, 9, 30)),
            (date(2024, 10, 1), date(2024, 10, 31)),
            (date(2024, 11, 1), date(2024, 11, 30)),
            (date(2024, 12, 1), date(2024, 12, 31)),
        ]
        structure = self.env.ref("l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary")
        all_payslips = self.env['hr.payslip'].create([
            {
                'name': f'{period[0].strftime("%b %Y")} Test Payslip',
                'employee_id': self.employee_isaac.id,
                'version_id': self.employee_isaac._get_version(period[0]).id,
                'date_from': period[0],
                'date_to': period[1],
                'company_id': self.belgian_company.id,
                'struct_id': structure.id,
            }
            for period in payslip_periods
        ])
        all_payslips.compute_sheet()
        all_payslips.action_payslip_done()

        holiday_attest_occupation = self.employee_isaac.get_l10n_be_holiday_attest_occupations(2024)
        holiday_attest_occupation_values = [
            {
                "date_start": date(2024, 1, 1),
                "hours_per_week": 38.0,
                "reference_hours_per_week": 38.0,
                "days_per_week": 5,
                "date_end": date(2024, 4, 30),
                "equivalent_days": 67.0,
                "senior_youth_leaves": 6.0,
                "european_leaves": 5.0,
                "paid_leaves": 5.0,
                "non_equivalent_days": 9.0,
                "european_leaves_amount": 576.92,
            },
            {
                "date_start": date(2024, 5, 1),
                "hours_per_week": 22.8,
                "reference_hours_per_week": 38.0,
                "days_per_week": 3,
                "date_end": date(2024, 8, 31),
                "equivalent_days": 40.0,
                "senior_youth_leaves": 4.0,
                "european_leaves": 3.0,
                "paid_leaves": 3.0,
                "non_equivalent_days": 6.0,
                "european_leaves_amount": 576.92,
            },
            {
                "date_start": date(2024, 9, 1),
                "hours_per_week": 30.4,
                "reference_hours_per_week": 38.0,
                "days_per_week": 4,
                "date_end": date(2024, 12, 31),
                "equivalent_days": 50.0,
                "senior_youth_leaves": 7.0,
                "european_leaves": 2.0,
                "paid_leaves": 4.0,
                "non_equivalent_days": 11.0,
                "european_leaves_amount": 288.46,
            },
        ]
        self._validate_holiday_attest(holiday_attest_occupation, holiday_attest_occupation_values)
