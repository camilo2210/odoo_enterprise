# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from freezegun import freeze_time

from odoo.tests import tagged, Form
from odoo.exceptions import ValidationError

from .common import TestPayrollCommon


@tagged('post_install_l10n', 'post_install', '-at_install', 'payroll_credit_time')
class TestPayrollCreditTime(TestPayrollCommon):

    @classmethod
    def setUpClass(cls):
        super(TestPayrollCreditTime, cls).setUpClass()

        cls.paid_time_off_type = cls.env.ref('hr_work_entry.be_work_entry_type_legal_leave')

        cls.wizard = cls.env['hr.payroll.alloc.paid.leave'].create({
            'year': 2022,
        })
        cls.wizard.alloc_employee_ids = cls.wizard.alloc_employee_ids.filtered(lambda alloc_employee: alloc_employee.employee_id.id in [cls.employee_georges.id, cls.employee_john.id, cls.employee_a.id])

        with freeze_time('2023-12-31'):
            view = cls.wizard.generate_allocation()
        cls.allocations = cls.env['hr.leave.allocation'].search(view['domain'])
        for allocation in cls.allocations:
            allocation.action_approve()

    def test_credit_time_for_georges(self):
        """
        Test Case:
        The employee Georges asks a credit time to work at mid-time (3 days/week) from 01/02 to 30/04 in the current year,
        normally, he has 14.5 days before his credit and with the credit, the number of paid time off days decreases to
        8.5 days (13.5 days remaining * mid-time's 0.5 rate / his current 4/5's 0.8 rate, rounded to
        the nearest half-day). If Georges didn't take some leaves during his credit, when he exists it,
        his number of paid time off days increase to the number of days he had before.
        """

        georges_current_contract = self.georges_contracts[-1]
        georges_allocation = self.allocations.filtered(lambda alloc: alloc.employee_id.id == self.employee_georges.id)
        self.assertEqual(georges_allocation.number_of_days, 13.5)
        initial_hours = georges_allocation.number_of_hours
        self.assertAlmostEqual(initial_hours, 102.80638977635783, 2)

        # Test for employee Georges
        # Credit time for Georges
        wizard = self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=self.belgian_company.ids, active_id=georges_current_contract.id).new({
            'date_start': date(2023, 2, 1),
            'date_end': date(2023, 4, 30),
            'resource_calendar_id': self.resource_calendar_mid_time.id,
        })
        self.assertEqual(wizard.time_off_allocation, 8.5)
        self.assertAlmostEqual(wizard.time_off_allocation_hours, 64.25, 2)  # 102.81h * (0.5/0.8) rate = 64.25h
        self.assertAlmostEqual(wizard.work_time_rate, 0.5, 2)
        self.assertEqual(wizard.leave_allocation_id.id, georges_allocation.id)
        wizard.with_context(force_schedule=True).action_validate()

        # Apply allocation changes directly
        self.assertEqual(georges_allocation.number_of_days, 13.5)
        self.assertAlmostEqual(georges_allocation.number_of_hours, initial_hours, 2)
        self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(date(2023, 2, 1))
        self.assertEqual(georges_allocation.number_of_days, 8.5)
        self.assertAlmostEqual(georges_allocation.number_of_hours, 64.25, 2)

        # Apply allocation changes directly - Credit time exit
        full_time_contract = self.employee_georges.version_ids[-1]
        self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(full_time_contract.contract_date_start)
        self.assertEqual(georges_allocation.number_of_days, 13.5)
        self.assertAlmostEqual(georges_allocation.number_of_hours, initial_hours, 2)

    def test_manual_time_off_allocation_edit_via_form_keeps_hours(self):
        georges_current_contract = self.georges_contracts[-1]
        georges_allocation = self.allocations.filtered(lambda alloc: alloc.employee_id.id == self.employee_georges.id)
        with Form(
            self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(
                allowed_company_ids=self.belgian_company.ids, active_id=georges_current_contract.id,
                default_resource_calendar_id=self.resource_calendar_mid_time.id,
            )
        ) as form:
            form.date_start = date.today()
            computed_hours = form.time_off_allocation_hours
            form.time_off_allocation = 9.5
        wizard = form.save()
        self.assertEqual(wizard.time_off_allocation, 9.5)
        self.assertAlmostEqual(wizard.time_off_allocation_hours, computed_hours, 2)
        self.assertNotEqual(wizard.time_off_allocation_hours, 0)
        wizard.action_validate()
        self.assertEqual(georges_allocation.number_of_days, 9.5)
        self.assertAlmostEqual(georges_allocation.number_of_hours, computed_hours, 2)

    def test_credit_time_for_john_doe(self):
        """
        Test Case:
        The employee John Doe asks a credit time to work at 9/10 from 01/02 to 30/04 in the current year.
        """
        john_current_contract = self.john_contracts[-1]
        john_allocation = self.allocations.filtered(lambda alloc: alloc.employee_id.id == self.employee_john.id)
        self.assertEqual(john_allocation.number_of_days, 12)

        # Test for employee John Doe
        # Credit time for John Doe
        wizard = self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=self.belgian_company.ids, active_id=john_current_contract.id).new({
            'date_start': date(2023, 2, 1),
            'date_end': date(2023, 4, 30),
            'resource_calendar_id': self.resource_calendar_9_10.id,
        })
        self.assertEqual(wizard.time_off_allocation, 17.0)  # John may have 88% of 20 days this year -> ~17.5
        self.assertAlmostEqual(wizard.work_time_rate, 0.9, 2)
        self.assertEqual(wizard.leave_allocation_id.id, john_allocation.id)
        wizard.with_context(force_schedule=True).action_validate()

        # Apply allocation changes directly
        self.assertEqual(john_allocation.number_of_days, 12)
        self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(date(2023, 2, 1))
        self.assertEqual(john_allocation.number_of_days, 17.0)

        # Apply allocation changes directly - Credit time exit
        continuation_contract = self.employee_john.version_ids[-1]
        self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(continuation_contract.contract_date_start)
        self.assertEqual(john_allocation.number_of_days, 9.5)

    def test_credit_time_for_a(self):
        """
        Test Case:
        The employee A has a contract full-time from 01/01 of the previous year.
        Then, he has right to 20 complete days as paid time off.
        The employee A asks a credit time to work at 4/5 (4 days/week) from 01/02 to 30/04 in the current year.
        With this credit time, his number of paid time off days decrease to 16.
        """
        a_current_contract = self.a_contracts[-1]
        a_allocation = self.allocations.filtered(lambda alloc: alloc.employee_id.id == self.employee_a.id)

        # Test for employee A
        # Credit time for A
        wizard = self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=self.belgian_company.ids, active_id=a_current_contract.id).new({
            'date_start': date(2023, 2, 1),
            'date_end': date(2023, 4, 30),
            'resource_calendar_id': self.resource_calendar_4_5.id,
        })
        self.assertEqual(wizard.time_off_allocation, 16)
        self.assertAlmostEqual(wizard.work_time_rate, 0.8, 2)
        wizard.with_context(force_schedule=True).action_validate()

        self.assertEqual(a_allocation.number_of_days, 20)
        self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(date(2023, 2, 1))
        self.assertEqual(a_allocation.number_of_days, 16)

        # Apply allocation changes directly
        full_time_contract = self.employee_a.version_ids[-1]
        self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(full_time_contract.contract_date_start)
        self.assertEqual(a_allocation.number_of_days, 20)

    def test_remaining_leaves_with_credit_time(self):
        """
        Test Case (only with the employee A)
        - Full Time 01/01 -> 31/05:
            A has an allocation for 20 days.
            A took 6 days off (14 leaves remaining on 20 max).
        - 4/5 (4 days/week) 01/06 -> 31/08:
            The allocation is adjusted to 17 days while keeping the 6 days already taken into account.
            A takes 6 additional days off, for a total of 12 days taken.
        - 1/2 (3 days/week) 01/09 -> 31/12:
            The allocation is adjusted to 15 days while keeping the 12 days already taken into account.
            A has 3 days remaining and cannot take a leave exceeding the remaining allocation.

        - When the employee returns to full time, the allocation is adjusted to 15.5 days.
        """
        a_current_contract = self.a_contracts[-1]
        a_allocation = self.allocations.filtered(lambda alloc: alloc.employee_id.id == self.employee_a.id)
        self.assertEqual(a_allocation.number_of_days, 20)

        taken_leaves = 0
        # leaves don't count if theyre planned in the future, they have to actually be taken
        with freeze_time(date(2023, 2, 1)):
            leave = self.env['hr.leave'].create({
                'work_entry_type_id': self.paid_time_off_type.id,
                'employee_id': self.employee_a.id,
                'request_date_from': date(2023, 2, 1),
                'request_date_to': date(2023, 2, 8),
            })
            leave.action_approve()
            taken_leaves += leave.number_of_days
            self.assertEqual(taken_leaves, 6)

            # Credit time
            wizard = self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=self.belgian_company.ids, active_id=a_current_contract.id).new({
                'date_start': date(2023, 6, 1),
                'resource_calendar_id': self.resource_calendar_4_5.id,
            })
            self.assertEqual(wizard.time_off_allocation, 17)
            self.assertAlmostEqual(wizard.work_time_rate, 0.8, 2)
            wizard.with_context(force_schedule=True).action_validate()

            # Apply allocation changes directly
            self.assertEqual(a_allocation.number_of_days, 20)
            self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(date(2023, 6, 1))
            self.assertEqual(a_allocation.number_of_days, 17)

        with freeze_time(date(2023, 7, 1)):
            leave = self.env['hr.leave'].create({
                'work_entry_type_id': self.paid_time_off_type.id,
                'employee_id': self.employee_a.id,
                'request_date_from': date(2023, 7, 1),
                'request_date_to': date(2023, 7, 11),
            })
            leave.action_approve()
            taken_leaves += leave.number_of_days
            self.assertEqual(taken_leaves, 12)

            # Credit time
            a_contract_4_5 = self.employee_a.version_ids[-1]
            wizard = self.env['l10n_be.hr.payroll.schedule.change.wizard'].with_context(allowed_company_ids=self.belgian_company.ids, active_id=a_contract_4_5.id).new({
                'date_start': date(2023, 9, 1),
                'date_end': date(2023, 12, 31),
                'resource_calendar_id': self.resource_calendar_mid_time.id,
            })

            # The allocation accounts for the 12 days already taken by the employee.
            self.assertEqual(wizard.time_off_allocation, 15)
            self.assertAlmostEqual(wizard.work_time_rate, 0.5, 2)
            wizard.with_context(force_schedule=True).action_validate()

            # Apply allocation changes directly
            self.assertEqual(a_allocation.number_of_days, 17)
            self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(date(2023, 9, 2))
            self.assertEqual(a_allocation.number_of_days, 15)

            # He now has 3 days remaining, so requesting more than 3 days should raise an error.
            with self.assertRaises(ValidationError):
                leave = self.env['hr.leave'].create({
                    'work_entry_type_id': self.paid_time_off_type.id,
                    'employee_id': self.employee_a.id,
                    'request_date_from': date(2023, 10, 4),
                    'request_date_to': date(2023, 10, 16),
                })
                leave.action_approve()

            full_time_contract = self.employee_a.version_ids[-1]
            self.assertEqual(a_allocation.number_of_days, 15)
            self.env['l10n_be.schedule.change.allocation']._cron_update_allocation_from_new_schedule(full_time_contract.contract_date_start)
            self.assertEqual(a_allocation.number_of_days, 14.0)
