# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_right_to_legal_leaves')
class TestPayrollRightToLegalLeaves(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super(TestPayrollRightToLegalLeaves, cls).setUpClass()

        cls.paid_time_off_type = cls.env.ref('hr_work_entry.be_work_entry_type_legal_leave')

        cls.resource_calendar_24_hours_per_week_5_days_per_week = cls.resource_calendar.copy({
            'name': 'Calendar 24 Hours/Week',
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 15}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 15}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
            ]
        })

        cls.resource_calendar_24_hours_per_week_4_days_per_week = cls.resource_calendar.copy({
            'name': 'Calendar 24 Hours/Week',
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 15}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 15}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 15}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 15}),
            ]
        })

        cls.resource_calendar_20_hours_per_week = cls.resource_calendar.copy({
            'name': 'Calendar 20 Hours/Week',
            'full_time_required_hours': 38,
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
            ]
        })

    def test_credit_time_for_employee_test_example1(self):
        """
        Test Case:
        In 2017, Employee Test has a Full-Time contract (38 hours/week - 5 days/week)
        In 2018, he keeps his contract until 31/03/2018 and take no time off.
        After that, he has a new contract on 01/04/2018, he works 30 hours/week (4 days/week)

        The calculation of paid time off should be :
        On 01/01/2018, this employee has right 20 days of Paid Time Off.
        On 01/04/2018, this employee should has 16 days of Paid Time Off.
        """
        wizard = self.env['hr.payroll.alloc.paid.leave'].new({
            'year': 2017,
        })
        wizard.alloc_employee_ids = wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_test.id)
        self.assertEqual(wizard.alloc_employee_ids.paid_time_off, 20, "Employee Test should have 20 days for 2018")

        view = wizard.generate_allocation()
        allocation = self.env['hr.leave.allocation'].search(view['domain'])
        allocation.action_approve()

        self.assertEqual(allocation.number_of_days, 20)
        self.assertEqual(allocation.number_of_hours, 152)

        employee_test_current_contract = self.test_contracts[-1]

        # Credit time
        wizard = self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=self.belgian_company.ids, active_id=employee_test_current_contract.id).new({
            'date_start': date(2018, 4, 1),
            'date_end': date(2018, 4, 30),
            'resource_calendar_id': self.resource_calendar_30_hours_per_week.id,
        })
        self.assertEqual(wizard.time_off_allocation, 16)
        view = wizard.with_context(force_schedule=True).action_validate()
        self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(date(2018, 4, 1))
        self.assertEqual(allocation.number_of_days, 16)

    def test_credit_time_for_employee_test_example2(self):
        """
        Test Case:
        In 2017, Employee Test has a Full-Time contract (38 hours/week - 5 days/week)
        In 2018, he keeps his contract until 31/03/2018 and take 4 days of paid time offs.
        After that, he has a new contract on 01/04/2018, he works 30 hours/week (4 days/week)

        The calculation of paid time off should be :
        On 01/01/2018, this employee has right 20 days of Paid Time Off.
        On 01/04/2018, this employee should has 16.5 days of Paid Time Off.
        """
        wizard = self.env['hr.payroll.alloc.paid.leave'].new({
            'year': 2017,
        })
        wizard.alloc_employee_ids = wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_test.id)
        self.assertEqual(wizard.alloc_employee_ids.paid_time_off, 20, "Employee Test should have 20 days for 2018")

        view = wizard.generate_allocation()
        allocation = self.env['hr.leave.allocation'].search(view['domain'])
        allocation.action_approve()

        self.assertEqual(allocation.number_of_days, 20)
        self.assertEqual(allocation.number_of_hours, 152)

        employee_test_current_contract = self.test_contracts[-1]

        leave = self.env['hr.leave'].create({
            'work_entry_type_id': self.paid_time_off_type.id,
            'employee_id': self.employee_test.id,
            'request_date_from': date(2018, 2, 1),
            'request_date_to': date(2018, 2, 5),
        })
        leave.action_approve()

        # Credit time
        wizard = self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=self.belgian_company.ids, active_id=employee_test_current_contract.id).new({
            'date_start': date(2018, 4, 1),
            'date_end': date(2018, 4, 30),
            'resource_calendar_id': self.resource_calendar_30_hours_per_week.id,
        })
        self.assertEqual(wizard.time_off_allocation, 16.5)
        view = wizard.with_context(force_schedule=True).action_validate()
        self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(date(2018, 4, 1))
        self.assertEqual(allocation.number_of_days, 16.5, "4 days taken + 16 remaining * (30/38), rounded to 0.5, gives 16.5.")

    def test_credit_time_for_employee_test_example3(self):
        """
        Test Case:
        In 2017, Employee Test has 3 contracts :
            - From 01/01/2017 to 05/31/2017: 38 hours/week (5 days/week)
            - From 06/01/2017 to 07/31/2017: 24 hours/week (5 days/week)
            - From 08/01/2017 to 12/31/2017: 20 hours/week (5 days/week)

        In 2018, he keeps his contract until 03/31/2018 and take 4 days of paid time offs.
        After that, he has a new contract on 04/01/2018, he works 30 hours/week (4 days/week)

        The calculation of paid time off should be :
        On 01/01/2018, this employee has right 20 days of Paid Time Off.
        On 04/01/2018, this employee should has 14.5 days of Paid Time Off.
        """
        employee_test_first_contract = self.test_contracts[-1]
        employee_test_first_contract.write({
            'contract_date_end': date(2017, 5, 31)
        })
        self.env.flush_all()  # Otherwise write cannot be seen by the query in _compute_alloc_employee_ids
        self.test_contracts |= employee_test_first_contract.copy({
            'name': "Employee Test's Contract",
            'employee_id': self.employee_test.id,
            'resource_calendar_id': self.resource_calendar_24_hours_per_week_5_days_per_week.id,
            'date_version': date(2017, 6, 1),
            'contract_date_start': date(2017, 6, 1),
            'contract_date_end': date(2017, 7, 31),
            'wage': employee_test_first_contract.wage / 24 * 38
        })

        self.test_contracts |= employee_test_first_contract.copy({
            'name': "Employee Test's Contract",
            'employee_id': self.employee_test.id,
            'resource_calendar_id': self.resource_calendar_20_hours_per_week.id,
            'date_version': date(2017, 8, 1),
            'contract_date_start': date(2017, 8, 1),
            'contract_date_end': date(2017, 12, 31),
            'wage': employee_test_first_contract.wage / 20 * 38
        })

        employee_test_current_contract = employee_test_first_contract.copy({
            'name': "Employee Test's Contract",
            'employee_id': self.employee_test.id,
            'resource_calendar_id': self.resource_calendar_20_hours_per_week.id,
            'date_version': date(2018, 1, 1),
            'contract_date_start': date(2018, 1, 1),
            'contract_date_end': False,
            'wage': employee_test_first_contract.wage / 20 * 38
        })
        self.test_contracts |= employee_test_current_contract

        wizard = self.env['hr.payroll.alloc.paid.leave'].new({
            'year': 2017,
        })
        wizard.alloc_employee_ids = wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id == self.employee_test.id)
        self.assertEqual(wizard.alloc_employee_ids.paid_time_off, 20)
        self.assertEqual(wizard.alloc_employee_ids.paid_time_off_to_allocate, 20)
        self.assertEqual(wizard.alloc_employee_ids.hours_to_allocate, 80)

        view = wizard.generate_allocation()
        allocation = self.env['hr.leave.allocation'].search(view['domain'])
        allocation.action_approve()

        self.assertEqual(allocation.number_of_days, 20)
        self.assertEqual(allocation.number_of_hours, 80)

        leave = self.env['hr.leave'].create({
            'work_entry_type_id': self.paid_time_off_type.id,
            'employee_id': self.employee_test.id,
            'request_date_from': date(2018, 2, 1),
            'date_from': date(2018, 2, 1),
            'request_date_to': date(2018, 2, 3),
            'date_to': date(2018, 2, 3),
            'number_of_days': 1.5
        })
        leave.action_approve()

        # Credit time
        wizard = self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=self.belgian_company.ids, active_id=employee_test_current_contract.id).new({
            'date_start': date(2018, 4, 1),
            'date_end': date(2018, 4, 30),
            'resource_calendar_id': self.resource_calendar_24_hours_per_week_4_days_per_week.id,
        })
        self.assertEqual(wizard.time_off_allocation, 14.5)
        view = wizard.with_context(force_schedule=True).action_validate()
        self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(date(2018, 4, 1))
        self.assertEqual(allocation.number_of_days, 14.5, "14.5 days allocated by the credit")
