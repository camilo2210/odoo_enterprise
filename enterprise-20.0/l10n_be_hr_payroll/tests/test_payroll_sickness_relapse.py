from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged("post_install_l10n", "post_install", "-at_install", "payroll_sickness_relapse")
class TestPayrollSicknessRelapse(TestPayrollCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.sick_time_off_type = cls.env.ref("hr_work_entry.be_work_entry_type_sick_leave")

    def _create_cdd_employe(self, contract_date_start, contract_date_end, wage=2000):
        return self.env['hr.employee'].create({
            'name': 'CDD Employe',
            'company_id': self.belgian_company.id,
            'resource_calendar_id': self.resource_calendar.id,
            'private_country_id': self.env.ref('base.be').id,
            'marital': 'single',
            'spouse_fiscal_status': 'without_income',
            'l10n_be_resident_situation': 'resident',
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'date_version': contract_date_start,
            'contract_date_start': contract_date_start,
            'contract_date_end': contract_date_end,
            'fixed_term': True,
            'wage': wage,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00495').id,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_b').id,
        })

    def test_sickness_relapse_visibility(self):
        """
        Test Case:
        Employee Test is sick for a week. The following week the employee becomes
        sick again and submits another time off request. For the second
        time off request the employee has the option to select if this sickness
        is a relapse of the sickness from the week before or a new sickness.
        """
        first_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 1),
                "request_date_to": date(2024, 7, 5),
            }
        )
        second_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 10),
                "request_date_to": date(2024, 7, 12),
            }
        )

        self.assertFalse(first_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(second_leave.l10n_be_sickness_can_relapse)

    def test_sickness_relapse_half_days_01(self):
        self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 1),
                "request_date_to": date(2024, 8, 1),
                "request_date_from_period": "pm",
                "request_date_to_period": "am"
            }
        )
        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_test.id)
        ]).sorted('request_date_from')

        self.assertEqual(len(all_leaves), 2)

        self.assertEqual(all_leaves[0].request_date_from, date(2024, 7, 1))
        self.assertEqual(all_leaves[0].request_date_to, date(2024, 7, 31))
        self.assertEqual(all_leaves[0].request_date_from_period, 'pm')
        self.assertEqual(all_leaves[0].request_date_to_period, 'am')

        self.assertEqual(all_leaves[1].request_date_from, date(2024, 7, 31))
        self.assertEqual(all_leaves[1].request_date_to, date(2024, 8, 1))
        self.assertEqual(all_leaves[1].request_date_from_period, 'pm')
        self.assertEqual(all_leaves[1].request_date_to_period, 'am')

    def test_sickness_relapse_half_days_02(self):
        self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 1),
                "request_date_to": date(2024, 8, 1),
                "request_date_from_period": "pm",
                "request_date_to_period": "pm"
            }
        )
        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_test.id)
        ]).sorted('request_date_from')

        self.assertEqual(len(all_leaves), 2)

        self.assertEqual(all_leaves[0].request_date_from, date(2024, 7, 1))
        self.assertEqual(all_leaves[0].request_date_to, date(2024, 7, 31))
        self.assertEqual(all_leaves[0].request_date_from_period, 'pm')
        self.assertEqual(all_leaves[0].request_date_to_period, 'am')

        self.assertEqual(all_leaves[1].request_date_from, date(2024, 7, 31))
        self.assertEqual(all_leaves[1].request_date_to, date(2024, 8, 1))
        self.assertEqual(all_leaves[1].request_date_from_period, 'pm')
        self.assertEqual(all_leaves[1].request_date_to_period, 'pm')

    def test_sickness_relapse_half_days_03(self):
        self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 1),
                "request_date_to": date(2024, 8, 1),
                "request_date_from_period": "am",
                "request_date_to_period": "pm"
            }
        )
        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_test.id)
        ]).sorted('request_date_from')

        self.assertEqual(len(all_leaves), 2)

        self.assertEqual(all_leaves[0].request_date_from, date(2024, 7, 1))
        self.assertEqual(all_leaves[0].request_date_to, date(2024, 7, 30))
        self.assertEqual(all_leaves[0].request_date_from_period, 'am')
        self.assertEqual(all_leaves[0].request_date_to_period, 'pm')

        self.assertEqual(all_leaves[1].request_date_from, date(2024, 7, 31))
        self.assertEqual(all_leaves[1].request_date_to, date(2024, 8, 1))
        self.assertEqual(all_leaves[1].request_date_from_period, 'am')
        self.assertEqual(all_leaves[1].request_date_to_period, 'pm')

    def test_sickness_relapse_half_days_04(self):
        self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 1),
                "request_date_to": date(2024, 8, 1),
                "request_date_from_period": "am",
                "request_date_to_period": "am"
            }
        )
        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_test.id)
        ]).sorted('request_date_from')

        self.assertEqual(len(all_leaves), 2)

        self.assertEqual(all_leaves[0].request_date_from, date(2024, 7, 1))
        self.assertEqual(all_leaves[0].request_date_to, date(2024, 7, 30))
        self.assertEqual(all_leaves[0].request_date_from_period, 'am')
        self.assertEqual(all_leaves[0].request_date_to_period, 'pm')

        self.assertEqual(all_leaves[1].request_date_from, date(2024, 7, 31))
        self.assertEqual(all_leaves[1].request_date_to, date(2024, 8, 1))
        self.assertEqual(all_leaves[1].request_date_from_period, 'am')
        self.assertEqual(all_leaves[1].request_date_to_period, 'am')

    def test_sickness_relapse_no_relapse(self):
        """
        Test Case:
        Employee Test is sick for 3 weeks. A week after the employee becomes
        sick again and submits another time off request for another 3 weeks.
        For the second time off request Employee test has indicated that this
        is a new sickness and not a relapse of the previous sickness.
        This results in a work entry with the code 013.00, Sick Time Off,
        30 Calendar days after the first sick day, indicating that
        the first sick leave has no effect on the second one.
        """
        self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 1),
                "request_date_to": date(2024, 7, 20),
            }
        )
        self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 29),
                "request_date_to": date(2024, 8, 16),
                "l10n_be_sickness_relapse": False,
            }
        )

        work_entries_vals = self.employee_test.version_ids.generate_work_entries(
            date(2024, 8, 8), date(2024, 8, 8)
        )
        work_entries_code = {vals['work_entry_type_id'].code for vals in work_entries_vals}

        self.assertSetEqual(work_entries_code, {"013.00"})

    def test_sickness_relapse_no_relapse_split(self):
        """
        Test Case:
        Employee Test is sick for 3 weeks. A week after the employee becomes
        sick again and submits another time off request for another 5 weeks.
        For the second time off request, Employee test has indicated that this
        is a new sickness and not a relapse of the previous sickness.
        This results two work entries:
            - a work entry with the code 013.00, Sick Time Off, 30 Calendar days
            after the first sick day, for a duration of 30 days;
            - a work entry with the code 122.00, Sick Time Off(Without Guaranteed Salary),
            60 Calendar days after the first sick day, for a duration of 5 days.
        """
        self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 1),
                "request_date_to": date(2024, 7, 20),
            }
        )
        self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 29),
                "request_date_to": date(2024, 9, 1),
                "l10n_be_sickness_relapse": False,
            }
        )

        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_test.id)
        ]).sorted('date_from')

        self.assertEqual(len(all_leaves), 3)

        self.assertEqual(all_leaves[0].date_from.strftime('%Y-%m-%d'), "2024-07-01")
        self.assertEqual(all_leaves[0].date_to.strftime('%Y-%m-%d'), "2024-07-20")
        self.assertEqual(all_leaves[0].work_entry_type_id, self.sick_time_off_type)

        self.assertEqual(all_leaves[1].date_from.strftime('%Y-%m-%d'), "2024-07-29")
        self.assertEqual(all_leaves[1].date_to.strftime('%Y-%m-%d'), "2024-08-27")
        self.assertEqual(all_leaves[1].work_entry_type_id, self.sick_time_off_type)

        self.assertEqual(all_leaves[2].date_from.strftime('%Y-%m-%d'), "2024-08-28")
        self.assertEqual(all_leaves[2].date_to.strftime('%Y-%m-%d'), "2024-09-01")
        self.assertEqual(all_leaves[2].work_entry_type_id, self.env.ref("hr_work_entry.l10n_be_work_entry_type_common_law_illness_after_legal_period"))

    def test_sickness_relapse_with_relapse(self):
        """
        Test Case:
        Employee Test is sick for 3 weeks. A week after the employee becomes
        sick again and submits another time off request for another 3 weeks.
        For the second time off request Employee test has indicated that this
        a relapse of the previous sickness. This results in a work entry
        with the code 122.00, Sick Time Off(Without Guaranteed Salary),
        31 sick days after the first sick day, indicating that the second
        sick leave is a continuation of the first one.
        """
        first_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 1),
                "request_date_to": date(2024, 7, 20),
            }
        )
        self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 29),
                "request_date_to": date(2024, 8, 16),
                "l10n_be_sickness_relapse": True,
                "l10n_be_sickness_relapse_origin_leave_id": first_leave.id,
            }
        )

        work_entry_paid_vals = self.employee_test.version_ids.generate_work_entries(
            date(2024, 8, 7), date(2024, 8, 7)
        )
        work_entry_unpaid_vals = self.employee_test.version_ids.generate_work_entries(
            date(2024, 8, 8), date(2024, 8, 8)
        )

        work_entry_paid_code = {vals['work_entry_type_id'].code for vals in work_entry_paid_vals}
        work_entry_unpaid_code = {vals['work_entry_type_id'].code for vals in work_entry_unpaid_vals}

        self.assertSetEqual(work_entry_paid_code, {"013.00"})
        self.assertSetEqual(work_entry_unpaid_code, {"122.00"})

    def test_sickness_multiple_sicknesses_partial_relapse(self):
        """
        Test Case:
        Employee Test is sick for 5 days every week for 4 weeks. The next week
        Employee Test is sick again, but this is a new sickness. This sickness
        relapses again every week for 2 more week. Even though Employee Test has
        taken 35 days of sick leave he should still be paid fully as the
        two sick leaves are not for the same illness. Thus all work entries
        starting from the first day in the 7th week should still have
        a work entry code of LEAVE110.
        """
        first_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 1),
                "request_date_to": date(2024, 7, 5),
            }
        )
        second_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 8),
                "request_date_to": date(2024, 7, 12),
                "l10n_be_sickness_relapse": True,
                "l10n_be_sickness_relapse_origin_leave_id": first_leave.id,
            }
        )
        third_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 15),
                "request_date_to": date(2024, 7, 19),
                "l10n_be_sickness_relapse": True,
                "l10n_be_sickness_relapse_origin_leave_id": second_leave.id,
            }
        )
        fourth_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 22),
                "request_date_to": date(2024, 7, 26),
                "l10n_be_sickness_relapse": True,
                "l10n_be_sickness_relapse_origin_leave_id": third_leave.id,
            }
        )
        fifth_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 29),
                "request_date_to": date(2024, 8, 2),
                "l10n_be_sickness_relapse": False,
            }
        )
        sixth_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 8, 5),
                "request_date_to": date(2024, 8, 9),
                "l10n_be_sickness_relapse": True,
                "l10n_be_sickness_relapse_origin_leave_id": fifth_leave.id,
            }
        )
        seventh_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 8, 12),
                "request_date_to": date(2024, 8, 16),
                "l10n_be_sickness_relapse": True,
                "l10n_be_sickness_relapse_origin_leave_id": sixth_leave.id,
            }
        )

        work_entries_vals = self.employee_test.version_ids.generate_work_entries(
            date(2024, 8, 12), date(2024, 8, 12)
        )

        work_entries_code = {vals['work_entry_type_id'].code for vals in work_entries_vals}

        self.assertSetEqual(work_entries_code, {"013.00"})
        self.assertFalse(first_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(second_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(third_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(fourth_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(fifth_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(sixth_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(seventh_leave.l10n_be_sickness_can_relapse)

    def test_sickness_multiple_sicknesses_only_relapse(self):
        """
        Test Case:
        Employee Test is sick for 5 days every week for 7 weeks, with every sick
        leave being a relapse of the previous one. All work entries starting
        from the first day in the 7th week should have a work entry code of 122.00.
        """
        first_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 1),
                "request_date_to": date(2024, 7, 5),
            }
        )
        second_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 8),
                "request_date_to": date(2024, 7, 12),
                "l10n_be_sickness_relapse": True,
                "l10n_be_sickness_relapse_origin_leave_id": first_leave.id,
            }
        )
        third_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 15),
                "request_date_to": date(2024, 7, 19),
                "l10n_be_sickness_relapse": True,
                "l10n_be_sickness_relapse_origin_leave_id": second_leave.id,
            }
        )
        fourth_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 22),
                "request_date_to": date(2024, 7, 26),
                "l10n_be_sickness_relapse": True,
                "l10n_be_sickness_relapse_origin_leave_id": third_leave.id,
            }
        )
        fifth_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 29),
                "request_date_to": date(2024, 8, 2),
                "l10n_be_sickness_relapse": True,
                "l10n_be_sickness_relapse_origin_leave_id": fourth_leave.id,
            }
        )
        sixth_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 8, 5),
                "request_date_to": date(2024, 8, 9),
                "l10n_be_sickness_relapse": True,
                "l10n_be_sickness_relapse_origin_leave_id": fifth_leave.id,
            }
        )
        seventh_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 8, 12),
                "request_date_to": date(2024, 8, 16),
                "l10n_be_sickness_relapse": True,
                "l10n_be_sickness_relapse_origin_leave_id": sixth_leave.id,
            }
        )

        work_entries_vals = self.employee_test.version_ids.generate_work_entries(
            date(2024, 8, 12), date(2024, 8, 12)
        )
        work_entries_code = {vals['work_entry_type_id'].code for vals in work_entries_vals}

        self.assertSetEqual(work_entries_code, {"122.00"})
        self.assertFalse(first_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(second_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(third_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(fourth_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(fifth_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(sixth_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(seventh_leave.l10n_be_sickness_can_relapse)

    def test_sickness_biweekly_relapse(self):
        """
        Test Case:
        A person is sick for 2 days every 14 days for almost 8 months.
        Eventually the sick leave days should culminate in over 30 days
        of leave causing the person to no longer have work entries with the
        code LEAVE110.
        """
        previous_leave = self.env["hr.leave"]
        for i in range(16):
            start_date = date(2024, 1, 1) + relativedelta(days=(14 * i))
            end_date = start_date + relativedelta(days=1)
            previous_leave = self.env["hr.leave"].create(
                {
                    "work_entry_type_id": self.sick_time_off_type.id,
                    "employee_id": self.employee_test.id,
                    "request_date_from": start_date,
                    "request_date_to": end_date,
                    "l10n_be_sickness_relapse": i != 0,
                    "l10n_be_sickness_relapse_origin_leave_id": previous_leave.id if i != 0 else None,
                }
            )

        work_entries_vals = self.employee_test.version_ids.generate_work_entries(
            date(2024, 7, 15), date(2024, 7, 29)
        )

        paid_date = [vals for vals in work_entries_vals if vals['date'].day == 15]
        unpaid_date = [vals for vals in work_entries_vals if vals['date'].day == 29]
        work_entry_paid_code = {vals['work_entry_type_id'].code for vals in paid_date}
        work_entry_unpaid_code = {vals['work_entry_type_id'].code for vals in unpaid_date}

        self.assertSetEqual(work_entry_paid_code, {"013.00"})
        self.assertSetEqual(work_entry_unpaid_code, {"122.00"})

    def test_from_comment(self):
        """
        Example (all dates are inclusive):
        | Name | Date from   | Date to     | Relapse | Calendar Days | Work Days  |
        | ---- | ----------- | ----------- | ------- | ------------- | ---------- |
        | 1st  | 10/Jun/2024 | 12/Jun/2024 | False   | 03 (c)days    | 03 (w)days |
        | 2nd  | 01/Jul/2024 | 08/Jul/2024 | False   | 08 (c)days    | 06 (w)days |
        | 3rd  | 15/Jul/2024 | 30/Jul/2024 | True    | 16 (c)days    | 12 (w)days |
        | 4th  | 05/Aug/2024 | 15/Aug/2024 | True    | 11 (c)days    | 09 (w)days |

        Note: 1st and 2nd leave will have a relapse value of True in practice because
        that is the default value for the field. In this example, the value is set to
        False to hopefully make the example clearer.

        The first leave is shorter than 30 (calendar) days.
        All (work) days within this leave have a guaranteed salary.

        The second leave is shorter than 30 (c) days.
        The gap between it and the first leave is greater than 14 days.
        All (w) days within this leave have a guaranteed salary.

        The third leave is shorter than 30 (c) days.
        The gap between it and the second leave is less than 14 days.
        It is a relapse, sum the duration of this and previous related leaves.
        The sum is 8 + 16 = 24 (c) days, which is less than 30 days.
        All (w) days within this leave have a guaranteed salary.

        The fourth leave is shorter than 30 (c) days.
        The gap between it and the third leave is less than 14 days.
        It is a relapse, sum the duration of this and previous related leaves.
        That sum is 8 + 16 + 11 = 35 (c) days, which is greater than 30 days.
        The first 6 (c) days have a guaranteed salary.
        (w) days 12/08 - 15/08 do not have a guaranteed salary.
        """
        first_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 6, 10),
                "request_date_to": date(2024, 6, 12),
            }
        )
        second_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 1),
                "request_date_to": date(2024, 7, 8),
            }
        )
        third_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 7, 15),
                "request_date_to": date(2024, 7, 30),
                "l10n_be_sickness_relapse": True,
                "l10n_be_sickness_relapse_origin_leave_id": second_leave.id,
            }
        )
        fourth_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2024, 8, 5),
                "request_date_to": date(2024, 8, 15),
                "l10n_be_sickness_relapse": True,
                "l10n_be_sickness_relapse_origin_leave_id": third_leave.id,
            }
        )

        work_entries_vals = self.employee_test.version_ids.generate_work_entries(
            date(2024, 8, 9), date(2024, 8, 12)
        )

        paid_date = [vals for vals in work_entries_vals if vals['date'].day == 9]
        unpaid_date = [vals for vals in work_entries_vals if vals['date'].day == 12]
        work_entry_paid_code = {vals['work_entry_type_id'].code for vals in paid_date}
        work_entry_unpaid_code = {vals['work_entry_type_id'].code for vals in unpaid_date}

        self.assertSetEqual(work_entry_paid_code, {"013.00"})
        self.assertSetEqual(work_entry_unpaid_code, {"122.00"})
        self.assertFalse(first_leave.l10n_be_sickness_can_relapse)
        self.assertFalse(second_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(third_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(fourth_leave.l10n_be_sickness_can_relapse)

    def test_sickness_relapse_starting_from_2026(self):
        """
        Example (all dates are inclusive):
        | Leave | Date from   | Date to     | Relapse | Calendar Days | Work Days  |
        | ----- | ----------- | ----------- | ------- | ------------- | ---------- |
        | 1st   | 10/Jan/26   | 30/Jan/26   | False   | 21 (c)days    | 15 (w)days |
        | 2nd   | 01/Apr/26   | 15/Apr/26   | False   | 15 (c)days    | 11 (w)days |
        | 3rd   | 11/May/26   | 30/May/26   | True    | 20 (c)days    | 15 (w)days |
        | 4th   | 10/Aug/26   | 20/Aug/26   | False   | 11 (c)days    | 8 (w)days  |

        The first leave is shorter than 30 (calendar) days.
        All (work) days within this leave have a guaranteed salary.

        The second leave is shorter than 30 (c) days.
        The gap between it and the first leave is greater than 56 days.
        It is not considered as a relapse.
        All (w) days within this leave have a guaranteed salary.

        The third leave is shorter than 30 (c) days.
        The gap between it and the second leave is less than 56 days.
        It is a relapse, sum the duration of this and previous related leaves.
        The sum is 15 + 20 = 35 (c) days, which is greater than 30 days.
        The first 30 (c) days have a guaranteed salary.
        (w) days 26/05 - 30/05 do not have a guaranteed salary.

        The fourth leave is shorter than 30 (c) days.
        The gap between it and the third leave is greater than 56 days.
        It is not considered as a relapse.
        """

        first_leave = self.env["hr.leave"].create({
            "work_entry_type_id": self.sick_time_off_type.id,
            "employee_id": self.employee_test.id,
            "request_date_from": date(2026, 1, 10),
            "request_date_to": date(2026, 1, 30),
        })

        second_leave = self.env["hr.leave"].create({
            "work_entry_type_id": self.sick_time_off_type.id,
            "employee_id": self.employee_test.id,
            "request_date_from": date(2026, 4, 1),
            "request_date_to": date(2026, 4, 15),
        })

        third_leave = self.env["hr.leave"].create({
            "work_entry_type_id": self.sick_time_off_type.id,
            "employee_id": self.employee_test.id,
            "request_date_from": date(2026, 5, 11),
            "request_date_to": date(2026, 5, 30),
            "l10n_be_sickness_relapse": True,
            "l10n_be_sickness_relapse_origin_leave_id": second_leave.id,
        })

        fourth_leave = self.env["hr.leave"].create({
            "work_entry_type_id": self.sick_time_off_type.id,
            "employee_id": self.employee_test.id,
            "request_date_from": date(2026, 8, 10),
            "request_date_to": date(2026, 8, 20),
        })

        work_entries_vals = self.employee_test.version_ids.generate_work_entries(
            date(2026, 5, 21), date(2026, 5, 30)
        )

        paid_date = [vals for vals in work_entries_vals if vals['date'].day == 22]
        unpaid_date = [vals for vals in work_entries_vals if vals['date'].day == 29]
        work_entry_paid_code = {vals['work_entry_type_id'].code for vals in paid_date}
        work_entry_unpaid_code = {vals['work_entry_type_id'].code for vals in unpaid_date}

        self.assertSetEqual(work_entry_paid_code, {"013.00"})
        self.assertSetEqual(work_entry_unpaid_code, {"122.00"})

        self.assertFalse(first_leave.l10n_be_sickness_can_relapse)
        self.assertFalse(second_leave.l10n_be_sickness_can_relapse)
        self.assertTrue(third_leave.l10n_be_sickness_can_relapse)
        self.assertFalse(fourth_leave.l10n_be_sickness_can_relapse)

    def test_worker_sick_time_off_01(self):
        """
        If worker started less than one month ago, sick leaves are unpaid
        """
        worker_employee = self.env['hr.employee'].create({
            'name': 'Worker Employee',
            'date_version': '2026-03-01',
            'contract_date_start': '2026-03-01',
            'wage': 2000,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00015').id
        })

        unpaid_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_common_law_illness_after_legal_period')

        self.env['hr.leave'].create([{
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': date(2026, 3, 2),
            'request_date_to': date(2026, 3, 6),
            'employee_id': worker_employee.id,
        }])

        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', worker_employee.id)
        ]).sorted('request_date_from')

        self.assertEqual(len(all_leaves), 1)

        self.assertEqual(all_leaves[0].request_date_from, date(2026, 3, 2))
        self.assertEqual(all_leaves[0].request_date_to, date(2026, 3, 6))
        self.assertEqual(all_leaves[0].work_entry_type_id, unpaid_work_entry_type)

    def test_worker_sick_time_off_02(self):
        """
        The 7 first days: paid 100%
        From 8 to 14 days: paid 85.88%
        15 to 30 days: paid 25.88% on the first 3464.43€ and 85.88% on the remaining amount above 3464.43€
        After 30 days: unpaid
        """
        worker_employee = self.env['hr.employee'].create({
            'name': 'Worker Employee',
            'date_version': '2026-01-01',
            'contract_date_start': '2026-01-01',
            'wage': 2000,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00015').id
        })

        unpaid_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_common_law_illness_after_legal_period')
        first_week_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_incapacity_first_week')
        second_week_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_incapacity_worker_second_week')
        third_fourth_week_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_incapacity_worker_after_second_week')

        self.env['hr.leave'].create([{
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'request_date_from': date(2026, 3, 1),
            'request_date_to': date(2026, 4, 15),
            'employee_id': worker_employee.id,
        }])

        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', worker_employee.id)
        ]).sorted('request_date_from')

        self.assertEqual(len(all_leaves), 4)

        self.assertEqual(all_leaves[0].request_date_from, date(2026, 3, 1))
        self.assertEqual(all_leaves[0].request_date_to, date(2026, 3, 7))
        self.assertEqual(all_leaves[0].work_entry_type_id, first_week_work_entry_type)

        self.assertEqual(all_leaves[1].request_date_from, date(2026, 3, 8))
        self.assertEqual(all_leaves[1].request_date_to, date(2026, 3, 14))
        self.assertEqual(all_leaves[1].work_entry_type_id, second_week_work_entry_type)

        self.assertEqual(all_leaves[2].request_date_from, date(2026, 3, 15))
        self.assertEqual(all_leaves[2].request_date_to, date(2026, 3, 30))
        self.assertEqual(all_leaves[2].work_entry_type_id, third_fourth_week_work_entry_type)

        self.assertEqual(all_leaves[3].request_date_from, date(2026, 3, 31))
        self.assertEqual(all_leaves[3].request_date_to, date(2026, 4, 15))
        self.assertEqual(all_leaves[3].work_entry_type_id, unpaid_work_entry_type)

    def test_worker_work_accident_01(self):
        """
        The 7 first days: paid 100%
        From 8 to 30 days: paid 85.88%
        After 30 days: unpaid
        """
        worker_employee = self.env['hr.employee'].create({
            'name': 'Worker Employee',
            'date_version': '2026-01-01',
            'contract_date_start': '2026-01-01',
            'wage': 2000,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00015').id
        })

        unpaid_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_unpaid')
        first_week_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week')
        first_month_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_second_week')

        self.env['hr.leave'].create([{
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week').id,
            'request_date_from': date(2026, 3, 1),
            'request_date_to': date(2026, 4, 15),
            'employee_id': worker_employee.id,
        }])

        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', worker_employee.id)
        ]).sorted('request_date_from')

        self.assertEqual(len(all_leaves), 3)

        self.assertEqual(all_leaves[0].request_date_from, date(2026, 3, 1))
        self.assertEqual(all_leaves[0].request_date_to, date(2026, 3, 7))
        self.assertEqual(all_leaves[0].work_entry_type_id, first_week_work_entry_type)

        self.assertEqual(all_leaves[1].request_date_from, date(2026, 3, 8))
        self.assertEqual(all_leaves[1].request_date_to, date(2026, 3, 30))
        self.assertEqual(all_leaves[1].work_entry_type_id, first_month_work_entry_type)

        self.assertEqual(all_leaves[2].request_date_from, date(2026, 3, 31))
        self.assertEqual(all_leaves[2].request_date_to, date(2026, 4, 15))
        self.assertEqual(all_leaves[2].work_entry_type_id, unpaid_work_entry_type)

    def test_worker_work_accident_02(self):
        """
        The 7 first days: paid 100%
        From 8 to 30 days: paid 85.88%
        After 30 days: unpaid
        """
        worker_employee = self.env['hr.employee'].create({
            'name': 'Worker Employee',
            'date_version': '2026-01-01',
            'contract_date_start': '2026-01-01',
            'wage': 2000,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00015').id
        })

        unpaid_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_unpaid')
        first_week_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week')
        first_month_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_second_week')

        self.env['hr.leave'].create([
            {
                'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week').id,
                'request_date_from': date(2026, 4, 1),
                'request_date_to': date(2026, 4, 30),
                'employee_id': worker_employee.id,
            },
            {
                'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week').id,
                'request_date_from': date(2026, 5, 1),
                'request_date_to': date(2026, 5, 31),
                'employee_id': worker_employee.id,
            }
        ])

        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', worker_employee.id)
        ]).sorted('request_date_from')

        self.assertEqual(len(all_leaves), 3)

        self.assertEqual(all_leaves[0].request_date_from, date(2026, 4, 1))
        self.assertEqual(all_leaves[0].request_date_to, date(2026, 4, 7))
        self.assertEqual(all_leaves[0].work_entry_type_id, first_week_work_entry_type)

        self.assertEqual(all_leaves[1].request_date_from, date(2026, 4, 8))
        self.assertEqual(all_leaves[1].request_date_to, date(2026, 4, 30))
        self.assertEqual(all_leaves[1].work_entry_type_id, first_month_work_entry_type)

        self.assertEqual(all_leaves[2].request_date_from, date(2026, 5, 1))
        self.assertEqual(all_leaves[2].request_date_to, date(2026, 5, 31))
        self.assertEqual(all_leaves[2].work_entry_type_id, unpaid_work_entry_type)

    def test_employee_work_accident_01(self):
        """
        The 30 first days: paid 100%
        After 30 days: unpaid
        """
        unpaid_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_unpaid')
        first_month_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_guaranteed_monthly')

        self.env['hr.leave'].create([
            {
                'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week').id,
                'request_date_from': date(2026, 3, 1),
                'request_date_to': date(2026, 4, 15),
                'employee_id': self.employee_test.id,
            },
        ])

        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_test.id)
        ]).sorted('request_date_from')

        self.assertEqual(len(all_leaves), 2)

        self.assertEqual(all_leaves[0].request_date_from, date(2026, 3, 1))
        self.assertEqual(all_leaves[0].request_date_to, date(2026, 3, 30))
        self.assertEqual(all_leaves[0].work_entry_type_id, first_month_work_entry_type)

        self.assertEqual(all_leaves[1].request_date_from, date(2026, 3, 31))
        self.assertEqual(all_leaves[1].request_date_to, date(2026, 4, 15))
        self.assertEqual(all_leaves[1].work_entry_type_id, unpaid_work_entry_type)

    def test_employee_work_accident_02(self):
        """
        The 30 first days: paid 100%
        After 30 days: unpaid
        """
        unpaid_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_unpaid')
        first_month_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_guaranteed_monthly')

        self.env['hr.leave'].create([
            {
                'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week').id,
                'request_date_from': date(2026, 4, 1),
                'request_date_to': date(2026, 4, 30),
                'employee_id': self.employee_test.id,
            },
            {
                'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week').id,
                'request_date_from': date(2026, 5, 1),
                'request_date_to': date(2026, 5, 31),
                'employee_id': self.employee_test.id,
            }
        ])

        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_test.id)
        ]).sorted('request_date_from')

        self.assertEqual(len(all_leaves), 2)

        self.assertEqual(all_leaves[0].request_date_from, date(2026, 4, 1))
        self.assertEqual(all_leaves[0].request_date_to, date(2026, 4, 30))
        self.assertEqual(all_leaves[0].work_entry_type_id, first_month_work_entry_type)

        self.assertEqual(all_leaves[1].request_date_from, date(2026, 5, 1))
        self.assertEqual(all_leaves[1].request_date_to, date(2026, 5, 31))
        self.assertEqual(all_leaves[1].work_entry_type_id, unpaid_work_entry_type)

    def test_cdd_employe_sick_leave_less_than_1_month_occupation(self):
        """
        CDD < 3 months + Employé, < 1 month occupation → all 122.00 (unpaid).
        """
        # Contract started 2026-03-01, leave starts 2026-03-15 (< 1 month occupation)
        employee = self._create_cdd_employe(date(2026, 3, 1), date(2026, 5, 15))
        unpaid_work_entry_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_common_law_illness_after_legal_period')

        self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'employee_id': employee.id,
            'request_date_from': date(2026, 3, 15),
            'request_date_to': date(2026, 3, 25),
        })

        all_leaves = self.env['hr.leave'].search([('employee_id', '=', employee.id)]).sorted('request_date_from')
        self.assertEqual(len(all_leaves), 1)
        self.assertEqual(all_leaves[0].work_entry_type_id, unpaid_work_entry_type)

    def test_cdd_employe_sick_leave_7_days(self):
        """
        CDD < 3 months + Employé, > 1 month occupation, 7-day leave → all 010.00 (100%).
        """
        employee = self._create_cdd_employe(date(2026, 1, 1), date(2026, 3, 30))
        first_week_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_incapacity_first_week')

        self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'employee_id': employee.id,
            'request_date_from': date(2026, 3, 1),
            'request_date_to': date(2026, 3, 7),
        })

        all_leaves = self.env['hr.leave'].search([('employee_id', '=', employee.id)]).sorted('request_date_from')
        self.assertEqual(len(all_leaves), 1)
        self.assertEqual(all_leaves[0].work_entry_type_id, first_week_type)

    def test_cdd_employe_sick_leave_14_days(self):
        """
        CDD < 3 months + Employé, > 1 month occupation, 14-day leave → 7d 010.00 + 7d 072.01.
        """
        employee = self._create_cdd_employe(date(2026, 1, 1), date(2026, 3, 30))
        first_week_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_incapacity_first_week')
        second_week_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_incapacity_worker_second_week_short_term_employee')

        self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'employee_id': employee.id,
            'request_date_from': date(2026, 3, 1),
            'request_date_to': date(2026, 3, 14),
        })

        all_leaves = self.env['hr.leave'].search([('employee_id', '=', employee.id)]).sorted('request_date_from')
        self.assertEqual(len(all_leaves), 2)
        self.assertEqual(all_leaves[0].request_date_from, date(2026, 3, 1))
        self.assertEqual(all_leaves[0].request_date_to, date(2026, 3, 7))
        self.assertEqual(all_leaves[0].work_entry_type_id, first_week_type)
        self.assertEqual(all_leaves[1].request_date_from, date(2026, 3, 8))
        self.assertEqual(all_leaves[1].request_date_to, date(2026, 3, 14))
        self.assertEqual(all_leaves[1].work_entry_type_id, second_week_type)

    def test_cdd_employe_sick_leave_30_days(self):
        """
        CDD < 3 months + Employé, > 1 month occupation, 30-day leave → 7d 010.00 + 7d 072.01 + 16d LEAVE219.
        """
        employee = self._create_cdd_employe(date(2026, 1, 1), date(2026, 3, 30))
        first_week_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_incapacity_first_week')
        second_week_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_incapacity_worker_second_week_short_term_employee')
        third_fourth_week_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_incapacity_worker_after_second_week')

        self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'employee_id': employee.id,
            'request_date_from': date(2026, 3, 1),
            'request_date_to': date(2026, 3, 30),
        })

        all_leaves = self.env['hr.leave'].search([('employee_id', '=', employee.id)]).sorted('request_date_from')
        self.assertEqual(len(all_leaves), 3)
        self.assertEqual(all_leaves[0].request_date_to, date(2026, 3, 7))
        self.assertEqual(all_leaves[0].work_entry_type_id, first_week_type)
        self.assertEqual(all_leaves[1].request_date_to, date(2026, 3, 14))
        self.assertEqual(all_leaves[1].work_entry_type_id, second_week_type)
        self.assertEqual(all_leaves[2].request_date_to, date(2026, 3, 30))
        self.assertEqual(all_leaves[2].work_entry_type_id, third_fourth_week_type)

    def test_cdd_employe_sick_leave_40_days(self):
        """
        CDD < 3 months + Employé, 40-day leave → 7d 010.00 + 7d 072.01 + 16d 072.00 + 10d 122.00.
        """
        employee = self._create_cdd_employe(date(2026, 1, 1), date(2026, 3, 30))
        first_week_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_incapacity_first_week')
        second_week_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_incapacity_worker_second_week_short_term_employee')
        third_fourth_week_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_incapacity_worker_after_second_week')
        unpaid_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_common_law_illness_after_legal_period')

        self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'employee_id': employee.id,
            'request_date_from': date(2026, 2, 1),
            'request_date_to': date(2026, 3, 12),
        })

        all_leaves = self.env['hr.leave'].search([('employee_id', '=', employee.id)]).sorted('request_date_from')
        self.assertEqual(len(all_leaves), 4)
        self.assertEqual(all_leaves[0].request_date_from, date(2026, 2, 1))
        self.assertEqual(all_leaves[0].request_date_to, date(2026, 2, 7))
        self.assertEqual(all_leaves[0].work_entry_type_id, first_week_type)
        self.assertEqual(all_leaves[1].request_date_from, date(2026, 2, 8))
        self.assertEqual(all_leaves[1].request_date_to, date(2026, 2, 14))
        self.assertEqual(all_leaves[1].work_entry_type_id, second_week_type)
        self.assertEqual(all_leaves[2].request_date_from, date(2026, 2, 15))
        self.assertEqual(all_leaves[2].request_date_to, date(2026, 3, 2))
        self.assertEqual(all_leaves[2].work_entry_type_id, third_fourth_week_type)
        self.assertEqual(all_leaves[3].request_date_from, date(2026, 3, 3))
        self.assertEqual(all_leaves[3].request_date_to, date(2026, 3, 12))
        self.assertEqual(all_leaves[3].work_entry_type_id, unpaid_type)

    def test_cdd_employe_sick_leave_relapse(self):
        """
        CDD < 3 months + Employé: 7d sick → back to work → relapse → second leave starts at day 8 (072.01).
        """
        employee = self._create_cdd_employe(date(2026, 1, 1), date(2026, 3, 30))
        second_week_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_incapacity_worker_second_week_short_term_employee')

        original_leave = self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'employee_id': employee.id,
            'request_date_from': date(2026, 2, 1),
            'request_date_to': date(2026, 2, 7),
        })
        self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'employee_id': employee.id,
            'request_date_from': date(2026, 2, 10),
            'request_date_to': date(2026, 2, 14),
            'l10n_be_sickness_relapse': True,
            'l10n_be_sickness_relapse_origin_leave_id': original_leave.id,
        })

        all_leaves = self.env['hr.leave'].search([('employee_id', '=', employee.id)]).sorted('request_date_from')
        # Second leave (relapse) should use 072.01 entirely (days 8-14)
        second_relapse_leaves = all_leaves.filtered(lambda l: l.request_date_from >= date(2026, 2, 10))
        self.assertEqual(len(second_relapse_leaves), 1)
        self.assertEqual(second_relapse_leaves[0].work_entry_type_id, second_week_type)

    def test_cdd_employe_at_least_3_months_treated_as_regular_employe(self):
        """
        CDD >= 3 months → treated as regular employee: 30d 013.00, then 122.00.
        """
        # Contract is exactly 3 months, so is_short_term_contract() returns False
        employee = self._create_cdd_employe(date(2026, 1, 1), date(2026, 3, 30))
        # Override: set contract to >= 3 months
        employee.version_id.contract_date_end = date(2026, 3, 31)  # exactly 3 months => not < 3 months

        paid_type = self.env['hr.work.entry.type'].search([('code', '=', '013.00'), ('country_id.code', '=', 'BE')])
        unpaid_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_common_law_illness_after_legal_period')

        self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'employee_id': employee.id,
            'request_date_from': date(2026, 3, 1),
            'request_date_to': date(2026, 4, 15),
        })

        all_leaves = self.env['hr.leave'].search([('employee_id', '=', employee.id)]).sorted('request_date_from')
        self.assertEqual(len(all_leaves), 2)
        self.assertEqual(all_leaves[0].work_entry_type_id, paid_type)
        self.assertEqual(all_leaves[1].work_entry_type_id, unpaid_type)

    def test_cdi_with_end_date_not_treated_as_cdd(self):
        """
        CDI with contract_date_end (resigned) → fixed_term=False → NOT a short-term contract.
        Treated as regular employee: 30d 013.00, then 122.00.
        """
        employee = self.env['hr.employee'].create({
            'name': 'CDI Resigned',
            'company_id': self.belgian_company.id,
            'resource_calendar_id': self.resource_calendar.id,
            'private_country_id': self.env.ref('base.be').id,
            'marital': 'single',
            'spouse_fiscal_status': 'without_income',
            'l10n_be_resident_situation': 'resident',
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'date_version': date(2026, 1, 1),
            'contract_date_start': date(2026, 1, 1),
            'contract_date_end': date(2026, 3, 15),
            'fixed_term': False,  # CDI terminated, not a CDD
            'wage': 2000,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00495').id,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_b').id,
        })

        paid_type = self.env['hr.work.entry.type'].search([('code', '=', '013.00'), ('country_id.code', '=', 'BE')])

        self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_sick_leave').id,
            'employee_id': employee.id,
            'request_date_from': date(2026, 2, 1),
            'request_date_to': date(2026, 2, 14),
        })

        all_leaves = self.env['hr.leave'].search([('employee_id', '=', employee.id)]).sorted('request_date_from')
        # Should be treated as regular employee (013.00), not 7/7/16 split
        self.assertEqual(len(all_leaves), 1)
        self.assertEqual(all_leaves[0].work_entry_type_id, paid_type)

    # =========================================================================
    # CDD < 3 months — Employé work accident scenarios
    # =========================================================================

    def test_cdd_employe_work_accident_7_days(self):
        """
        CDD < 3 months + Employé, 7-day work accident → all 009.00 (100%).
        """
        employee = self._create_cdd_employe(date(2026, 1, 1), date(2026, 3, 30))
        first_week_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week')

        self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week').id,
            'employee_id': employee.id,
            'request_date_from': date(2026, 3, 1),
            'request_date_to': date(2026, 3, 7),
        })

        all_leaves = self.env['hr.leave'].search([('employee_id', '=', employee.id)]).sorted('request_date_from')
        self.assertEqual(len(all_leaves), 1)
        self.assertEqual(all_leaves[0].work_entry_type_id, first_week_type)

    def test_cdd_employe_work_accident_30_days(self):
        """
        CDD < 3 months + Employé, 30-day work accident → 7d 009.00 + 23d 082.01.
        """
        employee = self._create_cdd_employe(date(2026, 1, 1), date(2026, 3, 30))
        first_week_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week')
        first_month_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_second_week_short_term_employee')

        self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week').id,
            'employee_id': employee.id,
            'request_date_from': date(2026, 3, 1),
            'request_date_to': date(2026, 3, 30),
        })

        all_leaves = self.env['hr.leave'].search([('employee_id', '=', employee.id)]).sorted('request_date_from')
        self.assertEqual(len(all_leaves), 2)
        self.assertEqual(all_leaves[0].request_date_to, date(2026, 3, 7))
        self.assertEqual(all_leaves[0].work_entry_type_id, first_week_type)
        self.assertEqual(all_leaves[1].request_date_to, date(2026, 3, 30))
        self.assertEqual(all_leaves[1].work_entry_type_id, first_month_type)

    def test_cdd_employe_work_accident_40_days(self):
        """
        CDD < 3 months + Employé, 40-day work accident → 7d 009.00 + 23d 082.01 + 10d LEAVE117.
        """
        employee = self._create_cdd_employe(date(2026, 1, 1), date(2026, 3, 30))
        first_week_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week')
        first_month_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_second_week_short_term_employee')
        unpaid_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_unpaid')

        self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week').id,
            'employee_id': employee.id,
            'request_date_from': date(2026, 2, 1),
            'request_date_to': date(2026, 3, 12),
        })

        all_leaves = self.env['hr.leave'].search([('employee_id', '=', employee.id)]).sorted('request_date_from')
        self.assertEqual(len(all_leaves), 3)
        self.assertEqual(all_leaves[0].work_entry_type_id, first_week_type)
        self.assertEqual(all_leaves[1].work_entry_type_id, first_month_type)
        self.assertEqual(all_leaves[2].work_entry_type_id, unpaid_type)
        self.assertEqual(all_leaves[1].request_date_to, date(2026, 3, 2))
        self.assertEqual(all_leaves[2].request_date_from, date(2026, 3, 3))

    # =========================================================================
    # Regular CDI employee — work accident scenarios
    # =========================================================================

    def _create_cdi_employe(self, contract_date_start, wage=2000):
        """Helper: create a regular CDI Employé (dmfa_code 495)."""
        return self.env['hr.employee'].create({
            'name': 'CDI Employe',
            'company_id': self.belgian_company.id,
            'resource_calendar_id': self.resource_calendar.id,
            'private_country_id': self.env.ref('base.be').id,
            'marital': 'single',
            'spouse_fiscal_status': 'without_income',
            'l10n_be_resident_situation': 'resident',
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'date_version': contract_date_start,
            'contract_date_start': contract_date_start,
            'fixed_term': False,
            'wage': wage,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00495').id,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'l10n_be_salary_scale_id': self.env.ref('l10n_be_hr_payroll.cp200_b').id,
        })

    def test_cdi_employe_work_accident_30_days(self):
        """
        Regular CDI employee, 30-day work accident → all 30d 012.00 (100%).
        """
        employee = self._create_cdi_employe(date(2026, 1, 1))
        paid_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_guaranteed_monthly')

        self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week').id,
            'employee_id': employee.id,
            'request_date_from': date(2026, 3, 1),
            'request_date_to': date(2026, 3, 30),
        })

        all_leaves = self.env['hr.leave'].search([('employee_id', '=', employee.id)]).sorted('request_date_from')
        self.assertEqual(len(all_leaves), 1)
        self.assertEqual(all_leaves[0].work_entry_type_id, paid_type)

    def test_cdi_employe_work_accident_40_days(self):
        """
        Regular CDI employee, 40-day work accident → 30d 012.00 + 10d LEAVE117.
        """
        employee = self._create_cdi_employe(date(2026, 1, 1))
        paid_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_guaranteed_monthly')
        unpaid_type = self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_unpaid')

        self.env['hr.leave'].create({
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_work_accident_first_week').id,
            'employee_id': employee.id,
            'request_date_from': date(2026, 3, 1),
            'request_date_to': date(2026, 4, 9),
        })

        all_leaves = self.env['hr.leave'].search([('employee_id', '=', employee.id)]).sorted('request_date_from')
        self.assertEqual(len(all_leaves), 2)
        self.assertEqual(all_leaves[0].request_date_to, date(2026, 3, 30))
        self.assertEqual(all_leaves[0].work_entry_type_id, paid_type)
        self.assertEqual(all_leaves[1].request_date_from, date(2026, 3, 31))
        self.assertEqual(all_leaves[1].work_entry_type_id, unpaid_type)

    def test_sickness_relapse_after_unpaid_leave(self):
        """
        Test Case:
        An Employee is sick for a week and then the employee takes 3 months of unpaid/maternity/paternity leave,
        after which the employee becomes sick again with the same illness. The second sick leave should be
        eligible as a relapse of the first one, even if there is a gap of more than 56 days/8 weeks between the two leaves.
        """
        first_sick_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2026, 6, 1),
                "request_date_to": date(2026, 6, 7),
            }
        )
        self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.env.ref('hr_work_entry.l10n_be_work_entry_type_maternity').id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2026, 6, 8),
                "request_date_to": date(2026, 9, 8),
            }
        )
        second_sick_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2026, 9, 9),
                "request_date_to": date(2026, 9, 16),
            }
        )

        work_entries_vals = self.employee_test.version_ids.generate_work_entries(
            date(2026, 9, 10), date(2026, 9, 10)
        )
        work_entries_code = {vals['work_entry_type_id'].code for vals in work_entries_vals}

        self.assertSetEqual(work_entries_code, {"013.00"})
        self.assertTrue(second_sick_leave.l10n_be_sickness_can_relapse)
        self.assertIn(first_sick_leave, second_sick_leave.allowed_l10n_be_sickness_relapse_origin_leave_ids)

    def test_sickness_relapse_consecutive_leaves(self):
        """
        Test Case:
        An Employee takes two sick leaves that are consecutive, meaning that the second leave starts the day after the first one ends.
        The second sick leave should be eligible and defaulted as a relapse of the first one.
        """
        first_sick_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2026, 6, 1),
                "request_date_to": date(2026, 6, 3),
            }
        )
        second_sick_leave = self.env["hr.leave"].create(
            {
                "work_entry_type_id": self.sick_time_off_type.id,
                "employee_id": self.employee_test.id,
                "request_date_from": date(2026, 6, 4),
                "request_date_to": date(2026, 6, 11),
            }
        )

        self.assertTrue(second_sick_leave.l10n_be_sickness_can_relapse)
        self.assertIn(first_sick_leave, second_sick_leave.allowed_l10n_be_sickness_relapse_origin_leave_ids)
        self.assertEqual(first_sick_leave, second_sick_leave.l10n_be_sickness_relapse_origin_leave_id)

    def test_employee_long_term_sick_split_basic(self):
        """
        Test Case:
        Employee Test starts a single sick leave spanning more than 12 months.
        First 30 days -> 013.00 (guaranteed salary)
        Next days up to the 12-month mark -> 122.00 (no guaranteed salary)
        From the 12-month mark onwards -> 123.00 (Long Term Sick)
        """
        self.env["hr.leave"].create({
            "work_entry_type_id": self.sick_time_off_type.id,
            "employee_id": self.employee_test.id,
            "request_date_from": date(2026, 1, 1),
            "request_date_to": date(2027, 8, 31),
        })

        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_test.id)
        ]).sorted('request_date_from')

        self.assertEqual(len(all_leaves), 3)

        self.assertEqual(all_leaves[0].request_date_from, date(2026, 1, 1))
        self.assertEqual(all_leaves[0].request_date_to, date(2026, 1, 30))
        self.assertEqual(all_leaves[0].work_entry_type_id.code, '013.00')

        self.assertEqual(all_leaves[1].request_date_from, date(2026, 1, 31))
        self.assertEqual(all_leaves[1].request_date_to, date(2026, 12, 31))
        self.assertEqual(all_leaves[1].work_entry_type_id.code, '122.00')

        self.assertEqual(all_leaves[2].request_date_from, date(2027, 1, 1))
        self.assertEqual(all_leaves[2].request_date_to, date(2027, 8, 31))
        self.assertEqual(all_leaves[2].work_entry_type_id.code, '123.00')

    def test_employee_long_term_sick_split_with_relapse_gap(self):
        """
        Test Case:
        Employee Test has a validated 16-day sick leave, followed by an 11-day
        gap (back at work, within the 56-day relapse window), then a second sick
        leave (relapse) that runs long enough to hit the 12-month long term sick
        threshold. The 11 gap days should NOT count towards the 12 months, so the
        cutoff for 123.00 should be pushed back by exactly the gap duration.
        """
        first_leave = self.env["hr.leave"].create({
            "work_entry_type_id": self.sick_time_off_type.id,
            "employee_id": self.employee_test.id,
            "request_date_from": date(2026, 1, 1),
            "request_date_to": date(2026, 1, 16),
        })

        self.env["hr.leave"].create({
            "work_entry_type_id": self.sick_time_off_type.id,
            "employee_id": self.employee_test.id,
            "request_date_from": date(2026, 1, 28),
            "request_date_to": date(2027, 1, 29),
            "l10n_be_sickness_relapse": True,
            "l10n_be_sickness_relapse_origin_leave_id": first_leave.id,
        })

        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_test.id),
            ('id', '!=', first_leave.id),
        ]).sorted('request_date_from')

        # base cutoff (chain start 2026-01-01 + 12 months) = 2027-01-01
        # + 11 gap days (2026-01-17 -> 2026-01-27) = 2027-01-12
        long_term_sick_leaves = all_leaves.filtered(lambda l: l.work_entry_type_id.code == '123.00')
        self.assertTrue(long_term_sick_leaves)
        self.assertEqual(min(long_term_sick_leaves.mapped('request_date_from')), date(2027, 1, 12))
        self.assertEqual(max(long_term_sick_leaves.mapped('request_date_to')), date(2027, 1, 29))

    def test_employee_long_term_sick_cutoff_ignores_later_gap(self):
        self.env['hr.leave'].create({
            'work_entry_type_id': self.sick_time_off_type.id,
            'employee_id': self.employee_test.id,
            'request_date_from': date(2026, 1, 1),
            'request_date_to': date(2027, 1, 10),
        })
        origin_leave = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_test.id),
        ], order='request_date_to desc', limit=1)
        relapse_leave = self.env['hr.leave'].create({
            'work_entry_type_id': self.sick_time_off_type.id,
            'employee_id': self.employee_test.id,
            'request_date_from': date(2027, 1, 20),
            'request_date_to': date(2027, 2, 10),
            'l10n_be_sickness_relapse_origin_leave_id': origin_leave.id,
        })

        self.assertEqual(
            relapse_leave._get_l10n_be_long_term_sick_cutoff_date(),
            date(2027, 1, 1),
        )

    def test_employee_long_term_sick_no_relapse_fresh_chain(self):
        """
        Test Case:
        Employee Test has an old, unrelated sick leave chain in the past that
        already passed its own 12-month long term sickness threshold. A NEW, unrelated
        sick leave (not a relapse, gap > 56 days) should NOT be affected by that
        old chain and should NOT be split into 123.00, even though it's created
        after the old chain's cutoff date would technically have passed.
        """
        self.env["hr.leave"].create({
            "work_entry_type_id": self.sick_time_off_type.id,
            "employee_id": self.employee_test.id,
            "request_date_from": date(2023, 1, 1),
            "request_date_to": date(2024, 1, 20),
        })

        # More than 56 days after the previous leave -> not a relapse, fresh chain
        new_leave = self.env["hr.leave"].create({
            "work_entry_type_id": self.sick_time_off_type.id,
            "employee_id": self.employee_test.id,
            "request_date_from": date(2026, 6, 1),
            "request_date_to": date(2026, 6, 20),
            "l10n_be_sickness_relapse": False,
        })

        self.assertFalse(new_leave.l10n_be_sickness_relapse)
        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', self.employee_test.id),
            ('request_date_from', '>=', date(2026, 1, 1)),
        ])
        self.assertTrue(all(l.work_entry_type_id.code in ('013.00', '122.00') for l in all_leaves))
        self.assertFalse(any(l.work_entry_type_id.code == '123.00' for l in all_leaves))

    def test_worker_long_term_sick_split_basic(self):
        """
        Test Case:
        Worker starts a single sick leave spanning more than 12 months.
        Week 1 -> 010.00
        Week 2 -> 082.00
        Weeks 3-4 -> 072.00
        Day 31 up to the 12-month mark -> 122.00
        From the 12-month mark onwards -> 123.00
        """
        worker_employee = self.env['hr.employee'].create({
            'name': 'Worker Employee',
            'date_version': '2025-01-01',
            'contract_date_start': '2025-01-01',
            'wage': 2000,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00015').id
        })

        self.env["hr.leave"].create({
            "work_entry_type_id": self.sick_time_off_type.id,
            "employee_id": worker_employee.id,
            "request_date_from": date(2026, 1, 1),
            "request_date_to": date(2027, 8, 31),
        })

        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', worker_employee.id)
        ]).sorted('request_date_from')

        self.assertEqual(len(all_leaves), 5)

        self.assertEqual(all_leaves[0].request_date_from, date(2026, 1, 1))
        self.assertEqual(all_leaves[0].request_date_to, date(2026, 1, 7))
        self.assertEqual(all_leaves[0].work_entry_type_id.code, '010.00')

        self.assertEqual(all_leaves[1].request_date_from, date(2026, 1, 8))
        self.assertEqual(all_leaves[1].request_date_to, date(2026, 1, 14))
        self.assertEqual(all_leaves[1].work_entry_type_id.code, '082.00')

        self.assertEqual(all_leaves[2].request_date_from, date(2026, 1, 15))
        self.assertEqual(all_leaves[2].request_date_to, date(2026, 1, 30))
        self.assertEqual(all_leaves[2].work_entry_type_id.code, '072.00')

        self.assertEqual(all_leaves[3].request_date_from, date(2026, 1, 31))
        self.assertEqual(all_leaves[3].request_date_to, date(2026, 12, 31))
        self.assertEqual(all_leaves[3].work_entry_type_id.code, '122.00')

        self.assertEqual(all_leaves[4].request_date_from, date(2027, 1, 1))
        self.assertEqual(all_leaves[4].request_date_to, date(2027, 8, 31))
        self.assertEqual(all_leaves[4].work_entry_type_id.code, '123.00')

    def test_worker_long_term_sick_split_with_relapse_gap(self):
        """
        Test Case:
        Worker has a validated 16-day sick leave, followed by an 11-day
        gap (back at work, within the 56-day relapse window), then a second sick
        leave (relapse) that runs long enough to hit the 12-month long term sick
        threshold. The 11 gap days should NOT count towards the 12 months.
        """
        worker_employee = self.env['hr.employee'].create({
            'name': 'Worker Employee',
            'date_version': '2025-01-01',
            'contract_date_start': '2025-01-01',
            'wage': 2000,
            'l10n_be_worker_code_id': self.env.ref('l10n_be_hr_payroll.l10n_be_worker_code_00015').id
        })

        self.env["hr.leave"].create({
            "work_entry_type_id": self.sick_time_off_type.id,
            "employee_id": worker_employee.id,
            "request_date_from": date(2026, 1, 1),
            "request_date_to": date(2026, 1, 16),
        })
        # As a worker, this 16-day leave itself gets split (by weekly pay buckets)
        # into several hr.leave records upon validation. `first_leave` ends up being
        # only the first chunk (request_date_to shrinks to the end of week 1), so the
        # relapse origin must point to the actual last chunk (ending 2026-01-16),
        first_leave_chunks = self.env['hr.leave'].search([
            ('employee_id', '=', worker_employee.id),
            ('request_date_from', '>=', date(2026, 1, 1)),
            ('request_date_to', '<=', date(2026, 1, 16)),
        ]).sorted('request_date_from')
        first_leave_last_chunk = first_leave_chunks[-1]
        self.assertEqual(first_leave_last_chunk.request_date_to, date(2026, 1, 16))

        self.env["hr.leave"].create({
            "work_entry_type_id": self.sick_time_off_type.id,
            "employee_id": worker_employee.id,
            "request_date_from": date(2026, 1, 28),
            "request_date_to": date(2027, 1, 29),
            "l10n_be_sickness_relapse": True,
            "l10n_be_sickness_relapse_origin_leave_id": first_leave_last_chunk.id,
        })

        all_leaves = self.env['hr.leave'].search([
            ('employee_id', '=', worker_employee.id),
            ('id', 'not in', first_leave_chunks.ids),
        ]).sorted('request_date_from')

        # base cutoff (chain start 2026-01-01 + 12 months) = 2027-01-01
        # + 11 gap days (2026-01-17 -> 2026-01-27) = 2027-01-12
        long_term_sick_leaves = all_leaves.filtered(lambda l: l.work_entry_type_id.code == '123.00')
        self.assertTrue(long_term_sick_leaves)
        self.assertEqual(min(long_term_sick_leaves.mapped('request_date_from')), date(2027, 1, 12))
        self.assertEqual(max(long_term_sick_leaves.mapped('request_date_to')), date(2027, 1, 29))
